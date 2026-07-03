import re
import math
import asyncio
from sentence_transformers import CrossEncoder
from google import genai
from google.genai import types
from google.oauth2 import service_account

from config import (
    faq_log,
    GEMINI_EMBEDDING_MODEL, RERANKER_PATH,
    VERTEX_PROJECT_ID, VERTEX_LOCATION, VERTEX_SERVICE_ACCOUNT_JSON,
    _get_pg_table, _get_pg_pool, _get_pg_vector_dim, TOP_K, _get_nlp,
    RERANK_SCORE_THRESHOLD, RERANK_POOL_SIZE,
)

# ──────────────────────────────────────────────
# Local MS-Marco Reranker
# ──────────────────────────────────────────────
# MS-Marco cross-encoder reranker — loaded at startup
_reranker = None

def _get_reranker():
    return _reranker

def _load_reranker():
    global _reranker
    if _reranker is not None:
        return _reranker
    _reranker = CrossEncoder(RERANKER_PATH, local_files_only=True)
    faq_log.info("[RERANKER] MS-Marco reranker loaded from %s", RERANKER_PATH)
    return _reranker


def _vertex_rerank(query: str, chunks: list, top_k: int) -> list:
    if not chunks:
        return []
       
    rerank_threshold = RERANK_SCORE_THRESHOLD
    try:
        reranker = _get_reranker()
        pairs = [(query, c["text"]) for c in chunks]
        scores = reranker.predict(pairs)
        for i, chunk in enumerate(chunks):
            chunk["rerank_score"] = float(scores[i])
        ranked = sorted(chunks, key=lambda x: x["rerank_score"], reverse=True)
        filtered = [c for c in ranked if c["rerank_score"] >= rerank_threshold]
        faq_log.debug("[RERANKER] threshold=%.2f | before=%d | after=%d", rerank_threshold, len(ranked), len(filtered))
        return filtered[:top_k]
    except Exception as e:
        faq_log.warning("[RERANKER] Reranker failed (%s) — falling back to RRF order", e)
        for chunk in chunks:
            chunk["rerank_score"] = 0.0
        return chunks[:top_k]


# ──────────────────────────────────────────────
# Noise Filter
# ──────────────────────────────────────────────
_NOISE_PATTERNS = re.compile(r'^News\s*&\s*Press Releases', re.IGNORECASE)


# Filters out noisy/irrelevant chunks before returning results
def _is_noisy_chunk(text: str) -> bool:
    if bool(_NOISE_PATTERNS.match(text.strip())):
        return True
    text_lower = text.lower()
    if text_lower.startswith('cholamandalam securities') or text_lower.startswith('csec'):
        return True
    return False


# ──────────────────────────────────────────────
# Shared Vertex AI client for embeddings
# ──────────────────────────────────────────────
_embedding_client = None

