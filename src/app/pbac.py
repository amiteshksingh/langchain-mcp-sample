# app/policy/pbac.py

# -------------------------
# Mock PBAC Authorization
# -------------------------

def classify_prompt(
    prompt: str,
    user_role: str
):

    prompt_lower = prompt.lower()

    if "national id" in prompt_lower:
        category = "PII_ACCESS"

    elif "risk profile" in prompt_lower:
        category = "CUSTOMER_RISK"

    elif "kyc" in prompt_lower:
        category = "KYC"

    else:
        category = "GENERAL"

    return {
        "decision": "PERMIT",
        "category": category
    }


def authorize_tool_access(
    user_role: str,
    agent_id: str,
    tool_name: str
):

    permissions = {

        "get_customer_risk_profile": [
            "KYC_ANALYST",
            "COMPLIANCE_OFFICER"
        ],

        "get_customer_sensitive_details": [
            "COMPLIANCE_OFFICER"
        ]
    }

    allowed_roles = permissions.get(
        tool_name,
        []
    )

    if user_role in allowed_roles:

        return {
            "decision": "PERMIT",
            "reason": (
                f"{user_role} allowed to execute "
                f"{tool_name}"
            )
        }

    return {
        "decision": "DENY",
        "reason": (
            f"{user_role} not permitted to "
            f"execute {tool_name}"
        )
    }

def evaluate_data_guardrail(
    rag_context: str
):

    rag_lower = (
        rag_context or ""
    ).lower()

    deny_patterns = [

        "access denied",

        "not permitted",

        "user role is not permitted",

        "no authorized",

        "permission denied",
    ]

    for pattern in deny_patterns:

        if pattern in rag_lower:

            return {
                "status": "FAIL",
                "reason": rag_context
            }

    return {
        "status": "PASS",
        "reason": (
            "Authorized documents retrieved"
        )
    }

def evaluate_output_guardrail(
    user_role: str,
    final_response: str
):

    response = (
        final_response or ""
    ).lower()

    if "********" in response:

        return {
            "status": "PASS",
            "reason": "PII successfully masked"
        }

    if user_role == "COMPLIANCE_OFFICER":

        return {
            "status": "NOT_USED",
            "reason": (
                "User allowed to view full PII"
            )
        }

    if "national id" in response:

        return {
            "status": "FAIL",
            "reason": (
                "PII exposed without masking"
            )
        }

    return {
        "status": "NOT_USED",
        "reason": (
            "No sensitive output returned"
        )
    }


def authorize(user_role, action, resource):

    if user_role == "KYC_ANALYST":
        return {
            "decision": "PERMIT"
        }

    return {
        "decision": "DENY"
    }


# -------------------------------------------------------------------
# Mock PlainID / PBAC decision for RAG retrieval.
#
# Replace this function with actual PlainID PDP API call.
# -------------------------------------------------------------------
from typing import Dict, Any
def pbac_decision_for_rag(
    user_context: Dict[str, Any],
    action: str,
    requested_customer: str,
) -> Dict[str, Any]:
    """
    Returns decision + obligations.

    Important:
      PDP decides access.
      PDP does NOT retrieve documents.
      Retrieval layer enforces filters.
    """

    role = user_context["userRole"]
    assigned_case = user_context["caseAssignment"]
    purpose = user_context["purposeOfUse"]

    
    if action != "READ_KYC_DOCUMENTS":
        return {
            "decision": "DENY",
            "reason": "Unsupported action",
            "allowedFilters": [],
            "obligations": []
        }

    if role != "KYC_ANALYST":
        return {
            "decision": "DENY",
            "reason": "User role is not permitted to read KYC documents",
            "allowedFilters": [],
            "obligations": []
        }

    if purpose != "KYC_REVIEW":
        return {
            "decision": "DENY",
            "reason": "Purpose of use is not allowed",
            "allowedFilters": [],
            "obligations": []
        }

    allowed_filters = []

    # Public information is always available for authenticated users.
    allowed_filters = [
        {
            "classification": "PUBLIC"
        }
    ]

    obligations = ["audit"]

    # Sensitive access allowed for KYC analyst only when assigned case matches.
    if role in ["KYC_ANALYST", "COMPLIANCE_OFFICER"] and purpose == "KYC_REVIEW":
        sensitive_filter = {
            "classification": "SENSITIVE",
            "caseId": assigned_case
        }
    
    
    # Only add customerName if available
    if requested_customer:
        sensitive_filter["customerName"] = requested_customer

    allowed_filters.append(sensitive_filter)


    if role == "KYC_ANALYST":
        obligations.append("maskPII")

    if role == "COMPLIANCE_OFFICER":
        obligations.append("allowPII")

    return {
        "decision": "PERMIT",
        "allowedFilters": allowed_filters,
        "obligations": obligations,
        "reason": "PBAC evaluated user, role, purpose, case assignment, and document classification.",
    }


def mask_sensitive_text(text: str) -> str:
    """
    Simple demo masking.
    In production, use a proper PII detection service such as Microsoft Presidio,
    DLP service, or policy-driven redaction service.
    """

    replacements = {
        "Ahmed Al Rahman": "A***** A* R*****",
        "1234567890": "********90",
        "John Smith": "J*** S****",
        "CUST-2026-001": "CUST-****-***",
        "USD 150": "USD ***",
        "Saudi Arabia": "S***** A******",
        "Industrial Manufacturing": "I******** M*********",
        "Amitesh K Singh": "A***** K S*****",
    }

    masked = text
    for source, target in replacements.items():
        masked = masked.replace(source, target)

    return masked



def mask_national_id(national_id: str) -> str:
    if not national_id or len(national_id) < 2:
        return "********"
    return "*" * (len(national_id) - 2) + national_id[-2:]


def mask_name(name: str) -> str:
    if not name:
        return ""
    parts = name.split()
    masked_parts = []
    for part in parts:
        if len(part) <= 2:
            masked_parts.append(part[0] + "*")
        else:
            masked_parts.append(part[0] + "*" * (len(part) - 2) + part[-1])
    return " ".join(masked_parts)

def evaluate_document_access(
    doc_metadata: dict,
    user_context: dict
) -> bool:

    classification = doc_metadata.get(
        "classification",
        "public"
    )

    # restricted docs require clearance
    if classification == "restricted":

        return (
            user_context.get("clearance")
            == "restricted"
        )

    return True