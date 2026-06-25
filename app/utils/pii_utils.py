"""
PII detection and scrubbing utilities.
"""
import re
from app.core.constants import REPLACE_PII_TEXT


def aadhar_validation(query: str, logger) -> str:
    try:
        aadhar_num = ""
        pattern = r'\b(?:[2-9]\d{3}\s\d{4}\s\d{4}|[2-9]\d{11})\b'
        matches = re.findall(pattern, query)
        logger.info(f"aadhar number regex result: {matches}")
        if matches:
            aadhar_num = matches[0]
            logger.info(f"aadhar number: {aadhar_num}")
        return aadhar_num
    except Exception as e:
        logger.exception(e)
        return ""


def pan_number_validation(query: str, logger) -> str:
    try:
        pan_num = ""
        pattern = r'\b[A-Z]{3}[ABCFGHLJPT][A-Z][0-9]{4}[A-Z]\b'
        matches = re.findall(pattern, query, re.IGNORECASE)
        logger.info(f"pan number validation regex result: {matches}")
        if matches:
            pan_num = matches[0]
            logger.info(f"pan number: {pan_num}")
        return pan_num
    except Exception as e:
        logger.exception(e)
        return ""


def driving_license_validation(query: str, logger) -> str:
    try:
        dl_num = ""
        pattern = r'\b[A-Z]{2}-\d{2}-\d{4}-\d{7}\b'
        matches = re.findall(pattern, query, re.IGNORECASE)
        logger.info(f"driving license number validation regex result: {matches}")
        if matches:
            dl_num = matches[0]
            logger.info(f"driving license number: {dl_num}")
        return dl_num
    except Exception as e:
        logger.exception(e)
        return ""


def ration_number_validation(query: str, logger) -> str:
    try:
        ration_num = ""
        pattern = r'\b\d{10}\b'
        matches = re.findall(pattern, query)
        logger.info(f"ration number validation regex result: {matches}")
        if matches:
            ration_num = matches[0]
            logger.info(f"ration number: {ration_num}")
        return ration_num
    except Exception as e:
        logger.exception(e)
        return ""


def passport_validation(query: str, logger) -> str:
    try:
        passport_num = ""
        pattern = r'\b[A-Z][0-9]{7}\b'
        matches = re.findall(pattern, query, re.IGNORECASE)
        logger.info(f"passport number validation regex result: {matches}")
        if matches:
            passport_num = matches[0]
            logger.info(f"passport number: {passport_num}")
        return passport_num
    except Exception as e:
        logger.exception(e)
        return ""


def voter_id_verification(query: str, logger) -> str:
    try:
        voter_id = ""
        pattern = r'\b[A-Z][0-9]{7}\b'
        matches = re.findall(pattern, query, re.IGNORECASE)
        logger.info(f"voter id validation regex result: {matches}")
        if matches:
            voter_id = matches[0]
            logger.info(f"voter id: {voter_id}")
        return voter_id
    except Exception as e:
        logger.exception(e)
        return ""


def strip_pii(query_input: str, logger) -> str:
    """
    Remove all detected PII tokens from *query_input* and return the
    sanitised string. Mirrors the PII-stripping block in app.py /v1/agent.
    """
    query_input = query_input.replace(aadhar_validation(query_input, logger), "")
    query_input = query_input.replace(pan_number_validation(query_input, logger), "")
    query_input = query_input.replace(driving_license_validation(query_input, logger), "")
    query_input = query_input.replace(ration_number_validation(query_input, logger), "")
    query_input = query_input.replace(passport_validation(query_input, logger), "")
    query_input = query_input.replace(voter_id_verification(query_input, logger), "")
    for token in REPLACE_PII_TEXT:
        if token in query_input:
            query_input = query_input.replace(token, "")
    logger.info(f"modified query after replacing pii data: {query_input}")
    return query_input

