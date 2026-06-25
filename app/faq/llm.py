import asyncio
import json
import re
import time
from google import genai
from google.genai import types
from google.oauth2 import service_account

from config import (
    faq_log,
    GEMINI_MODEL,
    VERTEX_PROJECT_ID, VERTEX_LOCATION, VERTEX_SERVICE_ACCOUNT_JSON,
    CONTEXT_MAX_CHAR,
)
from variables import SYSTEM_PROMPT, REWRITE_SYSTEM_PROMPT


_EMPTY_USAGE: dict = {"promptTokenCount": 0, "candidatesTokenCount": 0, "totalTokenCount": 0, "cachedContentTokenCount": 0}
_answer_cache_name: str | None = None
_answer_cache_expires: float = 0.0
_CACHE_TTL_SECONDS = 3600  # 1 hour

# ──────────────────────────────────────────────
# Google GenAI client
# ──────────────────────────────────────────────
def _get_genai_client():
    if VERTEX_SERVICE_ACCOUNT_JSON:
        creds = service_account.Credentials.from_service_account_file(
            VERTEX_SERVICE_ACCOUNT_JSON,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        return genai.Client(
            vertexai=True,
            project=VERTEX_PROJECT_ID,
            location=VERTEX_LOCATION,
            credentials=creds,
        )
    return genai.Client(
        vertexai=True,
        project=VERTEX_PROJECT_ID,
        location=VERTEX_LOCATION,
    )

# ──────────────────────────────────────────────
# System Prompt Cache
# ──────────────────────────────────────────────
# Caches the system prompt on Vertex AI for 1hr to reduce input tokens on every request
def _get_answer_cache(client) -> str | None:
    global _answer_cache_name, _answer_cache_expires
    now = time.time()
    if _answer_cache_name and now < _answer_cache_expires:
        faq_log.info(
            "[CACHE] System prompt cache HIT | name=%s | expires_in=%.0fs",
            _answer_cache_name, _answer_cache_expires - now,
        )
        return _answer_cache_name
    try:
        cached = client.caches.create(
            model=GEMINI_MODEL,
            config=types.CreateCachedContentConfig(
                system_instruction=SYSTEM_PROMPT,
                ttl=f"{_CACHE_TTL_SECONDS}s",
            ),
        )
        _answer_cache_name = cached.name
        _answer_cache_expires = now + _CACHE_TTL_SECONDS - 60
        faq_log.info("[CACHE] System prompt cached | name=%s | ttl=%ds", _answer_cache_name, _CACHE_TTL_SECONDS)
        return _answer_cache_name
    except Exception as e:
        faq_log.warning("[CACHE] Failed to create cache (%s) — using inline system prompt", e)
        return None

# ──────────────────────────────────────────────
# Core Gemini Call — returns (content, usage)
# ──────────────────────────────────────────────
# Core Gemini API call — runs in a thread (asyncio.to_thread) to avoid blocking the event loop
def _call_gemini_llm(messages: list, max_tokens: int = 8192, call_name: str = "unknown") -> tuple[str, dict]:

    system_text = "\n\n".join(
        m.get("content", "") for m in messages
        if m.get("role") == "system" and m.get("content")
    )
    contents = []
    for message in messages:
        role    = message.get("role")
        content = message.get("content", "")
        if role == "system" or not content:
            continue
        contents.append(
            types.Content(
                role="model" if role == "assistant" else "user",
                parts=[types.Part(text=content)],
            )
        )

    if not contents:
        raise ValueError("At least one non-system message is required.")

    started_at = time.perf_counter()
    try:
        client = _get_genai_client()
        cache_name = _get_answer_cache(client) if call_name == "generate_answer" else None
        config = types.GenerateContentConfig(
            temperature=0.1,
            max_output_tokens=max_tokens,
            stop_sequences=["\n\nQuestion:", "\nQuestion:", "Q:", "\n\nAnswer:"],
            cached_content=cache_name if cache_name else None,
            system_instruction=None if cache_name else (system_text or None),
        )
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=contents,
            config=config,
        )
        elapsed = time.perf_counter() - started_at
        content = response.text.strip() if response.text else ""
        um = response.usage_metadata
        usage = {
            "promptTokenCount":        getattr(um, "prompt_token_count", 0) or 0,
            "candidatesTokenCount":    getattr(um, "candidates_token_count", 0) or 0,
            "totalTokenCount":         getattr(um, "total_token_count", 0) or 0,
            "cachedContentTokenCount": getattr(um, "cached_content_token_count", 0) or 0,
        }
        finish_reason = (
            response.candidates[0].finish_reason.name
            if response.candidates else "n/a"
        )
        faq_log.debug(
            "[GEMINI] RESPONSE | call=%s | wall=%.2fs | finish=%s | prompt=%s | output=%s | cached=%s",
            call_name, elapsed, finish_reason,
            usage.get("promptTokenCount"), usage.get("candidatesTokenCount"), usage.get("cachedContentTokenCount"),
        )
        return content or "Sorry, I could not generate a response right now.", usage
    except Exception as e:
        faq_log.error("[GENAI] Error: %s: %s", type(e).__name__, e)
        return "We are receiving too many AI requests right now. Please try again in a minute.", _EMPTY_USAGE


