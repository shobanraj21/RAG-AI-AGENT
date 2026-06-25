import json
import os
import uuid
import psycopg2
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

load_dotenv()

from faq import invoke_faq_agent

app = FastAPI()

PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = os.getenv("PG_PORT", "5433")
PG_DB = os.getenv("PG_DB", "faq_rag")
PG_USER = os.getenv("PG_USER", "postgres")
PG_PASSWORD = os.getenv("PG_PASSWORD", "12345")


def get_conn():
    return psycopg2.connect(host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASSWORD)


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS chat_sessions (
            session_id     TEXT PRIMARY KEY,
            name           TEXT DEFAULT 'New Chat',
            history        JSONB DEFAULT '[]',
            active_product TEXT DEFAULT NULL,
            created_at     TIMESTAMP DEFAULT NOW()
        );
    """)
    cur.execute("""
        DO $$ BEGIN
            ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS history JSONB DEFAULT '[]';
        EXCEPTION WHEN others THEN NULL;
        END $$;
    """)
    cur.execute("""
        DO $$ BEGIN
            ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS active_product TEXT DEFAULT NULL;
        EXCEPTION WHEN others THEN NULL;
        END $$;
    """)
    conn.commit()
    cur.close()
    conn.close()


def _load_history(session_id: str) -> list:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT history FROM chat_sessions WHERE session_id = %s", (session_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row and row[0] else []


class ChatRequest(BaseModel):
    query: str
    session_id: str
    history: list = []


@app.get("/", response_class=HTMLResponse)
def index():
    with open("../templates/index.html", "r", encoding="utf-8") as f:
        return f.read()


@app.get("/api/sessions")
def list_sessions():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT session_id, name, created_at FROM chat_sessions ORDER BY created_at DESC")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [{
        "session_id": row[0],
        "name": row[1],
        "created_at": row[2].strftime("%d %b, %H:%M"),
    } for row in rows]


@app.post("/api/session")
def create_session():
    session_id = str(uuid.uuid4())
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO chat_sessions (session_id, name, history) VALUES (%s, %s, %s)",
        (session_id, "New Chat", json.dumps([])),
    )
    conn.commit()
    cur.close()
    conn.close()
    return {"session_id": session_id, "name": "New Chat"}


@app.delete("/api/session/{session_id}")
def delete_session(session_id: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM chat_sessions WHERE session_id = %s", (session_id,))
    conn.commit()
    cur.close()
    conn.close()
    return {"status": "deleted"}


@app.get("/api/history/{session_id}")
def get_history(session_id: str):
    history = _load_history(session_id)
    return [{"role": item["role"], "content": item.get("content", item.get("message", ""))} for item in history]


@app.post("/api/chat")
async def chat(req: ChatRequest):
    query = req.query.strip()
    session_id = req.session_id.strip()

    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    history = _load_history(session_id)
    llm_history = history[-6:]
    result = await invoke_faq_agent(query, session_id=session_id, history=llm_history)
    answer = result.get("result_text", "No response")

    history.append({"role": "user", "content": query})
    history.append({"role": "assistant", "content": answer})

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT name FROM chat_sessions WHERE session_id = %s", (session_id,))
    row = cur.fetchone()
    name = row[0] if row else "New Chat"
    if name == "New Chat":
        name = query[:40] + ("..." if len(query) > 40 else "")
        cur.execute("UPDATE chat_sessions SET name = %s WHERE session_id = %s", (name, session_id))

    cur.execute(
        "UPDATE chat_sessions SET history = %s WHERE session_id = %s",
        (json.dumps(history), session_id),
    )
    conn.commit()
    cur.close()
    conn.close()

    return {
        "status": "success",
        "response": answer,
        "status_code": result.get("status_code", 200),
        "session_id": session_id,
    }


_scraper_running = False

@app.post("/api/scraper/run")
async def trigger_scraper(background_tasks: BackgroundTasks):
    global _scraper_running
    if _scraper_running:
        return {"status": "already_running", "message": "Scraper is already running."}
    from scraper import run, request_stop, reset_stop
    def _run():
        global _scraper_running
        _scraper_running = True
        reset_stop()
        try:
            run()
        finally:
            _scraper_running = False
    background_tasks.add_task(_run)
    return {"status": "started", "message": "Scraper triggered. Check logs for progress."}


@app.post("/api/scraper/stop")
async def stop_scraper():
    global _scraper_running
    if not _scraper_running:
        return {"status": "not_running", "message": "Scraper is not running."}
    from scraper import request_stop
    request_stop()
    return {"status": "stopping", "message": "Stop signal sent. Scraper will stop after current chunk."}


@app.get("/api/scraper/status")
async def scraper_status():
    return {"running": _scraper_running}


if __name__ == "__main__":
    import uvicorn
    init_db()
    uvicorn.run("ui:app", host="0.0.0.0", port=5000, reload=False)
