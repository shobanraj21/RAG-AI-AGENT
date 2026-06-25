# app/services/faq_service.py

import os
import sys
import importlib
from app.services.agent_runtime import invoke_faq_agent


async def handle_faq_flow(
    query_input,
    session_id,
    logger,
):
    retry_flag = 0

    # Route to Gemini RAG pipeline (app/faq/) or Bedrock agent based on FAQ_PROVIDER env var.
    # FAQ_PROVIDER=gemini -> pgvector retrieval + Gemini LLM (history auto-fetched inside agent.py)
    # FAQ_PROVIDER=bedrock (default) -> AWS Bedrock agent
    faq_provider = os.getenv("FAQ_PROVIDER", "bedrock").strip().lower()

    if faq_provider == "gemini":
        faq_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "faq"))
        if faq_path not in sys.path:
            sys.path.insert(0, faq_path)
        gemini_agent = importlib.import_module("agent")
        llm_response = await gemini_agent.invoke_faq_agent(query=query_input, session_id=session_id)
    else:
        llm_response = invoke_faq_agent(query_input, session_id)

    logger.info(f"faq response : {llm_response}")
    logger.info(f"faq response type : {type(llm_response)}")

    if llm_response.get("status_code") == 300:
        retry_flag = 1

    response = llm_response.get("result_text", "")
    res_type = "json" if not isinstance(response, str) else "string"

    return {
        "response": response,
        "res_type": res_type,
        "retry_flag": retry_flag,
    }