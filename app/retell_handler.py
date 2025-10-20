"""
Retell AI Integration Handler

This module handles the integration between Retell AI voice platform and our
custom LangChain support agent.

Architecture:
    Retell AI (voice layer) ↔ This Handler ↔ Support Agent (reasoning)

Retell handles:
    - Voice-to-text (speech recognition)
    - Text-to-voice (speech synthesis)
    - Low latency conversation flow
    - Interruption handling

Our agent handles:
    - Autonomous reasoning
    - RAG knowledge retrieval
    - Tool execution (RADIUS)
    - Conversational memory

Communication:
    - Retell connects via WebSocket
    - Sends user messages and function call requests
    - Receives agent responses and function results
"""

import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from app.support_agent import SupportAgent
from app.radius_tools import (
    verify_customer,
    check_line_status,
    run_speed_test,
    reset_modem,
    change_wifi_password,
    change_wifi_channel
)

logger = logging.getLogger(__name__)


class RetellHandler:
    """
    Handles communication between Retell AI and our support agent.

    This class acts as a bridge, translating between:
    - Retell's WebSocket protocol
    - Our agent's Python API

    Why a handler class?
    - Encapsulates Retell-specific logic
    - Maintains conversation state per call
    - Makes it easy to swap voice providers if needed
    - Cleaner separation of concerns
    """

    def __init__(self, agent: SupportAgent):
        """
        Initialize the Retell handler.

        Args:
            agent: The SupportAgent instance to use for reasoning
        """
        self.agent = agent
        self.call_id: Optional[str] = None
        self.customer_id: Optional[str] = None
        self.call_start_time: Optional[datetime] = None

        # Map function names to actual tool implementations
        # Retell will call these by name via function calling
        self.available_functions = {
            "verify_customer": verify_customer,
            "check_line_status": check_line_status,
            "run_speed_test": run_speed_test,
            "reset_modem": reset_modem,
            "change_wifi_password": change_wifi_password,
            "change_wifi_channel": change_wifi_channel
        }

    def start_call(self, call_id: str):
        """
        Initialize a new call session.

        Called when Retell starts a new conversation.

        Args:
            call_id: Unique identifier for this call
        """
        self.call_id = call_id
        self.call_start_time = datetime.now()
        self.agent.reset_conversation()
        logger.info(f"Started call {call_id}")

    def end_call(self):
        """
        Clean up call session.

        Called when the conversation ends (user hangs up or escalation).
        """
        if self.call_start_time:
            duration = (datetime.now() - self.call_start_time).seconds
            logger.info(f"Ended call {self.call_id}, duration: {duration}s")

        self.call_id = None
        self.customer_id = None
        self.call_start_time = None
        self.agent.reset_conversation()

    async def process_user_message(self, message: str) -> str:
        """
        Process a user message from Retell.

        Flow:
        1. User speaks → Retell transcribes → sends text here
        2. We pass to agent (which uses RAG + reasoning)
        3. Agent returns response
        4. We send back to Retell → Retell speaks it

        Args:
            message: User's transcribed speech

        Returns:
            Agent's response text (Retell will speak this)
        """
        logger.info(f"User message: {message}")

        try:
            # Let the agent process with full RAG + reasoning
            response = self.agent.process_message(message)

            logger.info(f"Agent response: {response}")
            return response

        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            # Graceful degradation - don't crash the call
            return "Mi dispiace, ho avuto un problema tecnico. Può ripetere?"

    async def execute_function(self, function_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool/function requested by Retell.

        Flow:
        1. Agent decides it needs a tool (e.g., check_line_status)
        2. Retell sends function call request here
        3. We execute the actual tool
        4. Return result to Retell
        5. Retell gives result to agent, agent continues reasoning

        Args:
            function_name: Name of the tool to execute
            arguments: Arguments for the tool

        Returns:
            Tool execution result

        Example:
            function_name = "check_line_status"
            arguments = {"customer_id": "CL123456"}
            → executes check_line_status("CL123456")
            → returns line status data
        """
        logger.info(f"Function call: {function_name}({arguments})")

        if function_name not in self.available_functions:
            logger.error(f"Unknown function: {function_name}")
            return {
                "status": "error",
                "message": f"Function {function_name} not found"
            }

        try:
            # Get the actual function
            func = self.available_functions[function_name]

            # Execute it
            # Note: LangChain tools expect specific arg format
            if function_name == "verify_customer":
                result = func.invoke({"identifier": arguments.get("identifier")})
            elif function_name in ["check_line_status", "run_speed_test", "reset_modem"]:
                result = func.invoke({"customer_id": arguments.get("customer_id")})
            elif function_name == "change_wifi_password":
                result = func.invoke({
                    "customer_id": arguments.get("customer_id"),
                    "new_password": arguments.get("new_password")
                })
            elif function_name == "change_wifi_channel":
                result = func.invoke({
                    "customer_id": arguments.get("customer_id"),
                    "channel": arguments.get("channel")
                })

            # Store customer_id if this was verification
            if function_name == "verify_customer" and result.get("found"):
                self.customer_id = result.get("customer_id")
                self.agent.set_customer_id(self.customer_id)

            logger.info(f"Function result: {result}")
            return result

        except Exception as e:
            logger.error(f"Error executing function {function_name}: {e}", exc_info=True)
            return {
                "status": "error",
                "message": str(e)
            }

    def get_initial_greeting(self) -> str:
        """
        Get the initial greeting when call starts.

        This is what the agent says first when the call connects.

        Returns:
            Opening message
        """
        return "Buongiorno, sono l'assistente virtuale del supporto tecnico. Per iniziare, può fornirmi il suo codice cliente o il numero di telefono dell'utenza?"

    def should_escalate(self, message: str) -> bool:
        """
        Determine if the conversation should be escalated to human.

        Escalation triggers:
        - User explicitly asks for human operator
        - Conversation going in circles (not implemented yet)
        - Problem not resolvable by agent

        Args:
            message: Latest message or context

        Returns:
            True if should transfer to human
        """
        # Simple keyword detection
        # In production, this would be more sophisticated
        escalation_keywords = [
            "operatore",
            "operatore umano",
            "persona vera",
            "parlare con una persona",
            "non funziona",
            "voglio un tecnico"
        ]

        message_lower = message.lower()

        # Check for explicit requests
        for keyword in escalation_keywords:
            if keyword in message_lower:
                # Additional context check to avoid false positives
                if "voglio" in message_lower or "parlare" in message_lower:
                    return True

        return False

    def get_escalation_message(self) -> str:
        """
        Get message to say when escalating.

        Returns:
            Escalation message
        """
        return "Capisco, la metto in contatto con un operatore specializzato che potrà assisterla meglio. Un momento per favore."

    def get_call_summary(self) -> Dict[str, Any]:
        """
        Get summary of the call for logging/analytics.

        Useful for:
        - Post-call analysis
        - Training data
        - Quality monitoring
        - Handoff to human operator (context)

        Returns:
            Dictionary with call details
        """
        duration = None
        if self.call_start_time:
            duration = (datetime.now() - self.call_start_time).seconds

        conversation_history = self.agent.get_conversation_history()

        return {
            "call_id": self.call_id,
            "customer_id": self.customer_id,
            "duration_seconds": duration,
            "message_count": len(conversation_history),
            "conversation": [
                {
                    "role": msg.type,
                    "content": msg.content[:200]  # Truncate for logging
                }
                for msg in conversation_history
            ]
        }


def create_retell_function_definitions() -> List[Dict[str, Any]]:
    """
    Create function definitions for Retell AI agent configuration.

    These tell Retell what tools are available and when to use them.
    Retell's LLM will decide when to call these based on the conversation.

    Returns:
        List of function definition dictionaries in Retell format

    Note:
        These definitions should be configured in Retell dashboard.
        This function provides the JSON structure to copy-paste.
    """
    return [
        {
            "name": "verify_customer",
            "description": "Verify customer identity and retrieve account information. MUST be called first before any troubleshooting.",
            "parameters": {
                "type": "object",
                "properties": {
                    "identifier": {
                        "type": "string",
                        "description": "Customer code (CL######), phone number, or tax code"
                    }
                },
                "required": ["identifier"]
            }
        },
        {
            "name": "check_line_status",
            "description": "Check internet line status, signal quality, and connection statistics. Use when customer reports connectivity issues.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "Customer ID from verify_customer"
                    }
                },
                "required": ["customer_id"]
            }
        },
        {
            "name": "run_speed_test",
            "description": "Run a speed test on customer's line. Use when customer reports slow internet.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "Customer ID from verify_customer"
                    }
                },
                "required": ["customer_id"]
            }
        },
        {
            "name": "reset_modem",
            "description": "Remotely reset/reboot customer's modem. ALWAYS warn customer first that internet will drop for 2-3 minutes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "Customer ID from verify_customer"
                    }
                },
                "required": ["customer_id"]
            }
        },
        {
            "name": "change_wifi_password",
            "description": "Change customer's WiFi password. Use when customer forgot password or wants to change it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "Customer ID from verify_customer"
                    },
                    "new_password": {
                        "type": "string",
                        "description": "New WiFi password (min 8 characters)"
                    }
                },
                "required": ["customer_id", "new_password"]
            }
        },
        {
            "name": "change_wifi_channel",
            "description": "Change WiFi channel to reduce interference. Use when customer has weak WiFi signal in crowded area.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "Customer ID from verify_customer"
                    },
                    "channel": {
                        "type": "integer",
                        "description": "WiFi channel (recommended: 1, 6, or 11 for 2.4GHz)"
                    }
                },
                "required": ["customer_id", "channel"]
            }
        }
    ]