async def _call_gemini(messages: list, max_tokens: int = 8192, call_name: str = "unknown") -> tuple[str, dict]:
    return await asyncio.to_thread(_call_gemini_llm, messages, max_tokens, call_name)


# ──────────────────────────────────────────────
# Query Rewriter
# ──────────────────────────────────────────────
async def rewrite_query(query: str, history: list) -> tuple[dict, dict]:
    # LLM1: Classifies intent, rewrites query to English, generates search variations.
    # Returns: {intent, search_query, language, variations}
    default = {"intent": "faq", "search_query": query, "language": "english", "variations": []}

    if not history:
        history_text = ""
    else:
        recent = history[-6:]
        lines = []
        for m in recent:
            if m['role'] == 'assistant':
                content = m['content'][:150]
            else:
                content = m['content'][:400]
            lines.append(f"{m['role'].upper()}: {content}")
        history_text = "\n".join(lines)

    user_content = ""
    if history_text:
        user_content += f"[CONVERSATION HISTORY]\n{history_text}\n\n"
    user_content += f"[LATEST QUERY]\n{query}"

    try:
        raw, usage = await _call_gemini(
            [
                {"role": "system",  "content": REWRITE_SYSTEM_PROMPT},
                {"role": "user",    "content": user_content},
            ],
            call_name="rewrite_query",
        )
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE)
        parsed = json.loads(raw)
        search_query = (parsed.get("search_query") or "").strip() or query
        language     = (parsed.get("language") or "english").strip().lower()
        variations   = [v.strip() for v in (parsed.get("variations") or []) if isinstance(v, str) and v.strip()]
        intent       = (parsed.get("intent") or "faq").strip().lower()
        return {"intent": intent, "search_query": search_query, "language": language, "variations": variations}, usage
    except Exception as e:
        faq_log.warning("[REWRITE] Failed (%s: %s) — falling back to original query", type(e).__name__, e)
        return default, _EMPTY_USAGE


# ──────────────────────────────────────────────
# Answer Generator — returns (answer, usage)
# ──────────────────────────────────────────────
async def generate_answer(
    original_query: str,
    search_query: str,
    context_chunks: list,
    variations: list | None = None,
    language: str = "english",
) -> tuple[str, dict]:
    
    char_budget = CONTEXT_MAX_CHAR
    # LLM2: Generates final answer using retrieved context chunks.
    if context_chunks:
        capped = []
        total = 0
        for c in context_chunks:
            text = c["text"]
            section = c.get("section", "")
            if section and not text.startswith(section):
                text = f"{section}: {text}"
            c = dict(c)
            c["text"] = text
            total += len(text)
            if total > char_budget:
                break
            capped.append(c)
        context = "\n\n".join(c["text"] for c in capped)
        faq_log.debug(
            "[CONTEXT] Built | chunks=%d | chars=%d",
            len(capped), len(context),
        )
    else:
        context = ""

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    lang_instruction = f"IMPORTANT: You MUST reply in {language}.\n\n" if language != "english" else ""
    query_lines = [f"Received query: {original_query}"]
    if search_query and search_query != original_query:
        query_lines.append(f"Rewritten query: {search_query}")
    if variations:
        query_lines.append("Possible queries:")
        query_lines.extend(f"- {variation}" for variation in variations if variation)
    query_block = "\n".join(query_lines)

    if context:
        user_content = (
            lang_instruction
            + f"[CONTEXT]\n{context}\n[/CONTEXT]\n\n"
            f"{query_block}\n\n"
            "Answer using ONLY the context above."
        )
    else:
        user_content = (
            lang_instruction
            + query_block
        )

    messages.append({"role": "user", "content": user_content})

    return await _call_gemini(messages, call_name="generate_answer")
