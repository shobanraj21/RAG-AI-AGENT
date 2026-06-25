# app/services/orchestrator.py

from app.services.faq_service import handle_faq_flow
from app.services.lead_service import (
    handle_apply_loan_flow,
    handle_lead_capture_flow,
)
from app.services.loan_service import handle_my_loans_flow
from app.services.agent_runtime import invoke_common_agent


async def orchestrate_request(
    *,
    query_input,
    session_id,
    mobile_no,
    user_request,
    lead_capture,
    input_request,
    logger,
    language_data,
    agent_col,
    lead_agent_col,
    crm_col,
    cust_col,
    redis_client,
    redis_key_name,
    timestamp,
    detected_mobile_no,
    agreement_number,
    otp_verified,
    verification_code,
    show_more_req_flag,
    user_text_flag,
    show_all_loans,
):
    """
    Main orchestration layer — decides which business flow to execute.

    All parameters that the raw file passed inline are threaded through
    here so each service function has what it needs without reaching
    back into input_request directly.
    """

    retry_flag = 0

    # ------------------------------------------------------------------
    # Intent detection (if not already provided by the caller)
    # ------------------------------------------------------------------
    if not user_request:
        llm_response = invoke_common_agent(query_input, session_id)
        logger.info(f"intent detection response: {llm_response}")

        user_request = llm_response["result_text"]

        if llm_response.get("status_code") == 300:
            retry_flag = 1

    logger.info(f"user_request: {user_request}")

    # ==================================================================
    # FAQ FLOW — "About Chola"
    # ==================================================================
    if user_request == "About Chola":

        logger.info("FAQ............")

        # handle_faq_flow returns a dict — NOT a tuple
        faq_result = await handle_faq_flow(
            query_input=query_input,
            session_id=session_id,
            logger=logger,
        )

        return {
            "response": {"response": faq_result["response"]},
            "res_type": faq_result["res_type"],
            "retry_flag": faq_result["retry_flag"] or retry_flag,
            "loan_api_failure_flag": 0,
            "status_code": 200,
            "detected_mobile_no": detected_mobile_no,
        }

    # ==================================================================
    # APPLY LOAN FLOW
    # ==================================================================
    elif user_request == "Apply Loan":

        logger.info("APPLY LOAN............")

        if int(lead_capture) == 1:

            # Lead capture branch
            response, res_type, status_code = await handle_lead_capture_flow(
                query_input=query_input,
                session_id=session_id,
                mobile_no=mobile_no,
                logger=logger,
                lead_agent_col=lead_agent_col,
                crm_col=crm_col,
                cust_col=cust_col,
                detected_mobile_no=detected_mobile_no,
                timestamp=timestamp,
            )

            return {
                "response": {"response": response},
                "res_type": res_type,
                "retry_flag": retry_flag,
                "loan_api_failure_flag": 0,
                "status_code": status_code,
                "detected_mobile_no": detected_mobile_no,
            }

        # Non-lead-capture: loan agent + verification
        response, res_type = await handle_apply_loan_flow(
            query_input=query_input,
            session_id=session_id,
            mobile_no=mobile_no,
            logger=logger,
            cust_col=cust_col,
            timestamp=timestamp,
            language_data=language_data,
        )

        # Invalid-entity early-return check
        # handle_apply_loan_flow already returns a response dict;
        # if it contains loan_api_failure_flag the flow failed.
        status_code = 207 if response.get("loan_api_failure_flag") == 0 and res_type == "string" and "apply_loan_flag" not in response else 200

        return {
            "response": response,
            "res_type": res_type,
            "retry_flag": retry_flag,
            "loan_api_failure_flag": response.get("loan_api_failure_flag", 0),
            "status_code": status_code,
            "detected_mobile_no": detected_mobile_no,
        }

    # ==================================================================
    # MY LOANS FLOW
    # ==================================================================
    elif user_request == "My Loans":

        logger.info("MY LOANS............")

        result = await handle_my_loans_flow(
            input_request=input_request,
            query_input=query_input,
            session_id=session_id,
            mobile_no=mobile_no,
            detected_mobile_no=detected_mobile_no,
            agreement_number=agreement_number,
            logger=logger,
            language_data=language_data,
            redis_client=redis_client,
            redis_key_name=redis_key_name,
            show_all_loans=show_all_loans,
        )

        result["retry_flag"] = result.get("retry_flag", 0) or retry_flag
        return result

    # ==================================================================
    # FALLBACK
    # ==================================================================
    return {
        "response": {
            "response": language_data.get(
                "error_message",
                "Apologies, but I was unable to understand your request. "
                "Kindly rephrase it for better assistance.",
            ),
        },
        "res_type": "string",
        "retry_flag": retry_flag,
        "loan_api_failure_flag": 0,
        "status_code": 207,
        "detected_mobile_no": detected_mobile_no,
    }