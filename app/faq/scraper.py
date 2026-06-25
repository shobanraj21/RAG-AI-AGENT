import os
import re
import json
import hashlib
from datetime import datetime
from urllib.parse import urljoin, urlparse
import psycopg2
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from playwright.sync_api import sync_playwright
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from config import (
    faq_log,
    PG_HOST, PG_PORT, PG_DB, PG_USER, PG_PASSWORD,
    SCRAPER_URLS, FOOTER_BASE_URL, FOOTER_TOPICS,
    GEMINI_EMBEDDING_MODEL, GEMINI_MODEL, VERTEX_PROJECT_ID, VERTEX_LOCATION, VERTEX_SERVICE_ACCOUNT_JSON,
    PG_FAQ_TABLE, CHUNK_SIZE, DEBUG_MODE, DEBUG_DIR,
)


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────
def _save_debug_file(filename: str, content):
    if not DEBUG_MODE:
        return
    os.makedirs(DEBUG_DIR, exist_ok=True)
    filepath = os.path.join(DEBUG_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        if isinstance(content, (dict, list)):
            json.dump(content, f, indent=2, ensure_ascii=False)
        else:
            f.write(content)
    faq_log.debug(f"[SCRAPER] Saved debug file: {filename}")


def _url_hash(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:8]


def _is_scrapable_url(url: str, base_url: str) -> bool:
    parsed = urlparse(url)
    base_domain = urlparse(base_url).netloc
    if parsed.netloc and parsed.netloc != base_domain:
        return False
    if any(url.lower().endswith(ext) for ext in [".pdf", ".jpg", ".png", ".svg", ".mp4", ".zip"]):
        return False
    if url.startswith("#") or not url.startswith("http"):
        return False
    return True


# ──────────────────────────────────────────────
# Fetch + Clean + Markdown
# ──────────────────────────────────────────────
# Fetches page HTML using headless Chromium — retries up to 3 times on failure
@retry(
    retry=retry_if_exception_type(Exception),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8)
)
def _fetch_url(url: str) -> str:
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)
        except Exception:
            # Fall back to system Chrome or Edge if playwright browser not downloaded
            for channel in ("chrome", "msedge"):
                try:
                    browser = p.chromium.launch(headless=True, channel=channel)
                    break
                except Exception:
                    continue
            else:
                raise RuntimeError("No usable browser found. Run: playwright install chromium")
        page = browser.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(6000)
        html = page.content()
        browser.close()
        return html


def _clean_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript",
                     "svg", "iframe", "img", "picture", "form", "button",
                     "input", "select", "textarea", "aside"]):
        tag.decompose()
    for a in soup.find_all("a"):
        a.unwrap()
    for tag in soup.find_all(True):
        text = tag.get_text(separator=" ", strip=True)
        has_block_child = any(
            c.name in {"p", "ul", "ol", "li", "h1", "h2", "h3", "h4", "table", "div"}
            for c in tag.children if hasattr(c, "name")
        )
        if not has_block_child and len(text) < 60 and tag.name in {"div", "span", "section", "article"}:
            tag.unwrap()
    return str(soup)


def _html_to_markdown(html: str) -> str:
    content = md(html, heading_style="ATX")
    content = re.sub(r'!\[.*?\]\(.*?\)', '', content)
    content = re.sub(r'https?://\S+', '', content)
    content = re.sub(r'\n{3,}', '\n\n', content)
    # Promote list-wrapped headings: "* #### Name" -> "#### Name"
    content = re.sub(r'^\*\s+(#{1,6}\s+)', r'\1', content, flags=re.MULTILINE)
    # Promote plain "Mr./Ms./Mrs. Name (NN years)" lines into #### headings
    content = re.sub(
        r'^((?:Mr|Ms|Mrs|Dr)\. [A-Z][^\n]{3,60}\(\d{2} years\)[^\n]*)',
        r'#### \1',
        content, flags=re.MULTILINE
    )
    return content.strip()


# ──────────────────────────────────────────────
# Parsing — works for any page structure
# ──────────────────────────────────────────────
def _extract_faq_pairs(markdown: str) -> list:
    subsections = []
    for match in re.finditer(r'^\*\s+(.+\?)\s*\n((?:(?!\*\s).+\n?)*)', markdown, re.MULTILINE):
        question = match.group(1).strip()
        answer = re.sub(r'\s+', ' ', match.group(2).strip())
        if question and answer and len(answer) > 20:
            subsections.append({'level': 3, 'title': question, 'content': answer, 'subsections': []})

    for match in re.finditer(r'Q[:\.]?\s*(.+\?)\s*\n+A[:\.]?\s*(.+?)(?=\nQ[:\.]?|\Z)', markdown, re.DOTALL | re.MULTILINE):
        question = match.group(1).strip()
        answer = re.sub(r'\s+', ' ', match.group(2).strip())
        if question and answer and len(answer) > 20:
            subsections.append({'level': 3, 'title': question, 'content': answer, 'subsections': []})
    return subsections


