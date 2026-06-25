# app/services/spam_service.py

from datetime import datetime, timedelta


async def fetch_spam(agent_col, query, logger):
    """
    Fetch recent matching conversations for spam detection.
    """

    try:
        return await agent_col.find(query).to_list(None)

    except Exception as e:
        logger.exception(f"Exception while reading mongo: {e}")
        return []


async def check_spam(
    agent_col,
    query_input: str,
    timestamp: str,
    logger,
    date_format: str = "%Y-%m-%d %H:%M:%S",
):
    """
    Check whether the same query is repeatedly spammed
    within the last 2 minutes.

    Returns (is_spam: bool, spam_records: list).
    """

    try:
        if agent_col is None:
            return False, []

        curr_time = datetime.strptime(timestamp, date_format)
        condition_timestamp = curr_time - timedelta(minutes=2)

        curr_time_str = curr_time.strftime(date_format)
        condition_timestamp_str = condition_timestamp.strftime(date_format)

        pymongo_query = {
            "created_at": {
                "$gt": condition_timestamp_str,
                "$lt": curr_time_str,
            },
            "user_input": query_input,
        }

        spam_records = await fetch_spam(
            agent_col,
            pymongo_query,
            logger,
        )

        logger.info("SPAM CHECK.........")
        logger.info(f"curr_time : {curr_time_str}")
        logger.info(f"condition_timestamp : {condition_timestamp_str}")
        logger.info(f"is_spammed : {spam_records}")

        is_spam = len(spam_records) > 10

        return is_spam, spam_records

    except Exception as e:
        logger.exception(f"Error during spam check: {e}")
        return False, []