def _get_embedding_client():
    global _embedding_client
    if _embedding_client is not None:
        return _embedding_client
    if VERTEX_SERVICE_ACCOUNT_JSON:
        creds = service_account.Credentials.from_service_account_file(
            VERTEX_SERVICE_ACCOUNT_JSON,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        _embedding_client = genai.Client(
            vertexai=True,
            project=VERTEX_PROJECT_ID,
            location=VERTEX_LOCATION,
            credentials=creds,
        )
    else:
        _embedding_client = genai.Client(
            vertexai=True,
            project=VERTEX_PROJECT_ID,
            location=VERTEX_LOCATION,
        )
    return _embedding_client


# ──────────────────────────────────────────────
# Embedding
# ──────────────────────────────────────────────
# Calls Gemini Embedding API — sends all texts in ONE batch request, returns list of vectors
def get_gemini_embeddings_batch(texts: list[str]) -> list[list]:
    client = _get_embedding_client()
    result = client.models.embed_content(
        model=GEMINI_EMBEDDING_MODEL,
        contents=texts,
        config=types.EmbedContentConfig(output_dimensionality=3072),
    )
    return [e.values for e in result.embeddings]


# Async batch wrapper — single API call for all queries, validates dimensions
async def get_embeddings_batch(texts: list[str]) -> list[list]:
    embeddings = await asyncio.to_thread(get_gemini_embeddings_batch, texts)
    expected_dim = _get_pg_vector_dim()
    if expected_dim is not None:
        for emb in embeddings:
            if len(emb) != expected_dim:
                raise ValueError(
                    f"Embedding dimension mismatch: model returned {len(emb)} "
                    f"dimensions but table stores {expected_dim}."
                )
    return embeddings


# ──────────────────────────────────────────────
# Semantic Retrieval
# ──────────────────────────────────────────────
# Queries pgvector using cosine similarity, filters low-similarity results (<0.2)
def retrieve_semantic_chunks(query_embedding: list, top_k: int = TOP_K) -> list:
    table = _get_pg_table()
    pool = _get_pg_pool()
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT chunk_text, url, 1 - (embedding <=> %s::vector) AS similarity, section
                FROM {table}
                ORDER BY embedding <=> %s::vector
                LIMIT %s;
                """,
                (query_embedding, query_embedding, top_k),
            )
            rows = cur.fetchall()
        return [
            {"text": row[0], "url": row[1], "similarity": row[2], "section": row[3] or ""}
            for row in rows
            if row[2] > 0.2 and not _is_noisy_chunk(row[0])
        ]
    finally:
        pool.putconn(conn)

# ──────────────────────────────────────────────
# BM25
# ──────────────────────────────────────────────
def _tokenize(text: str) -> list:
    nlp = _get_nlp()
    doc = nlp(text.lower())
    return [token.lemma_ for token in doc if not token.is_punct and not token.is_space]


def _build_bm25_index(corpus: list) -> tuple:
    df = {}
    total_len = 0
    tokenized = []
    for doc in corpus:
        tokens = _tokenize(doc)
        tokenized.append(tokens)
        total_len += len(tokens)
        for t in set(tokens):
            df[t] = df.get(t, 0) + 1
    avgdl = total_len / max(len(corpus), 1)
    return tokenized, df, avgdl


def _bm25_score(query_tokens, doc_tokens, df, n_docs, avgdl, k1=1.5, b=0.75) -> float:
    score = 0.0
    dl = len(doc_tokens)
    tf_map = {}
    for t in doc_tokens:
        tf_map[t] = tf_map.get(t, 0) + 1
    for t in query_tokens:
        if t not in tf_map:
            continue
        tf = tf_map[t]
        idf = math.log((n_docs - df.get(t, 0) + 0.5) / (df.get(t, 0) + 0.5) + 1)
        score += idf * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * dl / max(avgdl, 1)))
    return score


def _bm25_rerank(query: str, chunks: list) -> list:
    if not chunks:
        return []
    corpus = [c["text"] for c in chunks]
    tokenized, df, avgdl = _build_bm25_index(corpus)
    query_tokens = _tokenize(query)
    n_docs = len(corpus)
    for i, doc_tokens in enumerate(tokenized):
        chunks[i]["bm25_score"] = _bm25_score(query_tokens, doc_tokens, df, n_docs, avgdl)
    return chunks


# ──────────────────────────────────────────────
# Merge + Rerank  (semantic → BM25 RRF → Vertex reranker)
# ──────────────────────────────────────────────
# Combines semantic rank + BM25 rank using RRF, then reranks top 20 with MS-Marco
def merge_and_rerank(semantic: list, query: str) -> list:
    if not semantic:
        return []
    rerank_pool_size = RERANK_POOL_SIZE

    candidates = [dict(c) for c in semantic]
    candidates = _bm25_rerank(query, candidates)

    sem_rank = {c["text"]: i for i, c in enumerate(semantic)}
    bm25_sorted = sorted(candidates, key=lambda c: c.get("bm25_score", 0), reverse=True)
    bm25_rank = {c["text"]: i for i, c in enumerate(bm25_sorted)}

    for c in candidates:
        t = c["text"]
        s = sem_rank.get(t, len(candidates))
        b = bm25_rank.get(t, len(candidates))
        c["rrf_score"] = 0.7 * (1 / (60 + s)) + 0.3 * (1 / (60 + b))

    fused = sorted(candidates, key=lambda c: c["rrf_score"], reverse=True)
    top_candidates = fused[:min(rerank_pool_size, len(fused))]
    return _vertex_rerank(query, top_candidates, top_k=len(top_candidates))

