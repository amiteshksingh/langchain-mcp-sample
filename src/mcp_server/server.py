from __future__ import annotations

import asyncio
import sys
from contextlib import asynccontextmanager

from mcp.server import Server
from mcp.server.fastmcp import FastMCP
from mcp.types import Tool

from .tools import add_numbers, explain_text, get_utc_time

# FastMCP with explicit ServerSession
mcp = FastMCP("sample-tools")


@mcp.tool()
def add_numbers_tool(a: float, b: float) -> float:
    """Add two numbers and return the result."""
    return add_numbers(a, b)


@mcp.tool()
def get_utc_time_tool() -> str:
    """Return current UTC time in ISO-8601 format."""
    return get_utc_time()


@mcp.tool()
def explain_text_tool(text: str) -> str:
    """Prefix input text with 'Explain'."""
    return explain_text(text)


def run() -> None:
    """Run MCP server with stdio transport for robustness."""
    # Silently run stdio transport; all output must be JSONRPC for client parsing
    mcp.run(transport="stdio")


# -------------------------------------------------------------------
# Mock customer data
# In real implementation, this may call CRM, KYC platform, case system,
# risk engine, screening system, or customer master.
# -------------------------------------------------------------------
CUSTOMERS = {
    "ABC Corp": {
        "customerName": "ABC Corp",
        "customerId": "CUST-2026-001",
        "caseId": "CASE-ABC-1001",
        "riskRating": "Medium",
        "kycStatus": "Approved",
        "country": "Saudi Arabia",
        "primaryBusiness": "Industrial Manufacturing",
        "annualRevenue": "USD 150 Million",
        "beneficialOwner": "Amitesh K Singh",
        "nationalId": "1234567890",
    }
}


# -------------------------------------------------------------------
# Mock PBAC / PlainID-style decision.
#
# Replace this function later with actual PlainID PDP REST call.
# -------------------------------------------------------------------
def authorize_tool_access(
    user_role: str,
    agent_id: str,
    tool_name: str,
    customer_name: str,
    action: str,
):
    """
    Mock PBAC decision for MCP tool access.

    Decision model:
      Subject  = user_role + agent_id
      Action   = READ_RISK_PROFILE / READ_SENSITIVE_DETAILS
      Resource = Customer / KYC profile
      Context  = purpose = KYC_REVIEW
    """

    if tool_name == "get_customer_risk_profile":
        if user_role in ["KYC_ANALYST", "COMPLIANCE_OFFICER"]:
            return {
                "decision": "PERMIT",
                "obligations": ["audit"],
                "reason": "User role is allowed to access customer risk profile.",
            }

    if tool_name == "get_customer_sensitive_details":
        if user_role == "COMPLIANCE_OFFICER":
            return {
                "decision": "PERMIT",
                "obligations": ["audit"],
                "reason": "Compliance officer can view sensitive details.",
            }

        if user_role == "KYC_ANALYST":
            return {
                "decision": "PERMIT_WITH_OBLIGATIONS",
                "obligations": ["maskPII", "audit"],
                "reason": "KYC analyst can view sensitive details with masking.",
            }

    return {
        "decision": "DENY",
        "obligations": ["audit"],
        "reason": "User role is not authorized for this MCP tool/action.",
    }


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


@mcp.tool()
def get_customer_risk_profile(
    customer_name: str,
    user_role: str = "KYC_ANALYST",
    agent_id: str = "kyc-review-agent",
):
    """
    Retrieves customer risk profile for KYC review.

    This MCP tool demonstrates:
      - Agent calling a tool
      - Tool-level authorization
      - PBAC decision before returning customer data
    """

    tool_name = "get_customer_risk_profile"

    auth = authorize_tool_access(
        user_role=user_role,
        agent_id=agent_id,
        tool_name=tool_name,
        customer_name=customer_name,
        action="READ_RISK_PROFILE",
    )

    if auth["decision"] == "DENY":
        return {
            "status": "DENIED",
            "decision": auth,
            "message": "Access denied by PBAC policy.",
        }

    customer = CUSTOMERS.get(customer_name)

    if not customer:
        return {
            "status": "NOT_FOUND",
            "message": f"Customer not found: {customer_name}",
        }

    return {
        "status": "SUCCESS",
        "decision": auth,
        "data": {
            "customerName": customer["customerName"],
            "customerId": customer["customerId"],
            "caseId": customer["caseId"],
            "riskRating": customer["riskRating"],
            "kycStatus": customer["kycStatus"],
            "country": customer["country"],
            "primaryBusiness": customer["primaryBusiness"],
            "annualRevenue": customer["annualRevenue"],
        },
    }


@mcp.tool()
def get_customer_sensitive_details(
    customer_name: str,
    user_role: str = "KYC_ANALYST",
    agent_id: str = "kyc-review-agent",
):
    """
    Retrieves sensitive customer details.

    Demonstrates PERMIT_WITH_OBLIGATIONS:
      - Compliance Officer: full data
      - KYC Analyst: masked PII
      - Others: denied
    """

    tool_name = "get_customer_sensitive_details"

    auth = authorize_tool_access(
        user_role=user_role,
        agent_id=agent_id,
        tool_name=tool_name,
        customer_name=customer_name,
        action="READ_SENSITIVE_DETAILS",
    )

    if auth["decision"] == "DENY":
        return {
            "status": "DENIED",
            "decision": auth,
            "message": "Access denied by PBAC policy.",
        }

    customer = CUSTOMERS.get(customer_name)

    if not customer:
        return {
            "status": "NOT_FOUND",
            "message": f"Customer not found: {customer_name}",
        }

    beneficial_owner = customer["beneficialOwner"]
    national_id = customer["nationalId"]

    if "maskPII" in auth.get("obligations", []):
        beneficial_owner = mask_name(beneficial_owner)
        national_id = mask_national_id(national_id)

    return {
        "status": "SUCCESS",
        "decision": auth,
        "data": {
            "customerName": customer["customerName"],
            "beneficialOwner": beneficial_owner,
            "nationalId": national_id,
        },
    }


if __name__ == "__main__":
    run()
