import os
import re
import glob
import logging
import psycopg2
import psycopg2.pool
import spacy
from datetime import date, timedelta
from dotenv import load_dotenv

_IS_SCRAPER = os.path.basename(__import__('__main__').__file__ or '') == 'scraper.py' if hasattr(__import__('__main__'), '__file__') else False


# Loads .env from project root (two levels up from app/faq/)
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".env"), override=True)

# ──────────────────────────────────────────────
# Logger
# ──────────────────────────────────────────────
def _make_log_handler(log_path: str, fmt: str) -> logging.FileHandler:
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S"))
    return handler

def _get_log_dir() -> str:
    log_dir = os.getenv("LOGGER_PATH", os.path.join(os.path.dirname(__file__), "logs"))
    if not os.path.isabs(log_dir):
        # Resolve relative path from project root (two levels up from app/faq/)
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        log_dir = os.path.join(project_root, log_dir)
    os.makedirs(log_dir, exist_ok=True)
    return log_dir

def _get_faq_logger() -> logging.Logger:
    today = date.today().isoformat()  # yyyy-mm-dd
    logger = logging.getLogger(f"faq_agent_{today}")
    if logger.handlers:
        return logger
    log_path = os.path.join(_get_log_dir(), f"faq_log_{today}.log")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(_make_log_handler(log_path, "%(asctime)s | %(levelname)s | %(message)s"))
    logger.propagate = False
    return logger


def _get_token_logger() -> logging.Logger:
    today = date.today().isoformat()  # yyyy-mm-dd
    logger = logging.getLogger(f"token_usage_{today}")
    if logger.handlers:
        return logger
    log_path = os.path.join(_get_log_dir(), f"faq_token_usage_{today}.log")
    logger.setLevel(logging.INFO)
    logger.addHandler(_make_log_handler(log_path, "%(message)s"))
    logger.propagate = False
    return logger

#faq_log automatically get deleted after 7 days 
def _cleanup_old_logs() -> None:
    retention_days = int(os.getenv("LOG_RETENTION_DAYS"))
    cutoff = date.today() - timedelta(days=retention_days)
    log_dir = _get_log_dir()
    for pattern in ("faq_log_*.log", "faq_token_usage_*.log"):
        for filepath in glob.glob(os.path.join(log_dir, pattern)):
            fname = os.path.basename(filepath)  # e.g. faq_log_2026-06-01.log
            date_part = fname.replace("faq_token_usage_", "").replace("faq_log_", "").replace(".log", "")
            try:
                if date.fromisoformat(date_part) < cutoff:
                    os.remove(filepath)
            except ValueError:
                pass  # skip files that don't match expected date format


# Always returns today's logger — safe across midnight if server restarts
faq_log = _get_faq_logger()
token_log = _get_token_logger()
_cleanup_old_logs()

# ──────────────────────────────────────────────
# Env Config
# ──────────────────────────────────────────────
PG_HOST      = os.getenv("PG_HOST")
PG_PORT      = os.getenv("PG_PORT")
PG_DB        = os.getenv("PG_DB")
PG_USER      = os.getenv("PG_USER")
PG_PASSWORD  = os.getenv("PG_PASSWORD")
GEMINI_EMBEDDING_MODEL     = os.getenv("GEMINI_EMBEDDING_MODEL")
VERTEX_RERANKER_MODEL      = os.getenv("VERTEX_RERANKER_MODEL")
RERANKER_PATH          = os.getenv("RERANKER_PATH")
GEMINI_MODEL               = (os.getenv("GEMINI_MODEL") or "").strip()
VERTEX_PROJECT_ID          = (os.getenv("VERTEX_PROJECT_ID") or "").strip()
VERTEX_LOCATION            = (os.getenv("VERTEX_LOCATION") or "").strip()
VERTEX_SERVICE_ACCOUNT_JSON = (os.getenv("VERTEX_SERVICE_ACCOUNT_JSON") or "").strip()
SCRAPER_URLS    = [u.strip() for u in (os.getenv("SCRAPER_URLS") or "").split(",") if u.strip()]
FOOTER_BASE_URL = os.getenv("FOOTER_BASE_URL", "")
FOOTER_TOPICS   = [t.strip() for t in (os.getenv("FOOTER_TOPICS") or "").split(",") if t.strip()]

