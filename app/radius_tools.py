"""
RADIUS Client Tools for LangChain Agent

This module implements the backend system integration tools that the AI agent
can use to interact with telecommunications infrastructure.

In production, these would connect to real RADIUS/AAA servers.
For this demo, we simulate realistic responses with an in-memory database.
"""

import random
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from langchain.tools import tool


# Mock customer database
# In production, this would be fetched from actual database/RADIUS
MOCK_CUSTOMERS = {
    "CL123456": {
        "customer_id": "CL123456",
        "name": "Mario Rossi",
        "phone": "3331234567",
        "tax_code": "RSSMRA80A01F205X",
        "contract_type": "FTTH",
        "contract_speed": 1000,  # Mbps
        "status": "active",
        "line_status": "active",
        "signal_quality": 85,
        "downstream_speed": 950,
        "upstream_speed": 290,
        "last_sync": datetime.now() - timedelta(hours=2),
        "modem_model": "TIM HUB+",
        "connection_drops_24h": 0
    },
    "CL789012": {
        "customer_id": "CL789012",
        "name": "Laura Bianchi",
        "phone": "3339876543",
        "tax_code": "BNCLRA85M42F839Y",
        "contract_type": "FTTC",
        "contract_speed": 200,
        "status": "active",
        "line_status": "degraded",
        "signal_quality": 45,
        "downstream_speed": 85,
        "upstream_speed": 18,
        "last_sync": datetime.now() - timedelta(hours=6),
        "modem_model": "Technicolor",
        "connection_drops_24h": 12
    },
    "3331234567": {  # Can search by phone too
        "customer_id": "CL123456",
        "name": "Mario Rossi",
        "phone": "3331234567",
        "tax_code": "RSSMRA80A01F205X",
        "contract_type": "FTTH",
        "contract_speed": 1000,
        "status": "active",
        "line_status": "active",
        "signal_quality": 85,
        "downstream_speed": 950,
        "upstream_speed": 290,
        "last_sync": datetime.now() - timedelta(hours=2),
        "modem_model": "TIM HUB+",
        "connection_drops_24h": 0
    }
}


@tool
def verify_customer(identifier: str) -> Dict[str, Any]:
    """
    Verify customer identity and retrieve account information.

    This tool MUST be called as the first action in every conversation
    to identify the customer before any troubleshooting can begin.

    Args:
        identifier: Customer code (CL######), phone number, or tax code

    Returns:
        Dictionary with customer information if found, or error if not found

    Example:
        result = verify_customer("CL123456")
        if result["found"]:
            customer_id = result["customer_id"]
            # Use customer_id for all subsequent tool calls
    """
    customer = MOCK_CUSTOMERS.get(identifier)

    if not customer:
        return {
            "found": False,
            "message": f"No customer found with identifier: {identifier}"
        }

    return {
        "found": True,
        "customer_id": customer["customer_id"],
        "name": customer["name"],
        "contract_type": customer["contract_type"],
        "contract_speed": customer["contract_speed"],
        "status": customer["status"],
        "message": f"Customer {customer['name']} verified successfully"
    }


@tool
def check_line_status(customer_id: str) -> Dict[str, Any]:
    """
    Check the current status and quality of the customer's internet line.

    Use this tool when:
    - Customer reports no internet connection
    - Need to diagnose connection quality issues
    - Investigating slow speed problems
    - Modem lights indicate line problems

    Args:
        customer_id: The customer ID (obtained from verify_customer)

    Returns:
        Dictionary with detailed line diagnostics including:
        - line_status: "active", "down", or "degraded"
        - signal_quality: 0-100% (higher is better)
        - speeds: actual downstream/upstream Mbps
        - connection_drops_24h: number of disconnections in last 24 hours
        - last_sync: when modem last synchronized

    Interpretation:
        - signal_quality >80%: Excellent
        - signal_quality 60-80%: Good but may affect performance
        - signal_quality <60%: Poor, likely causing issues
        - connection_drops >10: Unstable line, escalate
    """
    customer = MOCK_CUSTOMERS.get(customer_id)

    if not customer:
        return {
            "status": "error",
            "message": f"Customer {customer_id} not found"
        }

    # Simulate some variance in readings
    signal_variance = random.randint(-5, 5)
    signal_quality = max(0, min(100, customer["signal_quality"] + signal_variance))

    return {
        "status": "success",
        "line_status": customer["line_status"],
        "signal_quality": signal_quality,
        "downstream_speed": customer["downstream_speed"],
        "upstream_speed": customer["upstream_speed"],
        "contract_speed": customer["contract_speed"],
        "connection_drops_24h": customer["connection_drops_24h"],
        "last_sync": customer["last_sync"].isoformat(),
        "modem_model": customer["modem_model"]
    }


