from pydantic import BaseModel
from typing import Optional, Union

class AgentRequest(BaseModel):
    query_input: str
    session_id: str
    mobile_no: str
    user_text_flag: Optional[int] = 0
    show_more_req_flag: Optional[str] = "0"
    query_no: Optional[str] = "0"
    lead_capture: Optional[str] = "0"
    verification_code: Optional[str] = ""
    otp_verified: Optional[str] = "0"
    user_request: Optional[str] = ""
    show_all_loans: str = "0"
    selected_lang: str = "en"
    
class HRAgentRequest(BaseModel):
    user_question: str
    session_id: str
    employee_id: str
    mobile_number: str
    zone: str

# Agent response: the inner "message" object
class AgentMessage(BaseModel):
    response: Union[str, dict, list, None] = None
    type: Optional[str] = "string"
    retry_flag: Optional[int] = 0
    loan_api_failure_flag: Optional[int] = 0
    counter_flag_agg: Optional[int] = 0

    # greeting flow
    intent_dict: Optional[dict[str, str]] = None

    # OTP flow
    otp_verified: Optional[str] = None
    flow_type: Optional[str] = None

    # My Loans flow
    sr_flag: Optional[int] = None
    sr_text: Optional[str] = None
    loan_count: Optional[int] = None
    apply_loan_flag: Optional[int] = None

    # Apply Loan flow
    cust_details_flag: Optional[int] = None
    cust_api_status: Optional[int] = None
    product_type: Optional[str] = None
    product_type_flag: Optional[int] = None

    model_config = {"extra": "allow"}


# Agent response: the outer envelope
class AgentResponse(BaseModel):
    message: AgentMessage
    detected_mobile_no: str = ""
    response_code: int = 200


# HR Agent: inner response object from Bedrock
class HRAgentResult(BaseModel):
    status_code: int
    result_text: str


# HR Agent: outer envelope
class HRAgentResponse(BaseModel):
    success: bool
    response: HRAgentResult