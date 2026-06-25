import re
import os
from app.core.config import settings
from app.core.constants import APPLY_KEYWORDS, MY_LOAN_KEYWORDS
from app.core.logging import *
from app.db.session import *

# Bedrock runtime client which is reused across all agent calls
agent_runtime_client = create_agent_runtime(logger)

def _is_mock():
    return str(os.getenv("MOCK_MODE", "false")).strip().lower() in ("1", "true", "yes", "on")

# Setting logger 
def get_agent_logger():
    dt, timestamp = create_log_name()
    log_file_name = settings.LOGGER_PATH + f"agent_v1_{dt}.log"
    return setup_logger("agent_logger", log_file_name)

'''
def is_personnel_query(user_query):
    """Check if the query is asking about personnel/individuals"""
    # Restricted personnel related keywords
    personnel_keywords = [
        'chairman', 'ceo', 'cfo', 'managing director', 'board member', 
        'director', 'executive', 'president', 'vice president', 'manager',
        'who is', 'name of', 'current', 'new', 'appointed',"md","who's this"
    ]
    query_lower = user_query.lower()
    # Keyword filtering before hitting the KB
    for keyword in personnel_keywords:
        if keyword in query_lower:
            return True
    # Regex based detection which can be used for role based questions
    personnel_patterns = [
        r'\bwho\s+is\s+the\b',
        r'\bname\s+of\s+the\b',
        r'\bcurrent\s+\w+\s+of\b',
        r'\bmanaging\s+director\b',
        r'\bboard\s+of\s+directors\b'
    ]
    for pattern in personnel_patterns:
        if re.search(pattern, query_lower):
            return True  
    return False

# Alternate FAQ path using (retrieve_and_generate) with a custom prompt

def call_cholabot_with_custom_prompt(user_query, session_id=None):
    dt, timestamp = create_log_name()
    log_file_name = LOGGER_PATH + "agent_v1_" + str(dt) + ".log"
    # logger for KB interactions
    logger = setup_logger('agent_logger', log_file_name)
    # check for personnel query before invoking into Bedrock
    if is_personnel_query(user_query):
        logger.info(f"Personnel query detected and blocked: {user_query}")
        return "Sorry, I do not have any information related to individual personnel at the company."
    
    # Template for prompt to inject into Bedrock generation config
    custom_prompt = f"""You are **Cholabot**, the official AI assistant for Cholamandalam Investment and Finance Company Limited.

    RESPONSE GUIDELINES:
    - Use **bold text** for key information, important figures, and product names
    - Present numerical data clearly with time periods for financial information
    - Keep responses concise and direct
    - For unavailable information, respond with: "Sorry, I do not have any information about that topic."
    - If the user asks for personnel information return "Sorry, I do not have any information related to individual personnel at the company."
    
    User Question: {user_query}
    
    Based on the search results below, provide a direct answer:
    $search_results$"""

    try:
        # Bedrock RetrieveAndGenerate KB call
        response = agent_runtime_client.retrieve_and_generate(
            input={
                'text': user_query
            },
            retrieveAndGenerateConfiguration={
                'type': 'KNOWLEDGE_BASE',
                'knowledgeBaseConfiguration': {
                    'knowledgeBaseId': KNOWLEDGE_BASE_ID,
                    'modelArn': MODEL_ARN,
                    'generationConfiguration': {
                        'promptTemplate': {
                            'textPromptTemplate': custom_prompt
                        }
                    }
                }
            }
        )
        logger.info(f"response from faq_kb: {response}")
        logger.info(f"response returned from the function call_cholabot_with_custom_prompt: {response['output']['text']}")
        return response['output']['text']
    except Exception as e:
        logger.exception(f"Error calling Bedrock: {str(e)}")
        result = {
            "status_code": 300,
            "result_text": "We ran into a technical issue!! Please try again later."
        }
        return result
        '''


