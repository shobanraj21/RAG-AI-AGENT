# Conversation intent dictionaries
INTENT_DICT: dict[int, str] = {0: "About Chola", 1: "My Loans", 2: "Apply Loan"}

SERVICE_DICT: dict[int, str] = {
    0: "Loan Summary",
    1: "Disbursement Deduction",
    2: "My Loan Documents",
    3: "Service Request",
    4: "Pay Now",
    5: "PDD Status",
}

LOAN_DOC_DOWNLOAD_DICT: dict[int, str] = {
    0: "Welcome Letter",
    1: "Repayment Schedule",
    2: "Mini SOA",
    3: "Interest Certificate",
}

SERVICE_REQUEST_DICT: dict[int, str] = {
    0: "mobile_updation",
    1: "email_validation",
    2: "loan_closure_",
    3: "wrong_loan_agreement_",
    4: "loan_cancellation_",
    5: "updation_related_",
    6: "email_id_updation_",
    7: "name_correction_",
    8: "address_correction_",
    9: "mobile_no_updation_",
    10: "pan_no_updation_",
}

# Entity and intent lists
APPLY_LOAN_INTENT_LIST: list[str] = [
    "vf_apply_loan",
    "csel_apply_loan",
    "sbpl_apply_loan",
    "hl_apply_loan",
    "gl_apply_loan",
    "apply_loan_",
]

SR_INTENT_LIST: list[str] = [
    "vf_", "csel_", "hl_", "lap_", "sbpl_", "sme_", "loan_details_",
    "payment_history_", "payment_schedule_", "welcome_letter_", "mini_soa_",
    "pay_emi_", "loan_summary_", "interest_certificate_", "pdd_status_",
    "disbursement_details_", "payment_status_", "loan_closure_",
    "wrong_loan_agreement_", "loan_cancellation_", "updation_related_",
    "email_id_updation_", "name_correction_", "address_correction_",
    "mobile_no_updation_", "pan_no_updation_", "enquiry_foreclosure_",
    "loan_structure_", "payment_link_", "confirm_emi_payment_", "gst_invoice_",
    "foreclosure_letter_", "disbursement_related_", "hdfc_insurance_policy_",
    "accident_cover_policy_", "policy_document_", "product_features_",
    "limit_eligibility_", "deliverables_", "foreclosure_",
    "settlement_closure_", "permit_letters_", "payment_made_", "insurance_",
    "balance_confirmation_", "refund_related_", "waiver_related_",
    "crm_related_", "od_loan_related_", "credit_bureau_",
    "statement_of_accounts_", "disbursement_related_query_",
    "bounce_related_query_", "emi_related_query_", "loan_closure_enquiry_",
    "insurance_queries_", "part_prepayment_", "pmay_related_",
    "documents_related_", "insurance_related_", "loan_downsize_",
    "lap_related_", "lap_swapping_", "customer_profile_", "chola_anmol_",
    "closure_cancellation_", "kyc_related_", "sme_banking_", "collections_",
    "other_queries_feedback_", "track_loan_", "create_service_request_",
    "track_service_request_", "no_due_certi_",
]

ENTITY_LIMITED_LIST: list[str] = [
    "welcome_letter_", "payment_history_", "mini_soa_", "loan_summary_",
    "pay_emi_", "payment_schedule_", "pdd_status_", "disbursement_details_",
    "interest_certificate_", "track_loan_", "create_service_request_",
    "track_service_request_", "payment_status_", "loan_closure_",
    "wrong_loan_agreement_", "loan_cancellation_", "updation_related_",
    "email_id_updation_", "name_correction_", "address_correction_",
    "mobile_no_updation_", "pan_no_updation_", "loan_structure_",
    "payment_link_", "confirm_emi_payment_", "no_due_certi_", "gst_invoice_",
    "foreclosure_letter_", "disbursement_related_", "hdfc_insurance_policy_",
    "accident_cover_policy_", "policy_document_", "product_features_",
    "limit_eligibility_", "deliverables_", "csel_foreclosure_",
    "settlement_closure_", "permit_letters_", "payment_made",
    "balance_confirmation_", "insurance_", "enquiry_foreclosure_",
    "refund_related_", "waiver_related_", "crm_related_",
    "credit_bureau_", "od_loan_related_",
]

ENTITY_SUPER_LIST: list[str] = [
    "csel_", "vf_", "hl_", "lap_", "sbpl_", "sme_", "gl_",
    "welcome_letter_", "loan_details_", "payment_history_", "mini_soa_",
    "loan_summary_", "pay_emi_", "payment_schedule_", "pdd_status_",
    "disbursement_details_", "interest_certificate_", "track_loan_",
    "create_service_request_", "track_service_request_", "payment_status_",
    "loan_closure_", "wrong_loan_agreement_", "loan_cancellation_",
    "updation_related_", "email_id_updation_", "name_correction_",
    "address_correction_", "mobile_no_updation_", "pan_no_updation_",
    "loan_structure_", "payment_link_", "confirm_emi_payment_",
    "no_due_certi_", "gst_invoice_", "foreclosure_letter_",
    "disbursement_related_", "hdfc_insurance_policy_", "accident_cover_policy_",
    "policy_document_", "product_features_", "limit_eligibility_",
    "deliverables_", "csel_foreclosure_", "settlement_closure_",
    "permit_letters_", "payment_made", "balance_confirmation_",
    "insurance_", "enquiry_foreclosure_", "refund_related_",
    "waiver_related_", "crm_related_", "credit_bureau_", "od_loan_related_",
]