def _extract_plain_paragraphs(markdown: str) -> str:
    paragraphs = []
    for line in markdown.split('\n'):
        stripped = line.strip()
        if re.match(r'^#+\s', stripped):
            continue
        if re.match(r'^\*\s+\S.{0,40}$', stripped) and not re.search(r'[.!?:]', stripped):
            continue
        if len(stripped) > 40:
            paragraphs.append(stripped)
    return ' '.join(paragraphs)


def _parse_sections(markdown: str) -> list:
    markdown = re.sub(r'!\[.*?\]\(.*?\)', '', markdown)
    markdown = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', markdown)
    markdown = re.sub(r'https?://\S+', '', markdown)
    markdown = re.sub(r'\n{3,}', '\n\n', markdown)

    lines = markdown.split('\n')
    sections, current_h2, current_h3, current_h4, buffer = [], None, None, None, []

    def flush(target):
        if buffer and target is not None:
            text = ' '.join(' '.join(buffer).split())
            text = re.sub(r'\*{1,2}([^*]+)\*{1,2}', r'\1', text)
            text = re.sub(r'\*{1,2}', '', text)
            if text:
                target['content'] = (target.get('content', '') + ' ' + text).strip()
        buffer.clear()

    current_h4 = None

    for line in lines:
        stripped = line.strip()
        h1 = re.match(r'^#\s+(.+)$', stripped)
        h2 = re.match(r'^##\s+(.+)$', stripped)
        h3 = re.match(r'^###\s+(.+)$', stripped)
        h4 = re.match(r'^####\s+(.+)$', stripped)

        if (h2 or h1) and not stripped.startswith('###'):
            flush(current_h4 if current_h4 else current_h3 if current_h3 else current_h2)
            title = (h2 or h1).group(1).strip()
            current_h2 = {'level': 2, 'title': title, 'content': '', 'subsections': []}
            current_h3 = None
            current_h4 = None
            sections.append(current_h2)
        elif h3 and not stripped.startswith('####'):
            flush(current_h4 if current_h4 else current_h3 if current_h3 else current_h2)
            title = h3.group(1).strip()
            if re.match(r'^[\d,\.₹\+\s]{1,25}$', title) and not re.search(r'[a-zA-Z]', title):
                # Number-only heading - skip the heading but keep following text in current section
                current_h4 = None
                continue
            current_h3 = {'level': 3, 'title': title, 'content': '', 'subsections': []}
            current_h4 = None
            if current_h2:
                current_h2['subsections'].append(current_h3)
        elif h4:
            flush(current_h4 if current_h4 else current_h3 if current_h3 else current_h2)
            title = h4.group(1).strip()
            # Strip markdown bold/italic from name
            title = re.sub(r'\*{1,2}([^*]+)\*{1,2}', r'\1', title).strip()
            if not title:
                continue
            current_h4 = {'level': 4, 'title': title, 'content': '', 'subsections': []}
            parent = current_h3 if current_h3 else current_h2
            if parent:
                parent['subsections'].append(current_h4)
        else:
            if stripped:
                buffer.append(stripped)

    flush(current_h4 if current_h4 else current_h3 if current_h3 else current_h2)

    # Type 2: FAQ pairs
    faq_sections = _extract_faq_pairs(markdown)
    if faq_sections:
        sections.append({'level': 2, 'title': 'FAQs', 'content': '', 'subsections': faq_sections})

    # Type 3: Plain paragraph fallback
    if not sections:
        plain = _extract_plain_paragraphs(markdown)
        if plain:
            sections.append({'level': 2, 'title': 'Content', 'content': plain, 'subsections': []})

    def has_content(s):
        return s.get('content', '').strip() or any(sub.get('content', '').strip() for sub in s.get('subsections', []))

    return [s for s in sections if has_content(s)]


def _sections_to_chunks(sections: list, url: str, topic: str = "", link_text: str = "") -> list:
    chunks, seen = [], set()

    def process(section, parent_title=""):
        title = section.get("title", "")
        content = section.get("content", "")
        full_title = f"{parent_title} > {title}" if parent_title else title

        if content:
            product_prefix = f"[{link_text}] " if link_text else ""
            section_prefix = f"{full_title}: " if full_title else ""
            full_text = f"{product_prefix}{section_prefix}{content}"
            words = full_text.split()
            current = ""
            for word in words:
                candidate = f"{current} {word}".strip()
                if len(candidate) > CHUNK_SIZE:
                    if current and current not in seen:
                        seen.add(current)
                        chunks.append({"url": url, "text": current, "section": full_title,
                                       "topic": topic, "link_text": link_text})
                    current = word
                else:
                    current = candidate
            if current and current not in seen:
                seen.add(current)
                chunks.append({"url": url, "text": current, "section": full_title,
                               "topic": topic, "link_text": link_text})

        for sub in section.get("subsections", []):
            process(sub, full_title)

    for s in sections:
        process(s)
    return chunks


