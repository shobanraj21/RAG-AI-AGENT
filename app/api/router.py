from fastapi import APIRouter
from app.api.v1.agent import router as agent_router
from app.api.v1.hr_agent import router as hr_router

api_router = APIRouter()
router = api_router

api_router.include_router(agent_router, prefix="/v1", tags=["Agent"])
api_router.include_router(hr_router, tags=["HR Agent"])
