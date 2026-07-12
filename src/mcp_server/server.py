from __future__ import annotations

import asyncio
import sys
from contextlib import asynccontextmanager

from mcp.server import Server
from mcp.server.fastmcp import FastMCP
from mcp.types import Tool
from typing import Optional, Dict, Any

from .tools import add_numbers, explain_text, get_utc_time, get_customer_risk_profile
import logging

logger = logging.getLogger(__name__)

logger.info(
    "MCP Server initialized.",
    flush=True
)

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


@mcp.tool()
def get_customer_risk_profile_tool(
    customer_name: str,
    user_context: dict
) -> Dict[str, Any]:
    """Retrieve customer risk profile with PBAC enforcement."""
    return get_customer_risk_profile(
        customer_name=customer_name,
        user_context=user_context
    )

def run() -> None:
    """Run MCP server with stdio transport for robustness."""
    # Silently run stdio transport; all output must be JSONRPC for client parsing
    mcp.run(transport="stdio")






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
    from app.pbac import authorize_tool_access
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
