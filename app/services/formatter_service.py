# app/services/formatter_service.py

import json


DOWNLOADABLE_ENTITIES = [
    "welcome_letter_",
    "payment_schedule_",
    "interest_certificate_",
    "mini_soa_",
    "pay_emi_",
    "payment_history_",
]

NON_DICT_CONVERSION_ENTITIES = [
    "loan_summary_",
    "welcome_letter_",
    "payment_schedule_",
    "interest_certificate_",
    "mini_soa_",
    "pay_emi_"
    "payment_history_",
    "pdd_status_",
    "payment_status_",
    "loan_closure_",
    "wrong_loan_agreement_",
    "loan_cancellation_",
    "updation_related_",
    "disbursement_details_"
]


def format_loan_summary(response_data):
    """
    Formats loan summary response.
    """

    agreement_data = (
        response_data.get("data", {})
        .get("AGREEMENTDATA", {})
    )

    disbursement_data = (
        response_data.get("data", {})
        .get("DISBURSEMENTDATA", {})
    )

    loan_details = (
        response_data.get("data", {})
        .get("loandetails", {})
    )

    summary = (
        f"Sanction Amount: ₹{agreement_data.get('Amountfinanced', '0')}\n"
        f"Disbursement Amount: ₹{disbursement_data.get('DisbursementAmount', '0')}\n"
        f"EMI Amount: ₹{agreement_data.get('EMI', '0')}\n"
        f"Current due Date: {agreement_data.get('nextEmiDate', 'N/A')}\n"
        f"Tenure: {agreement_data.get('BalanceTenure', '0')} / "
        f"{agreement_data.get('Loantenure', '0')}\n"
        f"Principal Outstanding: ₹{loan_details.get('balanceprincipal', '0')}\n"
        f"Rate of Interest: {agreement_data.get('RateOfCurrentInterest', '0')}"
    )

    return summary


def format_download_link_response(
    entity,
    agreement_number,
    api_response,
):
    """
    Formats document download links.
    """

    entity_message_map = {
        "welcome_letter_": (
            "welcome letter",
            api_response["data"]["url"],
        ),
        "payment_schedule_": (
            "repayment schedule",
            api_response["data"]["download_url"],
        ),
        "interest_certificate_": (
            "interest certificate",
            api_response["data"]["url"],
        ),
        "mini_soa_": (
            "mini statement",
            api_response["data"]["url"],
        ),
        "pay_emi_": (
            "payment link",
            api_response["data"]["newurl"],
        ),
        "payment_history_": (
            "payment history",
            api_response["data"]["download_url"],
        ),
    }

    label, url = entity_message_map[entity]

    return (
        f"Here is the download link for the "
        f"{label} for agreement number "
        f"{agreement_number}: {url}"
    )


def format_pdd_status(response_data):
    """
    Formats PDD status response.
    """

    data = (
        response_data.get("data", {})
        .get("datastring", {})
    )

    summary = (
        f"Vehicle Registration Certificate: "
        f"{data.get('REGISTRATION_NUMBER', '')}\n"
        f"Invoice: "
        f"{data.get('INSURANCEPOLICY', '')}\n"
        f"Insurance: "
        f"{data.get('INVOICE_NUMBER', '')}\n"
        f"RC: "
        f"{data.get('RC', '')}"
    )

    return summary


def format_disbursement_details(response_data):
    """
    Formats disbursement detail response.
    """

    data = response_data.get("data", {})

    summary = (
        f"Sourcing Fee: ₹{data.get('SOURCING_FEE', '0')}\n"
        f"Admin & Processing Fee: ₹{data.get('Admin_processing_fee', '0')}\n"
        f"Statutory & Regulatory Fees - Stamp Duty Charges: "
        f"₹{data.get('stamp_duty_chargeges', '0')}\n"
        f"HDFC Life insurance: ₹{data.get('INSURANCE_HDFC', '0')}\n"
        f"MI insurance: ₹{data.get('CHOLA_MS_MI_INSUR', '0')}\n"
        f"PAC insurance: ₹{data.get('CHOLA_MS_PAC_PREMIUM', '0')}\n"
        f"Due date Shifting: ₹{data.get('DUEDATE_SHIFTING_CHARGES', '0')}"
    )

    return summary


def format_entity_response(
    entity,
    response,
    agreement_number,
    language_data,
    logger
):
    """
    Central formatter for all loan entities.
    """

    try:

        if (
            not isinstance(response, str)
            or response == "No Data Found"
        ):
            return response, "string"

        parsed_response = json.loads(response)

        # ---------------------------------------------------
        # LOAN SUMMARY
        # ---------------------------------------------------

        if entity == "loan_summary_":

            formatted_response = format_loan_summary(
                parsed_response
            )

            return formatted_response, "string"

        # ---------------------------------------------------
        # DOWNLOADABLE LINKS
        # ---------------------------------------------------

        elif entity in DOWNLOADABLE_ENTITIES:

            formatted_response = (
                format_download_link_response(
                    entity,
                    agreement_number,
                    parsed_response,
                )
            )

            return formatted_response, "string"

        # ---------------------------------------------------
        # PDD STATUS
        # ---------------------------------------------------

        elif entity == "pdd_status_":

            formatted_response = format_pdd_status(
                parsed_response
            )

            return formatted_response, "string"

        # ---------------------------------------------------
        # DISBURSEMENT DETAILS
        # ---------------------------------------------------

        elif entity == "disbursement_details_":

            formatted_response = (
                format_disbursement_details(
                    parsed_response
                )
            )

            return formatted_response, "string"

        # ---------------------------------------------------
        # DEFAULT
        # ---------------------------------------------------

        return response, "string"

    except Exception as e:
        logger.error(f"Error occurred while formatting entity response for {entity}: {e}")
        return (
            language_data.get(
                "fetch_error_message",
                "Sorry unable to fetch the details now. "
                "Please try again later",
            ),
        "string",
    )