FLOW_RELATED: list[str] = [
    "payment_status_", "loan_closure_", "wrong_loan_agreement_",
    "loan_cancellation_", "updation_related_", "email_id_updation_",
    "name_correction_", "address_correction_", "mobile_no_updation_",
    "pan_no_updation_", "loan_structure_", "payment_link_",
    "confirm_emi_payment_", "no_due_certi_", "gst_invoice_",
    "foreclosure_letter_", "disbursement_related_", "hdfc_insurance_policy_",
    "accident_cover_policy_", "policy_document_", "product_features_",
    "limit_eligibility_", "deliverables_", "csel_foreclosure_",
    "settlement_closure_", "permit_letters_", "enquiry_foreclosure_",
    "payment_made", "balance_confirmation_", "insurance_",
    "refund_related_", "waiver_related_", "crm_related_",
    "credit_bureau_", "od_loan_related_",
]

APPLY_LOAN_ENTITY_LIST: list[str] = [
    "vf_apply_loan", "csel_apply_loan", "sbpl_apply_loan",
    "hl_apply_loan", "gl_apply_loan", "apply_loan_",
]

# PII replacement tokens
REPLACE_PII_TEXT: list[str] = [
    "aadhar", "aadhaar", "adhar", "uid", "uidai", "12 digit number",
    "aadhar number", "aadhaar no", "aadhaar id", "aadhar id",
    "unique identification",
    "ration", "rationcard", "ration card", "family card", "food card",
    "public distribution", "pds", "10 digit number", "household id",
    "driving license", "dl", "driver's license", "driving licence",
    "license number", "driving id", "dl number", "ss-rr-yyyy-nnnnnnn",
    "passport", "passport number", "travel document", "pp number",
    "8 character code", "passport no",
    "voter id", "voter card", "epic", "election card", "epic number",
    "voter slip", "voter identity", "voting card",
]

# SR regex text map
SR_REGEX_TEXTS: dict[str, str] = {
    "welcome letter": "welcome_letter_",
    "pay emi": "pay_emi_",
    "repayment schedule": "payment_schedule_",
    "mini soa": "mini_soa_",
    "loan details ": "loan_details_",
    "loan summary": "loan_summary_",
    "payment details": "payment_history_",
    "pay now": "pay_emi_",
    "pl loan": "csel_",
    "personal loan": "csel_",
    "personal loans": "csel_",
    "pl detail": "csel_",
    "pl details": "csel_",
    "csel loan": "csel_",
    "csel loans": "csel_",
    "csel detail": "csel_",
    "csel details": "csel_",
    "hl loan": "hl_",
    "hl loans": "hl_",
    "home loan": "hl_",
    "home loans": "hl_",
    "hl detail": "hl_",
    "hl details": "hl_",
    "sbpl loan": "sbpl_",
    "sbpl loans": "sbpl_",
    "sbpl detail": "sbpl_",
    "sbpl details": "sbpl_",
    "business loan": "sbpl_",
    "business loans": "sbpl_",
    "gl loan": "gl_",
    "gl loans": "gl",
    "gl": "gl_",
    "gl detail": "gl_",
    "gl details": "gl_",
    "lap": "lap_",
    "sme": "sme_",
    "vf loan": "vf_",
    "vf loans": "vf_",
    "vehicle loan": "vf_",
    "vf detail": "vf_",
    "vf details": "vf_",
    "vf": "vf_",
    "loan structure": "loan_structure_",
    "payment link": "payment_link_",
    "confirm emi payment": "confirm_emi_payment_",
    "no due certificate": "no_due_certi_",
    "gst invoice": "gst_invoice_",
    "fore closure letter": "foreclosure_letter_",
    "disbursement related": "disbursement_related_",
    "hdfc insurance policy": "hdfc_insurance_policy_",
    "accident cover policy": "accident_cover_policy_",
    "policy document": "policy_document_",
    "product features": "product_features_",
    "limit eligibility": "limit_eligibility_",
    "deliverables": "deliverables_",
    "csel foreclosure": "csel_foreclosure_",
    "settlement closure": "settlement_closure_",
    "foreclosure letter": "foreclosure_letter_",
    "foreclosure": "csel_foreclosure_",
    "balance confirmation": "balance_confirmation_",
    "vf insurance": "insurance_",
    "enquiry foreclosure": "enquiry_foreclosure_",
    "disbursement detection": "disbursement_details_",
    "show my loan details": "loan_details_",
    "refund": "refund_related_",
    "waiver": "waiver_related_",
    "crm details": "crm_related_",
    "credit bureau": "credit_bureau_",
    "overdraft loan": "credit_bureau_",
    "loan od": "od_loan_related_",
}