@tool
def run_speed_test(customer_id: str) -> Dict[str, Any]:
    """
    Run a remote speed test on the customer's line.

    Use this tool when:
    - Customer complains about slow speed
    - Need to verify actual vs contracted speed
    - After fixing a problem to confirm resolution

    Args:
        customer_id: The customer ID (obtained from verify_customer)

    Returns:
        Dictionary with speed test results:
        - download_speed: Mbps download
        - upload_speed: Mbps upload
        - latency: milliseconds (ping)
        - jitter: latency variation
        - contract_speed: expected speed for comparison

    Interpretation:
        - Speed 80-100% of contract: Good
        - Speed 50-80% of contract: Acceptable but investigate
        - Speed <50% of contract: Problem, investigate further
        - Latency <20ms: Excellent, <50ms: Good, >100ms: Poor
    """
    customer = MOCK_CUSTOMERS.get(customer_id)

    if not customer:
        return {
            "status": "error",
            "message": f"Customer {customer_id} not found"
        }

    # Simulate realistic speed test with some variance
    download_variance = random.uniform(0.9, 1.0)
    upload_variance = random.uniform(0.9, 1.0)

    download_speed = round(customer["downstream_speed"] * download_variance, 2)
    upload_speed = round(customer["upstream_speed"] * upload_variance, 2)
    latency = random.randint(10, 30) if customer["signal_quality"] > 70 else random.randint(50, 150)
    jitter = random.randint(1, 5) if customer["signal_quality"] > 70 else random.randint(10, 30)

    return {
        "status": "success",
        "download_speed": download_speed,
        "upload_speed": upload_speed,
        "contract_speed": customer["contract_speed"],
        "latency": latency,
        "jitter": jitter,
        "test_timestamp": datetime.now().isoformat()
    }


@tool
def reset_modem(customer_id: str) -> Dict[str, Any]:
    """
    Remotely reset (reboot) the customer's modem.

    Use this tool when:
    - Line is active but modem not synchronizing properly
    - After physical checks (cables) have been done
    - Signal quality is degraded but line is up
    - As troubleshooting step before escalation

    IMPORTANT: Always warn the customer BEFORE using this tool that:
    - Internet will drop for 2-3 minutes
    - Any ongoing downloads/calls will be interrupted
    - They should wait for modem to fully restart

    Args:
        customer_id: The customer ID (obtained from verify_customer)

    Returns:
        Dictionary with reset status and estimated recovery time
    """
    customer = MOCK_CUSTOMERS.get(customer_id)

    if not customer:
        return {
            "status": "error",
            "message": f"Customer {customer_id} not found"
        }

    # Simulate modem reset
    # In real implementation, this would send command to RADIUS/TR-069
    customer["last_sync"] = datetime.now()
    customer["connection_drops_24h"] = 0

    # Simulate potential signal quality improvement
    if customer["signal_quality"] < 80:
        customer["signal_quality"] = min(85, customer["signal_quality"] + random.randint(5, 15))

    return {
        "status": "success",
        "message": "Modem reset command sent successfully",
        "estimated_recovery_time": 120,  # seconds
        "next_action": "Wait 2-3 minutes for modem to complete restart and resynchronization"
    }


@tool
def change_wifi_password(customer_id: str, new_password: str) -> Dict[str, Any]:
    """
    Change the customer's WiFi password.

    Use this tool when:
    - Customer has forgotten WiFi password
    - Customer wants custom password instead of default
    - Security concern (password compromised)

    Password requirements:
    - Minimum 8 characters
    - Mix of letters and numbers recommended

    Args:
        customer_id: The customer ID (obtained from verify_customer)
        new_password: The new WiFi password to set

    Returns:
        Dictionary with operation result
    """
    customer = MOCK_CUSTOMERS.get(customer_id)

    if not customer:
        return {
            "status": "error",
            "message": f"Customer {customer_id} not found"
        }

    if len(new_password) < 8:
        return {
            "status": "error",
            "message": "Password must be at least 8 characters long"
        }

    return {
        "status": "success",
        "message": f"WiFi password changed successfully to: {new_password}",
        "next_action": "Customer needs to reconnect all devices with the new password"
    }


@tool
def change_wifi_channel(customer_id: str, channel: int) -> Dict[str, Any]:
    """
    Change the WiFi channel to reduce interference.

    Use this tool when:
    - Customer has weak WiFi signal in area with many networks
    - Frequent WiFi disconnections
    - After confirming the issue is interference, not distance

    Recommended channels:
    - 2.4GHz: 1, 6, or 11 (non-overlapping)
    - 5GHz: Usually auto is fine (less crowded)

    Args:
        customer_id: The customer ID (obtained from verify_customer)
        channel: The WiFi channel number (1, 6, or 11 for 2.4GHz)

    Returns:
        Dictionary with operation result
    """
    customer = MOCK_CUSTOMERS.get(customer_id)

    if not customer:
        return {
            "status": "error",
            "message": f"Customer {customer_id} not found"
        }

    if channel not in [1, 6, 11]:
        return {
            "status": "warning",
            "message": f"Channel {channel} set, but recommended channels are 1, 6, or 11 for optimal performance"
        }

    return {
        "status": "success",
        "message": f"WiFi channel changed to {channel}",
        "next_action": "WiFi devices should reconnect automatically. Signal quality should improve within 1-2 minutes."
    }


# Export all tools as a list for LangChain agent
ALL_TOOLS = [
    verify_customer,
    check_line_status,
    run_speed_test,
    reset_modem,
    change_wifi_password,
    change_wifi_channel
]
