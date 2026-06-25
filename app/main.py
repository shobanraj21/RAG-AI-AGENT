from fastapi import FastAPI
from app.api.router import router as api_v1_router
from app.middleware.cors import add_cors_middleware
from app.core.exceptions import add_exception_handlers
# from app.core.logging import setup_logging

app = FastAPI()

# setup_logging()
add_cors_middleware(app)
add_exception_handlers(app)

app.include_router(api_v1_router)

@app.get("/")
def root():
    return {"message": "Agent is running"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=80)
