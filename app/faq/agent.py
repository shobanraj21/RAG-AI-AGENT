import asyncio
import time
import uuid
import json
from pathlib import Path
from collections import defaultdict

from config import (
    faq_log, token_log,
    save_message, _get_pg_pool, PG_CHAT_TABLE, TOP_K,
)

from variables import CHATBOT_NAME, COMPANY_NAME
from retrieval import (
    get_embedding, retrieve_semantic_chunks,
    merge_and_rerank,
)
from llm import rewrite_query, generate_answer

# Accumulates token counts per day in memory. Loaded from log on first request to survive restarts.
_daily_totals: dict = defaultdict(lambda: {
    "rewrite_in": 0, "rewrite_out": 0,
    "answer_in": 0, "answer_out": 0,
    "cached": 0, "grand_total": 0,
})
_daily_totals_loaded: set = set()


def _load_daily_totals_from_log(today: str) -> None:
    if today in _daily_totals_loaded:
        return
    _daily_totals_loaded.add(today)
    from config import _get_log_dir
    log_path = Path(_get_log_dir()) / f"faq_token_usage_{today}.log"
    if not log_path.exists():
        return
    try:
        with open(log_path, encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if e.get("date") != today:
                    continue
                _daily_totals[today]["rewrite_in"]  += e.get("rewrite_in", 0)
                _daily_totals[today]["rewrite_out"] += e.get("rewrite_out", 0)
                _daily_totals[today]["answer_in"]   += e.get("answer_in", 0)
                _daily_totals[today]["answer_out"]  += e.get("answer_out", 0)
                _daily_totals[today]["cached"]      += e.get("cached", 0)
                _daily_totals[today]["grand_total"] += e.get("grand_total", 0)
    except Exception:
        pass

def _usage_count(usage: dict, key: str) -> int:
    return int((usage or {}).get(key, 0) or 0)


def _log_token_usage(
    session_id: str,
    intent: str,
    rewrite_usage: dict,
    answer_usage: dict | None = None,
    elapsed_s: float = 0.0,
) -> None:
    # Logs per-request token counts + running daily totals to token_usage.log as JSON.
    answer_usage = answer_usage or {}
    rewrite_prompt = _usage_count(rewrite_usage, "promptTokenCount")
    rewrite_output = _usage_count(rewrite_usage, "candidatesTokenCount")
    answer_prompt = _usage_count(answer_usage, "promptTokenCount")
    answer_output = _usage_count(answer_usage, "candidatesTokenCount")
    cached_tokens = _usage_count(answer_usage, "cachedContentTokenCount")
    total_input = rewrite_prompt + answer_prompt
    total_output = rewrite_output + answer_output
    grand_total = total_input + total_output

    today = time.strftime("%Y-%m-%d")
    _load_daily_totals_from_log(today)
    _daily_totals[today]["rewrite_in"]  += rewrite_prompt
    _daily_totals[today]["rewrite_out"] += rewrite_output
    _daily_totals[today]["answer_in"]   += answer_prompt
    _daily_totals[today]["answer_out"]  += answer_output
    _daily_totals[today]["cached"]      += cached_tokens
    _daily_totals[today]["grand_total"] += grand_total
    d = _daily_totals[today]

    token_log.info(json.dumps({
        "date":        today,
        "time":        time.strftime("%H:%M:%S"),
        "session_id":  session_id,
        "intent":      intent,
        "rewrite_in":  rewrite_prompt,
        "rewrite_out": rewrite_output,
        "answer_in":   answer_prompt,
        "answer_out":  answer_output,
        "cached":      cached_tokens,
        "total_in":    total_input,
        "total_out":   total_output,
        "grand_total": grand_total,
        "elapsed_s":   round(elapsed_s, 2),
        "day_rewrite_in":  d["rewrite_in"],
        "day_rewrite_out": d["rewrite_out"],
        "day_answer_in":   d["answer_in"],
        "day_answer_out":  d["answer_out"],
        "day_cached":      d["cached"],
        "day_grand_total": d["grand_total"],
    }, ensure_ascii=False))


def _get_history(session_id: str) -> list:
    # Fetches last 6 messages from chat_history for context-aware responses.
    try:
        pool = _get_pg_pool()
        conn = pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT role, message FROM {PG_CHAT_TABLE} WHERE session_id = %s ORDER BY id DESC LIMIT 6",
                    (session_id,)
                )
                rows = cur.fetchall()
            return [{"role": r[0], "content": r[1]} for r in reversed(rows)]
        finally:
            pool.putconn(conn)
    except Exception:
        return []


