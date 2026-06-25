import boto3
import json
import os

from app.core.config import settings
from app.core.constants import *
from app.core.logging import logger
from app.db.session import *

# Shared Bedrock runtime client reused across HR flows
agent_runtime_client = create_agent_runtime(logger)


def invoke_learning_agent(query, session_id, logger, mobile_no=None):

    logger.info(f'Query received: {query}')

    # Mock mode avoids external Bedrock dependency during local testing
    if str(os.getenv("MOCK_MODE", "false")).strip().lower() in ("1", "true", "yes", "on"):

        return {
            "status_code": 200,
            "result_text":
                f"This is a mock HR response for your query: '{query}'. "
                f"In production, this will be answered by the HR knowledge base."
        }

    # Mobile number is appended to support personalized HR lookups if required
    if mobile_no:
        query = f"{query} {mobile_no}"

    try:

        # Parameters required for Bedrock agent invocation
        params = {
            'agentAliasId': settings.ALIAS_ID_HR_AGENT,  # your learning agent alias
            'agentId': settings.AGENT_ID_HR_AGENT,            # your learning agent ID
            'sessionId': session_id,
            'inputText': query,
            'enableTrace': True
        }

        response = agent_runtime_client.invoke_agent(**params)

        logger.info(f'Raw response from learning agent: {response}')

        # Bedrock streams responses as completion chunks
        for event in response.get('completion', []):

            if 'chunk' in event:

                result_bytes = event['chunk']['bytes']
                result_text = result_bytes.decode('utf-8')

                result = {
                    "status_code": 200,
                    "result_text": result_text
                }

                logger.info(f'Learning agent response: {result}')
                print(f'Learning agent response: {result}')

                return result

    except Exception as e:

        logger.exception(f"Error invoking learning agent: {e}")

        return {
            "status_code": 300,
            "result_text":
                "We ran into a technical issue!! Please try again later."
        }


# Prompt used for fallback retrieval based on KB
prompt = """
Provide answers based exclusively on the given context. 
Use definitive statements only. 
State 'Information not available' if the answer is not in the context.

Examples:
- If asked "How can I earn points through discussions?" and context shows discussion participation, answer:
  "You earn points by participating in the Discussions section and engaging with peers through the discussion forums."

- If asked about features not in context, respond:
  "Information not available"

Context: $search_results$"
"""


def bedrock_kb_with_prompt(query, kb_id, prompt_template, logger):

    try:

        # Direct KB retrieval flow used as fallback when agent confidence is low
        response = agent_runtime_client.retrieve_and_generate(

            input={'text': query},

            retrieveAndGenerateConfiguration={
                'type': 'KNOWLEDGE_BASE',

                'knowledgeBaseConfiguration': {
                    'knowledgeBaseId': settings.KNOWLEDGE_BASE_ID_HR_AGENT,
                    'modelArn': settings.MODEL_ARN
                }
            }
        )

        return response['output']['text']

    except Exception as e:

        logger.exception(e)
        return None


def enhanced_bedrock_fallback(query, kb_id, agent_response, zone, logger):

    try:

        logger.info(f"agent_response: {agent_response}")

        contact = contact_dict.get(zone.lower(), "")
        head_office_contact = settings.COMMON_MAIL_HR

        # Triggers KB retrieval only when primary agent fails
        if "not available" in agent_response.lower():

            logger.info("Fallback mechanism triggered for HR KB retrieval")

            kb_result = bedrock_kb_with_prompt(
                query,
                kb_id,
                "",
                logger
            )

            logger.info(f"kb_result: {kb_result}")

            # KB also failed to identify any meaningful answer
            if any(phrase in kb_result for phrase in failure_phrases):

                kb_resp = {
                    "status_code": 200,
                    "result_text":
                        "Apologies, I couldn't find any information relevant "
                        "to your query. For further assistance, please reach "
                        "out to "
                        + head_office_contact +
                        " or Zonal Training Team "
                        + contact +
                        " along with query screenshot."
                }

            # Successful KB retrieval response
            elif kb_result:

                kb_resp = {
                    "status_code": 200,
                    "result_text": kb_result
                }

            # Final fallback when KB retrieval also returns empty
            else:

                kb_resp = {
                    "status_code": 201,
                    "result_text":
                        "Apologies, I couldn't find any information relevant "
                        "to your query. To know or further assistance, "
                        "please reach out to "
                        + head_office_contact +
                        " or Zonal Training Team "
                        + contact +
                        " along with query screenshot."
                }

            return kb_resp

        # Return original response when agent answered
        return {
            "status_code": 200,
            "result_text": agent_response
        }

    except Exception as e:

        logger.exception(e)

        return {
            "status_code": 500,
            "result_text": "Error occurred"
        }

