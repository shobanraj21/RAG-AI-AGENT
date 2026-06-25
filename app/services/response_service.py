# app/services/response_service.py

import json

from fastapi.responses import JSONResponse

#from app.schemas.pydantic_schema import AgentResponse


def build_final_response(
    *,
    response,
    detected_mobile_no,
    status_code,
    res_type,
    retry_flag,
    loan_api_failure_flag,
):
    """
    Standard response normalization layer.

    Mirrors the raw file's final response-building block:
    - Stamps type, retry_flag, loan_api_failure_flag onto response dict.
    - Handles 422 agreement-number error message rewrite.
    - Converts intent_dict keys to strings.
    - Wraps everything in the standard envelope.
    """

    response["type"] = res_type
    response["retry_flag"] = retry_flag
    response["loan_api_failure_flag"] = loan_api_failure_flag

    # 422 agreement-number field rewrite (mirrors raw file)
    try:
        if (
            response is not None
            and "response" in response
            and isinstance(response["response"], str)
            and int(status_code) == 422
        ):
            response_message = json.loads(response["response"])["message"]

            if response_message == "The agfreement number field is required.":
                response = {
                    "response": (
                        "Please enter your query along with the agreement number."
                    ),
                    "type": "string",
                }
    except Exception:
        pass

    # Convert intent_dict keys to strings (mirrors raw file guard)
    if isinstance(response, dict) and "intent_dict" in response:
        response["intent_dict"] = {
            str(k): v for k, v in response["intent_dict"].items()
        }

    final_response = {
        "message": response,
        "detected_mobile_no": detected_mobile_no,
        "response_code": status_code,
    }

    return final_response