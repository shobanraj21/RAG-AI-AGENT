from fastapi import APIRouter, Depends
from fastapi.security import HTTPBasicCredentials

from app.api.deps import verify_auth
from app.schemas.pydantic_schema import AgentRequest
from app.services.agent_service import process_agent_request

router = APIRouter()


@router.post("/agent")
async def agent_v1(
    input_request: AgentRequest,
    credentials: HTTPBasicCredentials = Depends(verify_auth)
):
    return await process_agent_request(input_request, credentials)