async def invoke_faq_agent(
    query: str,
    session_id: str = None,
    history: list = None,
) -> dict:
    # Main entry point. Runs full RAG pipeline: rewrite → embed → retrieve → rerank → generate.
    try:
        if not session_id:
            session_id = str(uuid.uuid4())
            faq_log.info(f"[SESSION: {session_id}] NEW SESSION CREATED")
        
        faq_log.info("=" * 100)
        faq_log.info(f"[SESSION: {session_id}] RECEIVED QUERY: {query}")

        # Auto-fetch history from DB and rewrite query in parallel
        norm_history = history if history is not None else _get_history(session_id)

        # Step 1: Rewrite query
        rewrite_start = time.perf_counter()
        rewritten, rewrite_usage = await rewrite_query(query, norm_history)
        rewrite_elapsed = time.perf_counter() - rewrite_start
        faq_log.debug(
            "[SESSION: %s] QUERY REWRITE | elapsed=%.2fs | search_query=%r",
            session_id, rewrite_elapsed,
            rewritten.get("search_query"),
        )

        search_query = rewritten.get("search_query") or query
        language     = rewritten.get("language", "english")
        variations   = rewritten.get("variations") or []
        intent       = rewritten.get("intent", "faq")

        # Short-circuit: no retrieval or LLM2 needed for greetings/acknowledgements
        if intent in ("greeting", "acknowledgement"):
            answer, answer_usage = await generate_answer(
                original_query=query,
                search_query="",
                variations=[],
                context_chunks=[],
                language=language,
            )
            save_message(session_id, "user", query)
            save_message(session_id, "assistant", answer)
            faq_log.info(f"[SESSION: {session_id}] {intent.upper()} SHORT-CIRCUIT (lang={language})")
            _log_token_usage(session_id, intent, rewrite_usage, answer_usage, elapsed_s=rewrite_elapsed)
            return {"status_code": 200, "result_text": answer, "session_id": session_id}

        # Step 2: Multi-Query + Embed + Retrieve
        all_queries = []
        for candidate_query in [search_query] + variations:
            if candidate_query and candidate_query not in all_queries:
                all_queries.append(candidate_query)
        faq_log.debug(f"[SESSION: {session_id}]   queries={all_queries}")

        # Run all embeddings in parallel
        embeddings = await asyncio.gather(
            *[get_embedding(q) for q in all_queries]
        )

        faq_log.debug(f"[SESSION: {session_id}] RETRIEVAL")
        chunk_lists = await asyncio.gather(
            *[asyncio.to_thread(retrieve_semantic_chunks, emb, TOP_K) for emb in embeddings]
        )
        seen_texts = set()
        all_chunks = []
        for chunks in chunk_lists:
            for chunk in chunks:
                if chunk["text"] not in seen_texts:
                    seen_texts.add(chunk["text"])
                    all_chunks.append(chunk)

        faq_log.debug(f"[SESSION: {session_id}]   Semantic (deduped): {len(all_chunks)}")
        ranked_chunks = await asyncio.to_thread(merge_and_rerank, all_chunks, search_query)

        faq_log.debug(f"[SESSION: {session_id}]   Final chunks: {len(ranked_chunks)}")
        for index, chunk in enumerate(ranked_chunks):
            faq_log.debug(
                "[SESSION: %s]   chunk[%d/%d] section=%r sim=%.3f rerank=%.3f | %r",
                session_id, index + 1, len(ranked_chunks),
                chunk.get("section", ""), chunk.get("similarity", 0.0),
                chunk.get("rerank_score", 0.0), chunk["text"][:150].replace("\n", " "),
            )

        if not ranked_chunks:
            faq_log.warning(f"[SESSION: {session_id}] NO CHUNKS FOUND")
            return {"status_code": 200, "result_text": "Sorry, I do not have any information about that topic."}

        # Step 3: Generate answer
        faq_log.debug("[SESSION: %s] LLM QUERY SNAPSHOT | original=%r | all_queries=%s", session_id, search_query, all_queries)
        llm_start = time.perf_counter()

        answer, answer_usage = await generate_answer(
            original_query=query,
            search_query=search_query,
            variations=variations,
            context_chunks=ranked_chunks,
            language=language,
        )

        llm_elapsed = time.perf_counter() - llm_start

        # ── Real token summary for this session request ──
        rewrite_prompt    = _usage_count(rewrite_usage, "promptTokenCount")
        rewrite_output    = _usage_count(rewrite_usage, "candidatesTokenCount")
        answer_prompt     = _usage_count(answer_usage, "promptTokenCount")
        answer_output     = _usage_count(answer_usage, "candidatesTokenCount")
        cached_tokens     = _usage_count(answer_usage, "cachedContentTokenCount")
        total_input       = rewrite_prompt + answer_prompt
        total_output      = rewrite_output + answer_output
        grand_total       = total_input + total_output

        faq_log.info(
            "[SESSION: %s] TOKEN USAGE | "
            "rewrite=(%d in / %d out) | "
            "answer=(%d in / %d out, cached=%s) | "
            "TOTAL input=%d output=%d grand=%d | "
            "elapsed=%.2fs",
            session_id,
            rewrite_prompt, rewrite_output,
            answer_prompt, answer_output, cached_tokens,
            total_input, total_output, grand_total,
            llm_elapsed,
        )

        faq_log.info(f"[SESSION: {session_id}] ANSWER GENERATED: {answer}")

        if session_id:
            faq_log.debug(f"[SESSION: {session_id}] SAVING TO DATABASE...")
            save_message(session_id, "user", query)
            save_message(session_id, "assistant", answer)

        _log_token_usage(session_id, intent, rewrite_usage, answer_usage, llm_elapsed)

        faq_log.info(f"[SESSION: {session_id}] RESPONSE COMPLETE - Status: 200")
        faq_log.info("=" * 100)
        return {"status_code": 200, "result_text": answer, "session_id": session_id}

    except Exception as e:
        faq_log.error(f"[SESSION: {session_id}] ERROR: {type(e).__name__}: {str(e)}", exc_info=True)
        faq_log.error("=" * 100)
        return {"status_code": 500, "result_text": "We ran into a technical issue. Please try again later.", "session_id": session_id}