def invoke_bedrock_agent(
    query,
    session_id,
    agent_id,
    alias_id,
    logger
):
    try:

        params = {
            "agentAliasId": alias_id,
            "agentId": agent_id,
            "sessionId": session_id,
            "inputText": query,
            "enableTrace": True
        }

        response = agent_runtime_client.invoke_agent(**params)
        logger.info(f"raw response : {response}")
        
        for event in response.get("completion", []):
            if "chunk" in event:
                result_bytes = event["chunk"]["bytes"]
                result_text = result_bytes.decode("utf-8")
                final_response = {
                    "status_code": 200,
                    "result_text": result_text
                }
                logger.info(f"Agent response : {final_response}")
                return final_response
        return {
            "status_code": 204,
            "result_text": "No response generated."
        }
        
    except Exception as e:
        logger.exception(f"Error invoking agent : {e}")
        return {
            "status_code": 300,
            "result_text": "We ran into a technical issue!! Please try again later."
        }
        


def invoke_loan_agent(query, session_id):
    # local mock responses 
    if _is_mock():
        query_lower = query.lower()
        if "home" in query_lower:
            return {"status_code": 200, "result_text": "hl_apply_loan"}
        elif "vehicle" in query_lower or "car" in query_lower:
            return {"status_code": 200, "result_text": "vf_apply_loan"}
        elif "gold" in query_lower:
            return {"status_code": 200, "result_text": "gl_apply_loan"}
        elif "personal" in query_lower:
            return {"status_code": 200, "result_text": "csel_apply_loan"}
        elif "business" in query_lower:
            return {"status_code": 200, "result_text": "sbpl_apply_loan"}
        return {"status_code": 200, "result_text": "apply_loan_"}

    logger = get_agent_logger()

    return invoke_bedrock_agent(
        query=query,
        session_id=session_id,
        agent_id=settings.AGENT_ID_LOAN_AGENT,
        alias_id=settings.ALIAS_ID_LOAN_AGENT,
        logger=logger
    )


def invoke_sr_agent(query, session_id):
    
    # Mock SR intent mapping
    if _is_mock():
        query_lower = query.lower()
        if "summary" in query_lower:
            return {"status_code": 200, "result_text": "loan_summary_"}
        elif "welcome" in query_lower:
            return {"status_code": 200, "result_text": "welcome_letter_"}
        elif "payment history" in query_lower or "payment details" in query_lower:
            return {"status_code": 200, "result_text": "payment_history_"}
        elif "repayment" in query_lower or "schedule" in query_lower:
            return {"status_code": 200, "result_text": "payment_schedule_"}
        elif "mini" in query_lower or "soa" in query_lower:
            return {"status_code": 200, "result_text": "mini_soa_"}
        elif "interest" in query_lower:
            return {"status_code": 200, "result_text": "interest_certificate_"}
        elif "pdd" in query_lower:
            return {"status_code": 200, "result_text": "pdd_status_"}
        elif "disbursement" in query_lower:
            return {"status_code": 200, "result_text": "disbursement_details_"}
        return {"status_code": 200, "result_text": "loan_details_"}

    logger = get_agent_logger()

    return invoke_bedrock_agent(
        query=query,
        session_id=session_id,
        agent_id=settings.AGENT_ID_SR_AGENT,
        alias_id=settings.ALIAS_ID_SR_AGENT,
        logger=logger
    )


def invoke_faq_agent(query, session_id):

    if _is_mock():
        return {
            "status_code": 200,
            "result_text": (
                "Cholamandalam Investment and Finance Company Limited (Chola) is a leading NBFC in India offering vehicle finance, home loans, SME loans, and other financial products."
            )
        }

    logger = get_agent_logger()

    return invoke_bedrock_agent(
        query=query,
        session_id=session_id,
        agent_id=settings.AGENT_ID_FAQ_AGENT,
        alias_id=settings.ALIAS_ID_FAQ_AGENT,
        logger=logger
    )


def invoke_common_agent(query, session_id):

    # Entry-point classifier mock for routing top-level intents
    if _is_mock():
        query_lower = query.lower()
        if any(k in query_lower for k in APPLY_KEYWORDS):
            return {"status_code": 200, "result_text": "Apply Loan"}
        elif any(k in query_lower for k in MY_LOAN_KEYWORDS):
            return {"status_code": 200, "result_text": "My Loans"}
        return {"status_code": 200, "result_text": "About Chola"}

    logger = get_agent_logger()

    return invoke_bedrock_agent(
        query=query,
        session_id=session_id,
        agent_id=settings.AGENT_ID_COMMON_AGENT,
        alias_id=settings.ALIAS_ID_COMMON_AGENT,
        logger=logger
    )
