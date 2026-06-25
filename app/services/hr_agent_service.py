from fastapi.responses import JSONResponse
from fastapi.security import HTTPBasicCredentials

from app.core.config import settings
from app.core.constants import *
from app.db.session import *
from app.core.logging import *
from app.core.security import sha256_encoder
from app.services.hr_agent_llm_service import *
from app.services.agent_runtime import *

from app.schemas.pydantic_schema import HRAgentRequest


async def process_hr_agent_request(input_request: HRAgentRequest, credentials: HTTPBasicCredentials):
    dt, timestamp = create_log_name()
    log_file_name = settings.LOGGER_PATH + f"learing_platform_{dt}.log"
    logger = setup_logger('learing_platform_logger', log_file_name)
    kb_flag = 0
    enc_user_name,enc_pswd = sha256_encoder(logger,settings.AUTH_USER_NAME,settings.AUTH_PSWD)
    # Same auth contract as /v1/agent for parity across endpoints.
    if credentials.username == enc_user_name and credentials.password == enc_pswd:
        try:
            hr_agent_col = await create_mongo_connection_hr_agent(logger)
            logger.info(f'input request : {input_request}')

            user_query = input_request.user_question
            session_id = input_request.session_id
            emp_id = input_request.employee_id
            mobile_no = input_request.mobile_number
            zone = input_request.zone
    
            if("thanks" in user_query.lower()): 
                return JSONResponse(content={
                    "success":True,
                    "response": {"status_code":200,
                                 "result_text": "You're welcome! If you need any further assistance, feel free to reach out anytime.",
                    }
                })
            
            response = invoke_learning_agent(user_query,session_id,logger)
            logger.info(f"LLM response: {response}")
            # If learning agent returns a known failure phrase, fallback to KB retrieval.
            if any(phrase in response["result_text"] for phrase in failure_phrases):
                logger.info("agent failed now fallback mechanism of KB running")
                response = enhanced_bedrock_fallback(user_query, settings.KNOWLEDGE_BASE_ID_HR_AGENT, response["result_text"]+' not available', zone, logger)
                logger.info(f"KB response: {response}")
            if(hr_agent_col != None):
                result = await async_hr_log_mongo_insertion(logger, session_id, response, emp_id, mobile_no, timestamp, hr_agent_col)
                logger.info(f"mongo logger response : {result}")
            return JSONResponse(content={"success": True, "response": response})
        except Exception as e:
            logger.exception("Error while querying Bedrock agent")
            return JSONResponse(content={
                "success":False,
                "response": {"status_code":500,
                             "result_text":str(e)
                            }
            })
    else:
        logger.info(f"Authorization issue")
        return JSONResponse(content={
            "success":False,
            "response": {"status_code":401,
                         "result_text": "Authorization issue"
                        }
            })

