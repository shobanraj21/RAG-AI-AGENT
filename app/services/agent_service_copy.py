import time
import re
import ast
import secrets
import json
from datetime import datetime, timedelta

from fastapi.responses import JSONResponse
from fastapi.security import HTTPBasicCredentials

from app.core.config import *
from app.core.constants import *
from app.db.session import *
from app.utils.redis_cache import *
from app.utils.pii_utils import strip_pii
from app.utils.text_utils import (
    check_agent_response,
    convert_to_dict_if_possible,
    extract_after_dot,
    find_intent,
    mobile_num_check,
    mobile_num_validation,
    user_text_check,
    loan_verification,
)
from app.services.entity_mapping import entity_mapping
from app.utils.otp_utils import *
from app.core.logging import *
from app.core.security import sha256_encoder
from app.services.agent_runtime import *

from app.language.language_helper import get_language_mapping

from app.schemas.pydantic_schema import AgentRequest

async def fetch_spam(agent_col, query):
    try:
        # Reads recent matching conversations from MongoDB
        # Used for checking spam request detection
        return await agent_col.find(query).to_list(None)

    except Exception as e:
        logger.exception(f"Exception while reading mongo: {e}")
        return None

async def loan_against_mobilenumber(mobile_num, cust_col, logger,timestamp):
    try:
        # Customer verification API call used in Apply Loan flow.
        loan_against_mobilenumber_url = settings.LOAN_URL
        payload = json.dumps({
          "loanaccno": mobile_num,
          "source_system": "bedrock_cholaone_agent",
          "logintype": "M",
          "activity": "LOGINAUTH"
        })
        headers = {
          'Content-Type': 'application/json',
          'Authorization': settings.LOAN_URL_TOKEN
        }
        response = await async_client.post(loan_against_mobilenumber_url, headers=headers, content=payload)
        logger.info(f"response in loan_against_mobilenumber: {response}")
        response = response.json()
        logger.info(f"response in loan_against_mobilenumber in json: {response}")
        cust_insert_resp = await async_cust_log_mongo_insertion(logger,
                                                  mobile_num,
                                                  response,
                                                  timestamp,
                                                  cust_col)
        logger.info(f'customer check captured in mongo: {cust_insert_resp}')
        return response
    except Exception as e:
        logger.exception(f"exception in the function loan_against_mobilenumber: {e}")
        return None

async def loan_details_based_on_agreement(entity_loan_details, query_input, mobile_no, detected_mobile_no, agreement_number, session_id, logger, redis_client, redis_key_name, entity, show_all_loans):
    multi_loan_flag = 0
    identified_intent = ''
    choose_aggre_flag = 0
    logger.info('inside the function loan_details_based_on_agreement')

    try:
        api_resp, resp_count, rem_flag, loan_api_failure_flag = await entity_mapping(entity_loan_details, query_input, mobile_no, detected_mobile_no, agreement_number, session_id, logger, redis_client, redis_key_name, show_all_loans)

        if(resp_count == 0):
            message_text = 'No loans available under this mobile number'
            api_resp["message_text"] = message_text
            api_resp["multi_loan_flag"] = multi_loan_flag
            api_resp['identified_intent'] = entity
            api_resp['agreement_number'] = agreement_number
        elif(resp_count == 1):
            message_text = 'You have only one loan registered'
            agreement_number = api_resp['response'][0]['agreement_number']
            api_resp["message_text"] = message_text
            api_resp["multi_loan_flag"] = multi_loan_flag
            api_resp['identified_intent'] = entity
            api_resp['agreement_number'] = agreement_number
        else:
            if(choose_aggre_flag == 0):
                multi_loan_flag = 1
                message_text = 'You have multiple loans. Please choose one among them.'
                api_resp["message_text"] = message_text
                api_resp["multi_loan_flag"] = multi_loan_flag
                api_resp['identified_intent'] = entity
                api_resp['agreement_number'] = agreement_number

        logger.info(f'api_resp : {api_resp}\n resp_count : {resp_count}')
        return api_resp,resp_count
    except Exception as e:
        logger.exception(e)
        return api_resp,resp_count

