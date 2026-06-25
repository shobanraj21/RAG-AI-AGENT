# utils/otp_utils.py
"""
OTP related APIs.
"""

import json

from datetime import datetime

from app.core.config import settings
from app.core.http_client import async_client
from app.utils.crypto_utils import api_encrypt
from app.utils.network_utils import get_local_ip_address



async def otp_generation(mobile_no, logger):
    """
    Generate OTP.
    """

    value = {
        "date": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "sha_key": settings.SHA_KEY,
        "mobile_number": mobile_no,
        "ip_address": get_local_ip_address(logger),
    }

    auth_token = api_encrypt(value)

    payload = json.dumps({
        "mobile_number": mobile_no,
        "validate_user": False,
    })

    headers = {
        'Content-Type': 'application/json',
        'x-source-type': 'Web',
        'Authorization': auth_token,
    }

    response = await async_client.post(
        settings.OTP_GENERATE_URL,
        headers=headers,
        content=payload,
    )

    return response.json()



async def otp_verification(mobile_no, verification_code, logger):
    """
    Verify OTP.
    """

    payload = json.dumps({
        "mobile_number": mobile_no,
        "verification_code": verification_code,
    })

    headers = {
        'Content-Type': 'application/json',
    }

    response = await async_client.post(
        settings.OTP_VERIFY_URL,
        headers=headers,
        content=payload,
    )

    return response.json()
