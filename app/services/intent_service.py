# app/services/intent_service.py

from app.services.agent_runtime import (
    invoke_common_agent,
    invoke_loan_agent,
    invoke_sr_agent,
)
from app.utils.text_utils import (
    check_agent_response,
    extract_after_dot,
    find_intent,
    user_text_check,
)


async def detect_user_intent(
    query_input,
    session_id,
    logger,
):
    """
    Detects top-level intent via the common agent.

    Returns:
        {
            "user_request": str,
            "retry_flag": 0 | 1,
        }
    """

    retry_flag = 0

    llm_response = invoke_common_agent(query_input, session_id)

    logger.info(f"detect agent llm response: {llm_response}")

    if llm_response.get("status_code") == 300:
        retry_flag = 1

    return {
        "user_request": llm_response.get("result_text", ""),
        "retry_flag": retry_flag,
    }


async def detect_apply_loan_intent(
    query_input,
    session_id,
    logger,
    valid_intents,
):
    """
    Detects apply-loan intent/entity.

    Returns:
        {
            "entity": str,
            "invalid_entity": bool,
            "retry_flag": 0 | 1,
            "llm_response": dict,
        }
    """

    retry_flag = 0

    llm_response = invoke_loan_agent(query_input, session_id)

    logger.info(f"loan agent response : {llm_response}")

    if llm_response.get("status_code") == 300:
        retry_flag = 1

    entity = llm_response["result_text"].lower()
    entity = find_intent(logger, entity)

    invalid_entity = check_agent_response(logger, valid_intents, entity)

    return {
        "entity": entity,
        "invalid_entity": invalid_entity,
        "retry_flag": retry_flag,
        "llm_response": llm_response,
    }


async def detect_sr_intent(
    query_input,
    session_id,
    logger,
    sr_intent_list,
    entity_super_list,
    phrase="i will ask",
):
    """
    Detect service request intent.

    Returns:
        {
            "entity": str,
            "sr_flag": int,
            "invalid_entity": bool,
            "retry_flag": 0 | 1,
            "llm_response": dict,
        }
    """

    retry_flag = 0

    llm_response = invoke_sr_agent(query_input, session_id)

    logger.info(f"sr agent response : {llm_response}")

    if llm_response.get("status_code") == 300:
        retry_flag = 1

    entity_ = llm_response["result_text"].lower()

    entity = extract_after_dot(entity_, phrase, logger)

    logger.info(f"entity received from llm : {entity_}")

    sr_flag, entity = user_text_check(entity, logger)

    invalid_entity = check_agent_response(logger, sr_intent_list, entity_)

    for item in entity_super_list:
        if item in entity:
            entity = item

    return {
        "entity": entity,
        "sr_flag": sr_flag,
        "invalid_entity": invalid_entity,
        "retry_flag": retry_flag,
        "llm_response": llm_response,
    }