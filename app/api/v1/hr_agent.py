from fastapi import APIRouter, Depends
from fastapi.security import HTTPBasicCredentials

from app.api.deps import verify_auth
from app.schemas.pydantic_schema import HRAgentRequest, HRAgentResponse
from app.services.hr_agent_service import process_hr_agent_request

router = APIRouter()

@router.post("/query", response_model=HRAgentResponse)
async def query_agent(
    input_request: HRAgentRequest,
    credentials: HTTPBasicCredentials = Depends(verify_auth),
):
    return await process_hr_agent_request(input_request, credentials)