# ──────────────────────────────────────────────
# Scrape a URL
# ──────────────────────────────────────────────
def scrape_page(url: str, topic: str = "", link_text: str = "") -> list:
    faq_log.info(f"[SCRAPER] Scraping: {url}")
    try:
        html = _fetch_url(url)
        _save_debug_file(f"raw_{_url_hash(url)}.html", html)

        clean = _clean_html(html)
        markdown = _html_to_markdown(clean)
        _save_debug_file(f"page_{_url_hash(url)}.md", markdown)

        sections = _parse_sections(markdown)
        _save_debug_file(f"extracted_{_url_hash(url)}.json", sections)

        chunks = _sections_to_chunks(sections, url, topic, link_text)
        _save_debug_file(f"chunks_{_url_hash(url)}.json", chunks)

        faq_log.info(f"[SCRAPER] {url} → {len(chunks)} chunks")
        return chunks
    except Exception as e:
        faq_log.error(f"[SCRAPER] Failed: {url} | {type(e).__name__}: {e}")
        return []


# ──────────────────────────────────────────────
# Footer scraping
# ──────────────────────────────────────────────
def scrape_footer_topics(base_url: str, wanted_topics: list) -> list:
    faq_log.info(f"[SCRAPER] Extracting footer from: {base_url}")
    html = _fetch_url(base_url)
    soup = BeautifulSoup(html, "html.parser")

    footer = soup.find("footer")
    if not footer:
        faq_log.warning("[SCRAPER] No <footer> tag found")
        return []

    # Extract all topics and their links from footer
    all_topics = {}
    heading_tags = {'h2', 'h3', 'h4', 'h5', 'strong', 'b'}
    for container in footer.find_all(True):
        if container.name not in heading_tags:
            continue
        topic_name = container.get_text(strip=True)
        if not topic_name or len(topic_name) > 60:
            continue
        links = []
        for sibling in container.find_next_siblings():
            if sibling.name in heading_tags:
                break
            for a in (sibling.find_all('a') if sibling.name != 'a' else [sibling]):
                href = a.get('href', '').strip()
                text = a.get_text(strip=True)
                if href and text:
                    links.append({'text': text, 'url': urljoin(base_url, href)})
        if links:
            all_topics[topic_name] = links

    _save_debug_file("footer_all_topics.json", all_topics)
    faq_log.info(f"[SCRAPER] Found footer topics: {list(all_topics.keys())}")

    missing = [t for t in wanted_topics if t not in all_topics]
    if missing:
        faq_log.warning(f"[SCRAPER] Topics not found in footer: {missing}")

    all_chunks = []
    seen_urls = set()

    for topic in wanted_topics:
        if topic not in all_topics:
            continue
        links = all_topics[topic]
        faq_log.info(f"[SCRAPER] Topic: {topic} | {len(links)} links")
        for link in links:
            if _stop_requested:
                faq_log.warning("[SCRAPER] Stop requested — halting scraping")
                return all_chunks
            url = link["url"]
            if url in seen_urls or not _is_scrapable_url(url, base_url):
                continue
            seen_urls.add(url)
            chunks = scrape_page(url, topic=topic, link_text=link["text"])
            all_chunks.extend(chunks)

    return all_chunks