# HR response support constants
FAILURE_PHRASES: list[str] = [
    "does not provide", "do not provide", "could not find", "not available", "does not", "do not",
    "not found", "no information", "cannot find", "unable to locate", "cannot",
    "not specified", "not mentioned", "not included", "not covered",
    "no details", "information is not", "not documented", "unavailable",
    "missing information", "no data", "not present", "not contained",
]

CONTACT_DICT: dict[str, str] = {
    # zone_name: contact_details populate from config/env at runtime
}

# Entity mapping constants
ENTITY_MAPPING_ENTITIES: list[str] = [
    "csel_", "vf_", "hl_", "lap_", "sbpl_", "sme_", "gl_",
    "welcome_letter_", "loan_details_", "payment_history_",
    "mini_soa_", "loan_summary_", "pay_emi_", "payment_schedule_",
    "pdd_status_", "disbursement_details_", "interest_certificate_",
    "track_loan_", "create_service_request_", "track_service_request_",
    "payment_status_", "loan_closure_", "wrong_loan_agreement_",
    "loan_cancellation_", "updation_related_", "email_id_updation_",
    "name_correction_", "address_correction_", "mobile_no_updation_",
    "pan_no_updation_", "loan_structure_", "payment_link_",
    "confirm_emi_payment_", "no_due_certi_", "gst_invoice_",
    "foreclosure_letter_", "disbursement_related_",
    "hdfc_insurance_policy_", "accident_cover_policy_",
    "policy_document_", "product_features_", "limit_eligibility_",
    "deliverables_", "csel_foreclosure_", "settlement_closure_",
    "permit_letters_", "payment_made_", "balance_confirmation_",
    "insurance_", "enquiry_foreclosure_",
]

ENTITY_MAPPING_API_PATHS: dict[str, str] = {
    "welcome_letter_": "api/v1/download-welcome-letter",
    "loan_details_": "api/v1/get-all-loans",
    "payment_history_": "api/v1/get-payment-history",
    "mini_soa_": "api/v1/download-mini-statement",
    "loan_summary_": "api/v1/get-loan-summary",
    "payment_schedule_": "api/v1/get-payment-schedule",
    "pdd_status_": "api/v1/get-pdd-status",
    "interest_certificate_": "api/v1/get-interest-certificate",
    "track_loan_": "api/v1/track-loan",
    "create_service_request_": "api/v1/create-service-request",
    "track_service_request_": "api/v1/track-service-request",
}

ENTITY_MAPPING_URL_KEYS: list[str] = [
    "csel_", "vf_", "hl_", "lap_", "sbpl_", "sme_", "gl_",
    "welcome_letter_", "loan_details_", "payment_history_",
    "mini_soa_", "loan_summary_", "payment_schedule_", "pdd_status_",
    "interest_certificate_", "track_loan_", "create_service_request_",
    "track_service_request_",
]

LOAN_PRODUCT_TYPE_ABBREV: dict[str, str] = {
    "csel": "Unsecured Personal & Business Loans",
    "vf": "Vehicle Loans",
    "hl": "Home Loans",
    "lap": "Loan Against Property",
    "sbpl": "Secured Business & Personal Loans",
    "sme": "Small & Medium Term Enterprises",
    "gl": "Gold Loan",
}

# Runtime mock keyword groups
APPLY_KEYWORDS: list[str] = [
    "apply", "want loan", "need loan", "get loan",
    "home loan", "vehicle loan", "car loan",
    "gold loan", "personal loan", "business loan",
]

MY_LOAN_KEYWORDS: list[str] = [
    "my loan", "show loan", "loan details", "loan summary",
    "emi", "payment", "repayment", "welcome letter",
    "mini soa", "statement", "interest certificate",
    "otp", "pdd", "disbursement",
]

# Backward-compatible aliases used by existing service code.

service_dict = SERVICE_DICT
loan_doc_download_dict = LOAN_DOC_DOWNLOAD_DICT
service_request_dict = SERVICE_REQUEST_DICT
apply_loan_intent_list = APPLY_LOAN_INTENT_LIST
sr_intent_list = SR_INTENT_LIST
entity_limited_list = ENTITY_LIMITED_LIST
entity_super_list = ENTITY_SUPER_LIST
flow_related = FLOW_RELATED
apply_loan_entity_list = APPLY_LOAN_ENTITY_LIST
replace_pii_text = REPLACE_PII_TEXT
failure_phrases = FAILURE_PHRASES
contact_dict = CONTACT_DICT
entity_mapping_entities = ENTITY_MAPPING_ENTITIES
entity_mapping_api_paths = ENTITY_MAPPING_API_PATHS
entity_mapping_url_keys = ENTITY_MAPPING_URL_KEYS
