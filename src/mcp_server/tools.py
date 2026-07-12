from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Any
import logging
logger = logging.getLogger(__name__)

logger.info(
    "MCP Tool initialized.",
    flush=True
)


def add_numbers(a: float, b: float) -> float:
    return a + b


def get_utc_time() -> str:
    return datetime.now(timezone.utc).isoformat()


def explain_text(text: str) -> str:
    return f"Look {text} from existing internal knowledge and provide a detailed explanation of it."




# ==========================================================
# MOCK CUSTOMER DATABASE
# Replace with CRM / KYC API later
# ==========================================================

CUSTOMERS = {

    "ABC Corp": {

        "customerId": "CUST-2026-001",
        "customerName": "ABC Corp",
        "caseId": "CASE-ABC-1001",

        "country": "Saudi Arabia",

        "riskRating": "Medium",

        "riskScore": 62,

        "kycStatus": "Approved",

        "onboardingStatus": "Active",

        "businessType":
            "Industrial Manufacturing",

        "annualRevenue":
            "USD 150 Million"
    },

    "XYZ Corp": {

        "customerId": "CUST-2026-002",
        "customerName": "XYZ Corp",
        "caseId": "CASE-XYZ-1001",

        "country": "UAE",

        "riskRating": "High",

        "riskScore": 88,

        "kycStatus": "Pending",

        "onboardingStatus": "Under Review",

        "businessType":
            "Financial Services",

        "annualRevenue":
            "USD 400 Million"
    }
}


def get_customer_risk_profile(
    customer_name: str,
    user_context: dict
) -> Dict[str, Any]:

    TOOL_NAME = "get_customer_risk_profile"
    logger.info(
        "MCP Tool get_customer_risk_profile called."
    )
    
    try:

        # ==================================================
        # TOOL GUARDRAIL CHECK
        # ==================================================
        from app.pbac import authorize_tool_access
        tool_decision = authorize_tool_access(
            user_role=user_context.get("userRole", "unknown"),
            agent_id=user_context.get("agentId", "unknown"),
            tool_name=TOOL_NAME
        )

        if tool_decision["decision"] != "PERMIT":

            return {

                "status": "DENIED",

                "toolGuardrail": "FAIL",

                "tool": TOOL_NAME,

                "timestamp":
                    datetime.utcnow().isoformat(),

                "reason":
                    tool_decision["reason"],

                "audit": {

                    "userId": user_context.get("userId", "unknown"),

                    "userRole": user_context.get("userRole", "unknown"),

                    "agentId": user_context.get("agentId", "unknown")
                }
            }

        # ==================================================
        # CUSTOMER LOOKUP
        # ==================================================

        customer = CUSTOMERS.get(
            customer_name
        )

        if not customer:

            return {

                "status": "NOT_FOUND",

                "toolGuardrail": "PASS",

                "tool": TOOL_NAME,

                "timestamp":
                    datetime.utcnow().isoformat(),

                "reason":
                    f"Customer not found: "
                    f"{customer_name}"
            }

        # ==================================================
        # SUCCESS
        # ==================================================

        return {

            "status": "SUCCESS",

            "toolGuardrail": "PASS",

            "tool": TOOL_NAME,

            "timestamp":
                datetime.utcnow().isoformat(),

            "data": {

                "customerId":
                    customer["customerId"],

                "customerName":
                    customer["customerName"],

                "country":
                    customer["country"],

                "caseId":
                    customer["caseId"],

                "riskRating":
                    customer["riskRating"],

                "riskScore":
                    customer["riskScore"],

                "kycStatus":
                    customer["kycStatus"],

                "onboardingStatus":
                    customer["onboardingStatus"],

                "businessType":
                    customer["businessType"],

                "annualRevenue":
                    customer["annualRevenue"]
            },

            "audit": {

                "userId": user_context.get("userId", "unknown"),

                "userRole": user_context.get("userRole", "unknown"),

                "agentId": user_context.get("agentId", "unknown")
            }
        }

    except Exception as ex:

        return {

            "status": "ERROR",

            "toolGuardrail": "FAIL",

            "tool": TOOL_NAME,

            "timestamp":
                datetime.utcnow().isoformat(),

            "reason": str(ex)
        }