# ──────────────────────────────────────────────
# Embeddings + Storage
# ──────────────────────────────────────────────
# Calls Gemini Embedding API for a chunk — retries up to 3 times, returns (vector, token_count)
@retry(
    retry=retry_if_exception_type(Exception),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8)
)
def _get_embedding(text: str) -> tuple[list, int]:
    from google import genai
    from google.genai import types
    from google.oauth2 import service_account
    if VERTEX_SERVICE_ACCOUNT_JSON:
        creds = service_account.Credentials.from_service_account_file(
            VERTEX_SERVICE_ACCOUNT_JSON,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        client = genai.Client(
            vertexai=True, project=VERTEX_PROJECT_ID,
            location=VERTEX_LOCATION, credentials=creds,
        )
    else:
        client = genai.Client(
            vertexai=True, project=VERTEX_PROJECT_ID, location=VERTEX_LOCATION,
        )
    result = client.models.embed_content(
        model=GEMINI_EMBEDDING_MODEL, contents=text,
        config=types.EmbedContentConfig(output_dimensionality=3072),
    )
    token_count = client.models.count_tokens(
        model=GEMINI_MODEL, contents=text,
    ).total_tokens or 0
    return result.embeddings[0].values, token_count


# Creates/truncates faq_embeddings table, embeds all chunks and stores in pgvector
def store_embeddings(all_chunks: list):
    faq_log.info(f"[SCRAPER] Storing {len(all_chunks)} chunks...")
    conn = psycopg2.connect(host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASSWORD)
    cur = conn.cursor()

    cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    cur.execute(f"SELECT to_regclass('{PG_FAQ_TABLE}');")
    existed = cur.fetchone()[0] is not None
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {PG_FAQ_TABLE} (
            id SERIAL PRIMARY KEY,
            url TEXT,
            chunk_text TEXT,
            section TEXT,
            topic TEXT,
            link_text TEXT,
            embedding vector(3072)
        );
    """)
    if existed:
        faq_log.info("[SCRAPER] Table '%s' already exists — truncating for fresh load", PG_FAQ_TABLE)
    else:
        faq_log.info("[SCRAPER] Table '%s' did not exist — created new", PG_FAQ_TABLE)
    cur.execute(f"TRUNCATE TABLE {PG_FAQ_TABLE} RESTART IDENTITY;")
    conn.commit()

    total_tokens = 0
    for i, chunk in enumerate(all_chunks, 1):
        if _stop_requested:
            faq_log.warning("[SCRAPER] Stop requested — halting at chunk %d/%d", i, len(all_chunks))
            conn.commit()
            break
        embedding, tokens = _get_embedding(chunk["text"])
        total_tokens += tokens
        cur.execute(
            f"INSERT INTO {PG_FAQ_TABLE} (url, chunk_text, section, topic, link_text, embedding) VALUES (%s, %s, %s, %s, %s, %s)",
            (chunk["url"], chunk["text"], chunk.get("section", ""),
             chunk.get("topic", ""), chunk.get("link_text", ""), embedding)
        )
        faq_log.info(f"[SCRAPER] [{i}/{len(all_chunks)}] embedded | tokens_so_far={total_tokens}")
    conn.commit()

    cur.close()
    conn.close()

    faq_log.info(
        "[SCRAPER] Embedding token usage | chunks=%d | total_tokens=%d",
        len(all_chunks), total_tokens,
    )
    print(f"\n[SCRAPER] Total chunks embedded : {len(all_chunks)}")
    print(f"[SCRAPER] Total tokens used     : {total_tokens}")
    faq_log.info("[SCRAPER] All chunks stored successfully")


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────
# Entry point — scrapes direct URLs + footer topics, deduplicates, stores embeddings
def run():
    faq_log.info("[SCRAPER] Starting scraper run")

    all_chunks = []
    seen_texts = set()

    def add_chunks(chunks):
        for chunk in chunks:
            if chunk["text"] not in seen_texts:
                seen_texts.add(chunk["text"])
                all_chunks.append(chunk)

    # Mode 1: Scrape direct URLs
    if SCRAPER_URLS:
        faq_log.info(f"[SCRAPER] Scraping {len(SCRAPER_URLS)} direct URL(s)")
        for url in SCRAPER_URLS:
            if _stop_requested:
                faq_log.warning("[SCRAPER] Stop requested — halting scraping")
                return
            add_chunks(scrape_page(url))

    # Mode 2: Scrape footer topics
    if FOOTER_BASE_URL and FOOTER_TOPICS:
        faq_log.info(f"[SCRAPER] Scraping footer topics: {FOOTER_TOPICS}")
        add_chunks(scrape_footer_topics(FOOTER_BASE_URL, FOOTER_TOPICS))

    if not all_chunks:
        faq_log.warning("[SCRAPER] No chunks extracted. Check SCRAPER_URLS or FOOTER_BASE_URL in .env")
        return

    faq_log.info(f"[SCRAPER] Total unique chunks: {len(all_chunks)}")
    _save_debug_file(f"summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", {
        "timestamp": datetime.now().isoformat(),
        "total_chunks": len(all_chunks),
        "scraper_urls": SCRAPER_URLS,
        "footer_base_url": FOOTER_BASE_URL,
        "footer_topics": FOOTER_TOPICS,
        "table": PG_FAQ_TABLE,
        "embedding_model": "gemini-embedding-001",
    })

    store_embeddings(all_chunks)

    faq_log.info("[SCRAPER] Scraping complete")


_stop_requested = False

def request_stop():
    global _stop_requested
    _stop_requested = True

def reset_stop():
    global _stop_requested
    _stop_requested = False


if __name__ == "__main__":
    run()
