# utils/crypto_utils.py

"""
Encryption helpers.
"""

import base64
import binascii
import hashlib
import json

from Crypto.Cipher import AES

from app.core.config import settings



def hexa_to_base64(hex_string):
    bytes_data = binascii.unhexlify(hex_string)

    return base64.b64encode(bytes_data).decode()



def api_encrypt(value):
    hasdkey = hashlib.sha256(
        settings.SHA_SECRET_KEY.encode(),
    ).hexdigest()[:32]

    hasdiv = hashlib.sha256(
        settings.SHA_SECRET_IV.encode(),
    ).hexdigest()[:32]

    key = binascii.unhexlify(hasdkey)
    iv = binascii.unhexlify(hasdiv)

    cipher = AES.new(key, AES.MODE_CBC, iv)

    value_json = json.dumps(value)

    value_padded = value_json + (
        16 - len(value_json) % 16
    ) * chr(16 - len(value_json) % 16)

    encrypted = cipher.encrypt(value_padded.encode())

    return hexa_to_base64(
        binascii.hexlify(encrypted).decode(),
    )