from fastapi import Depends, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app.core.config import settings
from app.core.logging import logger
from app.core.security import sha256_encoder

security = HTTPBasic()


def verify_auth(credentials: HTTPBasicCredentials = Depends(security)) -> HTTPBasicCredentials:
    enc_user_name, enc_pswd = sha256_encoder(logger, settings.AUTH_USER_NAME, settings.AUTH_PSWD)
    if credentials.username != enc_user_name or credentials.password != enc_pswd:
        raise HTTPException(status_code=401, detail="Authorization issue")
    return credentials