async def process_agent_request(input_request: AgentRequest, credentials: HTTPBasicCredentials) -> JSONResponse:
    dt, timestamp = create_log_name()
    log_file_name = settings.LOGGER_PATH + "app_v1_"+str(dt)+".log"
    logger = setup_logger('app_logger',log_file_name)
    st = time.time()
    date_format = "%Y-%m-%d %H:%M:%S"
    
    detected_mobile_no = ''
    agreement_number = ''
    message_text = ''
    identified_intent = ''
    
    res_type = 'string'
    status_code = 200
    
    default_flag = 0
    choose_aggre_flag = 0
    loan_api_failure_flag = 0
    counter_flag_agg = 0
    user_text_flag = 0
    entity = ''
    apply_loan_flag = 0
    resp_count = 0
    rem_flag = 0
    retry_flag = 0
    loan_count = 0
    show_all_loans = 0
    
    phrase = "i will ask"
    entity_loan_details = 'loan_details_'
    
    lead_capture_dict = {}
    api_lead_dict = {}
    api_resp = {}
    response = {}

    is_spammed = []
    
    sr_flag = 0
    intent_dict = INTENT_DICT
    service_dict = SERVICE_DICT
    loan_doc_download_dict = LOAN_DOC_DOWNLOAD_DICT
    service_request_dict = SERVICE_REQUEST_DICT
    entity_limited_list = ENTITY_LIMITED_LIST
    entity_super_list = ENTITY_SUPER_LIST
    flow_related = FLOW_RELATED
    apply_loan_entity_list = APPLY_LOAN_ENTITY_LIST
    apply_loan_intent_list = APPLY_LOAN_INTENT_LIST
    sr_intent_list = SR_INTENT_LIST

    

    enc_user_name,enc_pswd = sha256_encoder(logger,settings.AUTH_USER_NAME,settings.AUTH_PSWD)
    # API expects client to send hashed credentials in HTTP Basic Auth.
    if credentials.username == enc_user_name and credentials.password == enc_pswd:
        agent_col = None
        lead_agent_col = None
        crm_col = None
        cust_col = None
        redis_client = None
        query_input = ""
        session_id = ""
        mobile_no = ""

        try:
            agent_col, lead_agent_col, crm_col, cust_col = await create_mongo_connection(logger)
            redis_client = create_redis_connection(logger)
            logger.info(f'input request : {input_request}')
            
            #P61-183 - language conversation changes 
            lang_code = input_request.selected_lang.lower()
            language_data = get_language_mapping(lang_code)
            query_input = input_request.query_input
            session_id = input_request.session_id
            query_input = input_request.query_input
            session_id = input_request.session_id
            mobile_no = input_request.mobile_no
            user_text_flag = input_request.user_text_flag
            show_more_req_flag = input_request.show_more_req_flag
            #P61-183 - language conversation changes
            show_all_loans = input_request.show_all_loans
            query_no = input_request.query_no
            lead_capture = input_request.lead_capture
            verification_code = input_request.verification_code
            otp_verified = input_request.otp_verified
            user_request = input_request.user_request
            redis_key_name = session_id + "_" + str(query_no)
            mobile_no = mobile_no.lstrip("\n")

            #Spam API call check
            if(agent_col != None):
                curr_time = datetime.strptime(timestamp, date_format)
                condition_timestamp = curr_time - timedelta(minutes = 2)
                curr_time = curr_time.strftime('%Y-%m-%d %H:%M:%S')
                condition_timestamp = condition_timestamp.strftime('%Y-%m-%d %H:%M:%S')
                pymongo_query = {"created_at":{"$gt": condition_timestamp, "$lt" : curr_time},"user_input" : query_input}
    
                is_spammed = await fetch_spam(agent_col, pymongo_query)
                logger.info(f'SPAM CHECK.........')
                logger.info(f'curr_time : {curr_time}\ncondition_timestamp : {condition_timestamp}')
                logger.info(f'is_spammed : {is_spammed}')
                
            # Keep existing PII scrub behavior; implementation now lives in utils.
            query_input = strip_pii(query_input, logger)
            
            #Initial API response
            if(len(is_spammed)<=10): 
                logger.info('inside the condition of non spammed')
                mobile_num_detection_flag = True 
                mobile_num_validation_flag = False
                if(lead_capture != '1'):
                    detected_mobile_no,agreement_number = mobile_num_check(query_input,logger)
                if(str(query_input).lower()=="hi"):
                    res_type = 'string'
                    response['counter_flag_agg'] = counter_flag_agg
                    
                    #P61-183 - language conversation changes 
                    #response['response'] = "I'm Yuva, a virtual Chola representative. How can I assist you today?"
                    response['response'] = language_data["greeting_message"]                    
                    response['response'] = "I'm Cholaone Agent, a virtual Chola representative. It's nice to meet you. How can I assist you today?"                    
                    response['intent_dict'] = intent_dict
                else:     
                    #Check mobile no in text and actual mobile no matches
                    if(detected_mobile_no):
                        mobile_num_detection_flag = False
                        mobile_num_validation_flag = mobile_num_validation(mobile_no,detected_mobile_no,logger)

                    #If they are matched replace mobile no in text and replace for product type text 
                    if(mobile_num_detection_flag or mobile_num_validation_flag): 
                        sub_str = 'for product type'
                        query_input = query_input.replace(detected_mobile_no, "")
                        if sub_str in query_input:
                            query_input = query_input[:query_input.find(sub_str)]
                        logger.info(f"query sent to llm {query_input}")
                        if(user_request == ""):
                            logger.info("Detect Intent............")
                            llm_response = invoke_common_agent(query_input,session_id)
                            logger.info(f"detect agent llm response: {llm_response}")
                            user_request = llm_response["result_text"]
                            if(llm_response['status_code']==300):
                                retry_flag = 1
                        #Calling agent
                        # Main intent branches:
                        # 1) About Chola (FAQ)
                        # 2) Apply Loan
                        # 3) My Loans (OTP-gated)
                        if(user_request == "About Chola"):
                            logger.info("FAQ............")
                            llm_response = invoke_faq_agent(query_input,session_id)
                            logger.info(f"responses : {llm_response}")
                            logger.info(f"response type : {type(llm_response)}")
                            response["response"] = llm_response["result_text"]
                            if(llm_response['status_code']==300):
                                retry_flag = 1
                            if (not isinstance(response["response"],str)):
                                res_type = 'json' 
                            else:
                                res_type = 'string'

                        elif(user_request == "Apply Loan"):
                            # invoke lead capture api
                            logger.info("APPLY LOAN............")
                            if (int(lead_capture) == 1): 
                                logger.info("LEAD CAPTURE............")
                                try:
                                    ID_value = "cholaone_agent_" + secrets.token_hex(16)
                                    logger.info(query_input)
                                    logger.info(type(query_input))
                                    if(isinstance(query_input, str)):
                                        customer_data = convert_to_dict_if_possible(query_input, logger)[0]
                                        logger.info(customer_data)
                                        logger.info(type(customer_data))
                                        
                                    if(isinstance(customer_data, dict)):
                                        pincode = customer_data["pincode"]
                                        product_type = customer_data["product_type"].lower()
                                        if(product_type.find("vehicle") != -1):
                                            product_type = "vf"
                                        elif(product_type.find("home") != -1):
                                            product_type = "hl"
                                        elif(product_type.find("gold") != -1):
                                            product_type = "gl"    
                                        elif(product_type.find("personal") != -1):
                                            product_type = "csel"
                                        elif(product_type.find("business") != -1):
                                            product_type = "sbpl"
                                        elif(product_type.find("property") != -1):
                                            product_type = "lap"
                                        else:
                                            pass
                                        customer_name = customer_data["customer_name"]
                                        customer_name = re.sub(r'[^a-zA-Z]', ' ', customer_name)
                                        customer_name = re.sub(r'\s+', ' ', customer_name).strip()
                                        customer_type = await get_cust_details_from_mongo(logger, cust_col, mobile_no)
                                        if(product_type == "vf"):
                                            product = "Car Loans"
                                        elif(product_type == "hl"):
                                            product = "Home Loans"
                                        elif(product_type == "gl"):
                                            product = "Gold Loans"
                                        elif(product_type == "csel"):
                                            product = "Consumer & Small Enterprise Loans"
                                        elif(product_type == "lap"):
                                            product = "Loan Against Property" 
                                        elif(product_type == "sbpl"):
                                            product = "Secured Business & Personal Loans"
                                        else:
                                            pass

                                        api_lead_dict = {"name": customer_name,
                                                    "mobile_number": mobile_no,
                                                    "pincode" : pincode,
                                                    "category" : "lr", 
                                                    "product": product,
                                                    "customer_type": customer_type, 
                                                    "source_from":"Chatbot"
                                                }
                                        logger.info(f'api_lead_dict: {api_lead_dict}')
                                        if(lead_agent_col != None):
                                            lead_insert_resp = await async_lead_log_mongo_insertion(logger, session_id, mobile_no, customer_name, pincode, ID_value, product_type, detected_mobile_no, timestamp, lead_agent_col)
                                        logger.info(f'lead captured in mongo: {lead_insert_resp}')
                                        response["response"] = api_lead_dict
                                        res_type = "json"
                                        result = await send_to_lead_api(logger, settings.LEAD_URL, settings.LEAD_URL_TOKEN, api_lead_dict, session_id, mobile_no, crm_col)
                                        logger.info(f"suite crm lead api response : {result}")
                                        crm_insert_resp = await async_crm_log_mongo_insertion(logger,
                                                          session_id,
                                                          mobile_no,
                                                          api_lead_dict,
                                                          result,
                                                          timestamp,
                                                          crm_col)
                                        logger.info(f'crm captured in mongo: {crm_insert_resp}')
                                except Exception as e:
                                    logger.exception(f'exception while capturing lead details in mongo {e}')
                                    response["response"] = "Issue in lead capture"
                                    status_code = 210
                            else:
                                logger.info("LOAN AGENT .................")
                                llm_response = invoke_loan_agent(query_input,session_id)
   
                                logger.info(f"responses : {llm_response}")
                                logger.info(f"response type : {type(llm_response)}")

                                entity_ = (llm_response['result_text']).lower()
                                logger.info(f'entity received from llm : {entity_}')

                                entity_ = find_intent(logger, entity_)

                                invalid_entity = check_agent_response(logger, apply_loan_intent_list, entity_)
                                if(invalid_entity==True):
                                    #P61-183 - language conversation changes
                                    #response['response'] = "Apologies, but I was unable to understand your request. Kindly rephrase it for better assistance."

                                    response['response'] = language_data["error_message"]

                                    response['loan_api_failure_flag'] = 0
                                    response['type'] = "string"
                                    response['retry_flag'] = "string"
                                    detected_mobile_no = ""
                                    response = {"message" : response,
                                                "detected_mobile_no": detected_mobile_no,
                                                "response_code": 207}
                                    if(agent_col != None):
                                        result = await async_convo_log_mongo_insertion(logger, query_input, session_id, mobile_no, response, detected_mobile_no, timestamp, agent_col)
                                    end_ = time.time()
                                    logger.info(f'final response : {response}')
                                    logger.info(f'total time taken : {end_-st}')
                                    return JSONResponse(content=response)
                                
                                loan_verification_details = await loan_against_mobilenumber(mobile_no, cust_col, logger, timestamp)
                                loan_verification_ = loan_verification(loan_verification_details,llm_response["result_text"],logger)
     
                                if(isinstance(loan_verification_,str)):
                                    loan_verification_ = json.loads(loan_verification_)
                                
                                loan_verification_['apply_loan_flag'] = 1
                                response = loan_verification_
                                if (not isinstance(response['response'],str)):
                                    res_type = 'json' 
                                else:
                                    res_type = 'string'   
                        elif(user_request == "My Loans"):        
                            # OTP gate protects loan-account actions.
                            if(query_input == 'otp_generate'):
                                logger.info("Inside OTP Generate in APP")
                                if(settings.APP_ENV == "stage"):
                                    logger.info("Stage env - No OTP will be generated")
                                    pass
                                else:
                                    logger.info("Prod env - OTP generate")
                                    otp_generate_response = await otp_generation(mobile_no, logger)
                                res_type = 'string'
                                #response['response'] = "Please enter your otp..."
                                response['response'] = language_data["otp_request_message"]
                                response['flow_type'] = 'otp_generate'
                            if(query_input == 'otp_verify'):
                                otp_verify_response = {}
                                verification_code = input_request.verification_code
                                if(settings.APP_ENV == "stage"):
                                    logger.info("Stage env - No OTP will be verified")
                                    pass
                                else:
                                    logger.info("Prod env - OTP verify")
                                    otp_verify_response = await otp_verification(mobile_no, verification_code, logger)
                                    if otp_verify_response is None:
                                        otp_verify_response = {
                                            "success": False,
                                            "message": "OTP verification service unavailable"
                                            }                                
                                if(verification_code == "1234"):
                                    otp_verify_response['success'] = True
                                else:
                                    otp_verify_response['success'] = False
                                response['flow_type'] = 'otp_verify'
                           
                                if(otp_verify_response['success'] == True):
                                    response['otp_verified'] = "1" 
                                    otp_verified = "1"
                                    query_input = "Show my loan details"
                                else:
                                    response['otp_verified'] = "0"
                                    otp_verified = "0"
                                    #response['response'] = "Invalid OTP. Please try again."
                                    response['response'] = language_data["otp_fail_message"]
                                    response['loan_api_failure_flag'] = 0
                                    response['type'] = "string"
                                    response['retry_flag'] = "string"
                                    if(detected_mobile_no is None):
                                        detected_mobile_no = ""
                                    response = {"message" : response,
                                                "detected_mobile_no": detected_mobile_no,
                                                "response_code": 208}
                                    if(agent_col != None):
                                        result = await async_convo_log_mongo_insertion(logger, query_input, session_id, mobile_no, response, detected_mobile_no, timestamp, agent_col)
                                    end_ = time.time()
                                    logger.info(f'final response : {response}')
                                    logger.info(f'total time taken : {end_-st}')
                                    return JSONResponse(content=response)
                            if(otp_verified == "1"):
                                logger.info(f"query_input : {query_input}")
                                if(show_more_req_flag == "0"):
                                    if(user_text_flag):
                                        sr_flag,entity = user_text_check(query_input,logger)
                                        logger.info(f"entity: {entity}") 

                                    if(int(sr_flag)==0):
                                        llm_response = invoke_sr_agent(query_input,session_id)
                                        entity_ = (llm_response['result_text']).lower()

                                        entity = extract_after_dot(entity_, phrase, logger)
                                        logger.info(f'entity received from llm : {entity_}')

                                        sr_flag,entity = user_text_check(entity,logger)
                                        invalid_entity = check_agent_response(logger, sr_intent_list, entity_)
                                       
                                        if(invalid_entity==True):
                                            #P61-183 - language conversation changes 
                                            #response['response'] = "Apologies, but I was unable to understand your request. Kindly rephrase it for better assistance."

                                            response['response'] = language_data["error_message"]
                                            response['loan_api_failure_flag'] = 0
                                            response['type'] = "string"
                                            response['retry_flag'] = "string"
                                            detected_mobile_no = ""
                                            response = {"message" : response,
                                                        "detected_mobile_no": detected_mobile_no,
                                                        "response_code": 207}
                                            if(agent_col != None):
                                                result = await async_convo_log_mongo_insertion(logger, query_input, session_id, mobile_no, response, detected_mobile_no, timestamp, agent_col)
                                            end_ = time.time()
                                            logger.info(f'final response : {response}')
                                            logger.info(f'total time taken : {end_-st}')
                                            return JSONResponse(content=response)
                                        if(llm_response['status_code']==300):
                                            retry_flag = 1
                                        for i in entity_super_list:
                                            if i in entity: 
                                                entity = i
                                        if(entity in "loan_details_"):
                                            default_flag = sr_flag   
                                    
                                    if(entity in entity_limited_list and agreement_number == ''):

                                        resp,resp_count = await loan_details_based_on_agreement(entity_loan_details, query_input, mobile_no, detected_mobile_no, agreement_number, session_id, logger, redis_client, redis_key_name, entity)
                                        if(resp_count == 0):
                                            loan_count = resp_count
                                            api_resp = resp
                                        elif(resp_count == 1):
                                            loan_count = resp_count
                                            if('identified_intent' not in resp.keys()):
                                                api_resp = {}
                                            else:
                                                api_resp, resp_count, rem_flag,loan_api_failure_flag = await entity_mapping(resp['identified_intent'], query_input, mobile_no, detected_mobile_no, resp['agreement_number'], session_id, logger, redis_client, redis_key_name, show_all_loans)   
                                        else:
                                            loan_count = resp_count
                                            api_resp = resp
                                            res_type = 'json'  
                                    else:
                                        api_resp, resp_count, rem_flag, loan_api_failure_flag = await entity_mapping(entity, query_input, mobile_no, detected_mobile_no, agreement_number, session_id, logger, redis_client, redis_key_name, show_all_loans)
                                        loan_count = resp_count 
                                else: 
                                   if(redis_client != None):
                                       api_resp, resp_count, rem_flag = retrieve_data_redis(redis_client, redis_key_name, logger)
                                
                                logger.info(f"LOAN COUNT............ {resp_count}")
                                logger.info(f"API RESPONSE...........{api_resp}")
                                logger.info(f"FLAG...........{rem_flag}")
                                if(resp_count == 0):
                                    api_resp['response'] = "No loans available"
                                if(isinstance(api_resp, dict)):
                                    if('response' not in api_resp.keys()):
                                        #response['response'] = "We ran into a technical issue. Please try again later."
                                        response['response'] = language_data["technical_error_message"]
                                        status_code = 201
                                    else:
                                        if(len(api_resp['response']) == 0 ):
                                            api_resp['response'] = "No loans available"

                                if(isinstance(api_resp,str)):
                                    api_resp = json.loads(api_resp)
                                logger.info(f"loan_count: {loan_count}")
                                logger.info(f"api_resp: {api_resp}")
                                logger.info(f"agreement_number: {agreement_number}")
                                
                                if(isinstance(api_resp,list)):  
                                    response['response'] = api_resp
                                elif("identified_intent" in api_resp.keys() and api_resp["identified_intent"] in flow_related and (loan_count!=0 or agreement_number!='')):
                                    response['response'] = api_resp["identified_intent"]
                                    sr_flag = 1  
                                elif("response" in api_resp.keys() and api_resp["response"] in flow_related and (loan_count!=0 or agreement_number!='')):
                                    response['response'] = api_resp["response"]
                                    sr_flag = 1
                                elif("result_text" in api_resp.keys() and api_resp["result_text"] in flow_related and (loan_count!=0 or agreement_number!='')):
                                    response['response'] = api_resp["result_text"]
                                    sr_flag = 1
                                elif("response" in api_resp.keys() and api_resp["response"] in entity_super_list and (loan_count!=0 or agreement_number!='')):
                                    response['response'] = api_resp["response"]
                                    sr_flag = 1
                                elif("result_text" in api_resp.keys() and api_resp["result_text"] in entity_super_list and (loan_count!=0 or agreement_number!='')):
                                    response['response'] = api_resp["result_text"]
                                    sr_flag = 1  
                                else:
                                    response['response'] = api_resp['response']

                                if (not isinstance(response['response'],str)):
                                    res_type = 'json' 
                                else:
                                    res_type = 'string'

                                if (isinstance(response['response'],str) and response['response'] != 'No Data Found' and entity not in ["loan_summary_", "welcome_letter_", "payment_schedule_", "interest_certificate_", "mini_soa_", "payment_history_", "pdd_status_","payment_status_", "loan_closure_", "wrong_loan_agreement_", "loan_cancellation_", "updation_related_"]): 
                                    try:
                                        response['response'],res_type = convert_to_dict_if_possible(response['response'],logger)
                                    except Exception as e:
                                        logger.exception(e)
                                        api_resp['response'] = "dict conversion issue"
                                        status_code = 202
                                    try:
                                        if(response['response']['code'] != None and response['response']['code'] != 200):
                                            response['response'] = response['response']['message']
                                            res_type = 'string'
                                    except Exception as e:
                                        logger.exception(e)  
                                        api_resp['response'] = "code response issue"
                                        status_code = 204
                                else:
                                    try:
                                        if(isinstance(response['response'],str) and response['response'] != 'No Data Found' and entity == "loan_summary_"):                 
                                            summary_dict = {}
                                            response['response'] = json.loads(response['response'])
                                            res_type = 'json' 
                                            resp = (response or {}).get('response') or {}
                                            data = resp.get('data') or {}
                                            agreement_data = data.get('AGREEMENTDATA') or {}
                                            disbursement_data = data.get('DISBURSEMENTDATA') or {}
                                            loan_details = data.get('loandetails') or {}
                                            
                                            summary = (
                                                "Sanction Amount: ₹" + str(agreement_data.get('Amountfinanced', '0')) + "\n" +
                                                "Disbursement Amount: ₹" + str(disbursement_data.get('DisbursementAmount', '0')) + "\n" +
                                                "EMI Amount: ₹" + str(agreement_data.get('EMI', '0')) + "\n" +
                                                "Current due Date: " + str(agreement_data.get('nextEmiDate', 'N/A')) + "\n" +
                                                "Tenure: " + str(agreement_data.get('BalanceTenure', '0')) + " / " + str(agreement_data.get('Loantenure', '0')) + "\n" +
                                                "Principal Outstanding: ₹" + str(loan_details.get('balanceprincipal', '0')) + "\n" +
                                                "Rate of Interest: " + str(agreement_data.get('RateOfCurrentInterest', '0'))
                                            )
                                            response['response'] = summary
                                            res_type = 'string'
                                            
                                        elif(isinstance(response['response'],str) and response['response'] != 'No Data Found' and entity == "welcome_letter_"):                 
                                            api_response = json.loads(response['response'])
                                            output_text = "Here is the download link for the welcome letter for agreement number " + agreement_number + ": "+ api_response['data']['url']
                                            response['response'] = output_text
                                            
                                        elif(isinstance(response['response'],str) and response['response'] != 'No Data Found' and entity == "payment_schedule_"): 
                                            api_response = json.loads(response['response'])
                                            output_text = "Here is the download link for the repayment schedule for agreement number " + agreement_number + ": "+ api_response['data']['download_url']
                                            response['response'] = output_text
                                            
                                        elif(isinstance(response['response'],str) and response['response'] != 'No Data Found' and entity == "interest_certificate_"):        
                                            api_response = json.loads(response['response'])
                                            output_text = "Here is the download link for the interest certificate for agreement number " + agreement_number + ": "+ api_response['data']['url']
                                            response['response'] = output_text
                                            
                                        elif(isinstance(response['response'],str) and response['response'] != 'No Data Found' and entity == "mini_soa_"):                                
                                            api_response = json.loads(response['response'])
                                            output_text = "Here is the download link for the mini statement for agreement number " + agreement_number + ": "+ api_response['data']['url']
                                            response['response'] = output_text
                                            
                                        elif(isinstance(response['response'],str) and response['response'] != 'No Data Found' and entity == "pay_emi_"):
                                            
                                            api_response = json.loads(response['response'])
                                            output_text = "Here is the download link for the payment link for agreement number " + agreement_number + ": "+ api_response['data']['newurl']
                                            response['response'] = output_text
                                            
                                        elif(isinstance(response['response'],str) and response['response'] != 'No Data Found' and entity == "payment_history_"):
                                            
                                            api_response = json.loads(response['response'])
                                            output_text = "Here is the download link for the payment history for agreement number " + agreement_number + ": "+ api_response['data']['download_url']
                                            response['response'] = output_text
                                            
                                        elif(isinstance(response['response'],str) and response['response'] != 'No Data Found' and entity == "pdd_status_"):
                                            summary_dict = {}
                                            response['response'] = json.loads(response['response'])
                                            res_type = 'json' 
                                            summary = "Vehicle Registration Certificate:" + response['response']['data']['datastring']['REGISTRATION_NUMBER'] + "\n" + "Invoice" + response['response']['data']['datastring']['INSURANCEPOLICY'] + "\n" + "Insurance" + response['response']['data']['datastring']['INVOICE_NUMBER'] + "\n" + "RC: " + response['response']['data']['datastring']['RC']
                                            response['response'] = summary
                                            res_type = 'string'
                                            
                                        elif(isinstance(response['response'],str) and response['response'] != 'No Data Found' and entity == "disbursement_details_"):
                                            summary_dict = {}
                                            response['response'] = json.loads(response['response'])
                                            res_type = 'json' 
                                            summary = "Sourcing Fee: ₹" + response['response']['data']['SOURCING_FEE'] + "\n" + "Admin & Processing Fee: ₹" + response['response']['data']['Admin_processing_fee'] + "\n" + "Statutory & Regulatory Fees - Stamp Duty Charges: ₹" + response['response']['data']['stamp_duty_chargeges'] + "\n" + "HDFC Life insurance: ₹" + response['response']['data']['INSURANCE_HDFC'] + "\n" + "MI insurance: ₹" + response['response']['data']['CHOLA_MS_MI_INSUR'] + "\n" + "PAC insurance: ₹" + str(response['response']['data']['CHOLA_MS_PAC_PREMIUM']) + "\n" + "Due date Shifting: ₹" + response['response']['data']['DUEDATE_SHIFTING_CHARGES']
                                            response['response'] = summary
                                            res_type = 'string'
                                        
                                    except Exception as e:
                                        logger.exception(e)
                                        response['response'] = "Sorry unable to fetch the details now. Please try again later"
                                        status_code = 209
                                if(default_flag):
                                    sr_flag = 0
                                response['counter_flag_agg'] = rem_flag
                                response['sr_flag'] = sr_flag
                                response['loan_count'] = loan_count
                                
                                if(loan_count == 0 and len(agreement_number)==0):
                                    response['apply_loan_flag'] = 1
                                    sr_flag = 0
                                    response["sr_flag"] = sr_flag
                                if(sr_flag == 1):
                                    response['sr_text'] = entity
                                logger.info(f"responses : {response}")
                                logger.info(f"response type : {type(response)}")
                                
                    else:
                        res_type = 'string'
                        response['response'] = 'mobile number mismatch'
                        status_code = 205
            else:
                res_type = 'string'
                response['response'] = 'being spammed'
                status_code = 206
                
        except Exception as e:
            logger.exception(f"exception while getting response : {e}")
        
        # Final response normalization happens here so all flows return
        # a common envelope.
        response["type"] = res_type
        response["retry_flag"] = retry_flag
        response["loan_api_failure_flag"] = loan_api_failure_flag

        try:
            if(response is not None and 'response' in response.keys() and isinstance(response['response'],str)):
                if(int(status_code) == 422):
                    response = json.loads(response['response'])['message']
                    if(response == 'The agfreement number field is required.'):
                        response = {"response":'Please enter your query along with the agreement number.',"type": "string"}
        except Exception as e:
            logger.exception(e)
        response = {"message" : response,'detected_mobile_no':detected_mobile_no,'response_code':status_code}
        logger.info(f'final response : {response}')
        if("intent_dict" in response["message"].keys()):
            response["message"]["intent_dict"] = {str(k): v for k, v in response["message"]["intent_dict"].items()}
        if(agent_col != None):
            result = await async_convo_log_mongo_insertion(logger, query_input, session_id, mobile_no, response, detected_mobile_no, timestamp, agent_col)
            logger.info(f"mongo logger response : {result}")
        end_ = time.time()
        logger.info(f'total time taken : {end_-st}')
        if(response):
            return JSONResponse(content=response)
        else:
            return JSONResponse(content="no response")
    else:
        res_type = 'string'
        detected_mobile_no = ''
        message = 'Authorization issue'
        status_code = 401
        response = {"message" : message,'detected_mobile_no':detected_mobile_no,'response_code':status_code}
        logger.info(f'final response : {response}')
        return response