PG_FAQ_TABLE  = os.getenv("PG_FAQ_TABLE", "faq")
PG_CHAT_TABLE = os.getenv("PG_CHAT_TABLE", "chat_history")
TOP_K                  = int(os.getenv("TOP_K", "40"))
CHUNK_SIZE             = int(os.getenv("CHUNK_SIZE", "600"))
RERANK_SCORE_THRESHOLD = float(os.getenv("RERANK_SCORE_THRESHOLD", "-1.0"))
RERANK_POOL_SIZE       = int(os.getenv("RERANK_POOL_SIZE", "40"))
CONTEXT_MAX_CHAR   = int(os.getenv("CONTEXT_MAX_CHAR", "10000"))
DEBUG_MODE    = os.getenv("DEBUG_MODE", "false").lower() == "true"
DEBUG_DIR     = os.getenv("DEBUG_DIR", "./scraper_debug")

# ──────────────────────────────────────────────
# Singletons
# ──────────────────────────────────────────────
_pg_pool: psycopg2.pool.ThreadedConnectionPool | None = None
_pg_vector_dim: int | None = None
_nlp = None


def _get_nlp():
    global _nlp
    if _nlp is None:
        _nlp = spacy.load("en_core_web_sm", disable=["parser", "ner"])
    return _nlp


def _get_pg_table() -> str:
    table = (PG_FAQ_TABLE or "").strip()
    if not table:
        raise ValueError("PG_FAQ_TABLE is not configured.")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table):
        raise ValueError(f"Invalid PG_FAQ_TABLE value: {table!r}")
    return table


# Shared PG connection pool — reused across all requests (1-10 connections)
def _get_pg_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pg_pool
    if _pg_pool is None:
        _pg_pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1, maxconn=10,
            host=PG_HOST, port=PG_PORT,
            dbname=PG_DB, user=PG_USER, password=PG_PASSWORD,
        )
    return _pg_pool


def _get_pg_vector_dim() -> int | None:
    global _pg_vector_dim
    if _pg_vector_dim is not None:
        return _pg_vector_dim
    table = _get_pg_table()
    pool = _get_pg_pool()
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT vector_dims(embedding) FROM {table} WHERE embedding IS NOT NULL LIMIT 1;")
            row = cur.fetchone()
            _pg_vector_dim = row[0] if row and row[0] else None
    finally:
        pool.putconn(conn)
    return _pg_vector_dim

# Auto-creates chat_history table on startup if it doesn't exist
def _ensure_chat_table() -> None:
    pool = _get_pg_pool()
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass(%s)", (PG_CHAT_TABLE,))
            if cur.fetchone()[0] is not None:
                return
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {PG_CHAT_TABLE} (
                    id SERIAL PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """)
            conn.commit()
        faq_log.info("[DB] chat table '%s' ready", PG_CHAT_TABLE)
    except Exception as e:
        faq_log.error("[DB] Failed to create chat table: %s", e)
    finally:
        pool.putconn(conn)

# Saves each user/assistant message to chat_history for session context
def save_message(session_id: str, role: str, message: str) -> None:
    pool = _get_pg_pool()
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"INSERT INTO {PG_CHAT_TABLE} (session_id, role, message) VALUES (%s, %s, %s)",
                (session_id, role, message),
            )
            conn.commit()
    except Exception as e:
        faq_log.error(f"[DB] Error saving message: {e}")
    finally:
        pool.putconn(conn)

if not _IS_SCRAPER:
    _ensure_chat_table()
