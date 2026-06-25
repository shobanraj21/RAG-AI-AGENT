# app/services/auth_service.py

from fastapi import HTTPException, status
from fastapi.security import HTTPBasicCredentials

from app.core.config import settings
from app.core.security import sha256_encoder


async def validate_credentials(
    credentials: HTTPBasicCredentials,
    logger,
):
    """
    Validate incoming basic auth credentials.
    Raises HTTPException on failure.
    """

    try:
        enc_user_name, enc_pswd = sha256_encoder(
            logger,
            settings.AUTH_USER_NAME,
            settings.AUTH_PSWD,
        )

        if (
            credentials.username != enc_user_name
            or credentials.password != enc_pswd
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authorization issue",
            )

        return True

    except HTTPException:
        raise

    except Exception as e:
        logger.exception(f"Error validating credentials: {e}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication validation failed",
        )