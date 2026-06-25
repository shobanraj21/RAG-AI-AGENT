# app/services/lead_service.py

import json
import re
import secrets

from app.core.config import settings
from app.db.session import (
    async_crm_log_mongo_insertion,
    async_lead_log_mongo_insertion,
    get_cust_details_from_mongo,
    send_to_lead_api,
)
from app.utils.text_utils import convert_to_dict_if_possible, loan_verification
from app.services.agent_runtime import invoke_loan_agent
from app.services.loan_service import loan_against_mobilenumber


# ---------------------------------------------------------------------------
# Product type mapping (raw file's inline if/elif chain, extracted)
# ---------------------------------------------------------------------------

PRODUCT_TYPE_MAP = {
    "vehicle": ("vf", "Car Loans"),
    "home": ("hl", "Home Loans"),
    "gold": ("gl", "Gold Loans"),
    "personal": ("csel", "Consumer & Small Enterprise Loans"),
    "business": ("sbpl", "Secured Business & Personal Loans"),
    "property": ("lap", "Loan Against Property"),
}


def normalize_product_type(product_type: str):
    """
    Convert product text into (internal_code, display_label).
    """

    product_type = product_type.lower()

    for key, value in PRODUCT_TYPE_MAP.items():
        if key in product_type:
            return value

    return product_type, product_type


def sanitize_customer_name(customer_name: str) -> str:
    """
    Remove special characters from customer name.
    """

    customer_name = re.sub(r"[^a-zA-Z]", " ", customer_name)
    customer_name = re.sub(r"\s+", " ", customer_name).strip()
    return customer_name


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

async def build_lead_payload(query_input, mobile_no, cust_col, logger):
    """
    Parse customer lead details from query and build CRM payload dict.
    """

    customer_data = {}

    if isinstance(query_input, str):
        customer_data = convert_to_dict_if_possible(query_input, logger)[0]

    if not isinstance(customer_data, dict):
        return None

    pincode = customer_data.get("pincode")
    raw_product_type = customer_data.get("product_type", "")
    product_code, product_name = normalize_product_type(raw_product_type)

    customer_name = sanitize_customer_name(
        customer_data.get("customer_name", "")
    )

    customer_type = await get_cust_details_from_mongo(
        logger, cust_col, mobile_no
    )

    api_lead_dict = {
        "name": customer_name,
        "mobile_number": mobile_no,
        "pincode": pincode,
        "category": "lr",
        "product": product_name,
        "customer_type": customer_type,
        "source_from": "Chatbot",
    }

    return {
        "customer_name": customer_name,
        "product_code": product_code,
        "lead_payload": api_lead_dict,
    }


async def capture_lead(
    *,
    logger,
    session_id,
    mobile_no,
    query_input,
    detected_mobile_no,
    timestamp,
    lead_agent_col,
    crm_col,
    cust_col,
):
    """
    Complete lead capture workflow:
    1. Parse lead data
    2. Save lead in Mongo
    3. Send CRM API
    4. Save CRM logs
    """

    try:
        lead_data = await build_lead_payload(
            query_input=query_input,
            mobile_no=mobile_no,
            cust_col=cust_col,
            logger=logger,
        )

        if not lead_data:
            return {
                "success": False,
                "message": "Invalid lead payload",
            }

        customer_name = lead_data["customer_name"]
        product_code = lead_data["product_code"]
        api_lead_dict = lead_data["lead_payload"]

        logger.info(f"api_lead_dict: {api_lead_dict}")

        lead_id = "cholaone_agent_" + secrets.token_hex(16)

        if lead_agent_col is not None:
            lead_insert_resp = await async_lead_log_mongo_insertion(
                logger,
                session_id,
                mobile_no,
                customer_name,
                api_lead_dict["pincode"],
                lead_id,
                product_code,
                detected_mobile_no,
                timestamp,
                lead_agent_col,
            )
            logger.info(f"lead captured in mongo: {lead_insert_resp}")

        crm_response = await send_to_lead_api(
            logger,
            settings.LEAD_URL,
            settings.LEAD_URL_TOKEN,
            api_lead_dict,
            session_id,
            mobile_no,
            crm_col,
        )
        logger.info(f"suite crm lead api response : {crm_response}")

        crm_insert_resp = await async_crm_log_mongo_insertion(
            logger,
            session_id,
            mobile_no,
            api_lead_dict,
            crm_response,
            timestamp,
            crm_col,
        )
        logger.info(f"crm captured in mongo: {crm_insert_resp}")

        return {
            "success": True,
            "response": api_lead_dict,
        }

    except Exception as e:
        logger.exception(f"Exception while capturing lead: {e}")
        return {
            "success": False,
            "message": "Issue in lead capture",
        }


# ---------------------------------------------------------------------------
# Orchestrator-facing handlers
# ---------------------------------------------------------------------------

async def handle_lead_capture_flow(
    *,
    query_input,
    session_id,
    mobile_no,
    logger,
    lead_agent_col,
    crm_col,
    cust_col,
    detected_mobile_no,
    timestamp,
):
    """
    Thin wrapper called by orchestrator when lead_capture == "1".

    Returns (response_dict, res_type, status_code) to match
    how the raw file's inline lead-capture block behaved.
    """

    logger.info("LEAD CAPTURE............")

    result = await capture_lead(
        logger=logger,
        session_id=session_id,
        mobile_no=mobile_no,
        query_input=query_input,
        detected_mobile_no=detected_mobile_no,
        timestamp=timestamp,
        lead_agent_col=lead_agent_col,
        crm_col=crm_col,
        cust_col=cust_col,
    )

    if result["success"]:
        return result["response"], "json", 200
    else:
        return result.get("message", "Issue in lead capture"), "string", 210


async def handle_apply_loan_flow(
    *,
    query_input,
    session_id,
    mobile_no,
    logger,
    cust_col,
    timestamp,
    language_data,
):
    """
    Apply Loan flow when lead_capture != "1".

    Mirrors the raw file's LOAN AGENT branch:
    - Invoke loan agent to get entity
    - Call loan_against_mobilenumber for customer verification
    - Run loan_verification to build the response
    - Set apply_loan_flag = 1

    Returns (response_dict, res_type).
    """

    from app.core.constants import APPLY_LOAN_INTENT_LIST
    from app.utils.text_utils import find_intent, check_agent_response

    logger.info("LOAN AGENT .................")

    llm_response = invoke_loan_agent(query_input, session_id)

    logger.info(f"responses : {llm_response}")
    logger.info(f"response type : {type(llm_response)}")

    entity_ = llm_response["result_text"].lower()
    logger.info(f"entity received from llm : {entity_}")

    entity_ = find_intent(logger, entity_)

    invalid_entity = check_agent_response(logger, APPLY_LOAN_INTENT_LIST, entity_)

    if invalid_entity:
        response = {
            "response": language_data.get(
                "error_message",
                "Apologies, but I was unable to understand your request. "
                "Kindly rephrase it for better assistance.",
            ),
            "loan_api_failure_flag": 0,
            "type": "string",
            "retry_flag": "string",
        }
        return response, "string"

    loan_verification_details = await loan_against_mobilenumber(
        mobile_no, cust_col, logger, timestamp
    )

    loan_verification_ = loan_verification(
        loan_verification_details, llm_response["result_text"], logger
    )

    if isinstance(loan_verification_, str):
        loan_verification_ = json.loads(loan_verification_)

    loan_verification_["apply_loan_flag"] = 1

    response = loan_verification_
    res_type = "json" if not isinstance(response.get("response", ""), str) else "string"

    return response, res_type