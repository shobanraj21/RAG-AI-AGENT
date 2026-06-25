# app/services/otp_service.py

from app.core.config import settings
from app.utils.otp_utils import (
    otp_generation,
    otp_verification,
)


async def generate_otp_service(
    mobile_no: str,
    logger,
):
    """
    Generate OTP for customer verification.
    """

    try:
        if settings.APP_ENV == "stage":
            logger.info("Stage env - OTP generation skipped")
            return {
                "success": True,
                "message": "OTP generation skipped in stage environment",
            }

        logger.info("Prod env - OTP generate")
        response = await otp_generation(mobile_no, logger)
        return response

    except Exception as e:
        logger.exception(f"Error generating OTP: {e}")
        return {
            "success": False,
            "message": "OTP generation failed",
        }


async def verify_otp_service(
    mobile_no: str,
    verification_code: str,
    logger,
):
    """
    Verify customer OTP.

    The hardcoded "1234" bypass mirrors the raw file's
    stage/testing shortcut.
    """
    logger.info(settings.APP_ENV)
    try:
        if settings.APP_ENV == "stage":
            logger.info("Stage env - OTP verification skipped")
            otp_verify_response = {
                "success": True,
                "message": "OTP verification skipped in stage environment",
            }

        else:
            logger.info("Prod env - OTP verify")
            otp_verify_response = await otp_verification(
                mobile_no, verification_code, logger
            )

            if otp_verify_response is None:
                otp_verify_response = {
                    "success": False,
                    "message": "OTP verification service unavailable",
                }

        # Hardcoded bypass for testing (mirrors raw file)
        if verification_code == "1234":
            otp_verify_response["success"] = True

        return otp_verify_response

    except Exception as e:
        logger.exception(f"Error verifying OTP: {e}")
        return {
            "success": False,
            "message": "OTP verification failed",
        }