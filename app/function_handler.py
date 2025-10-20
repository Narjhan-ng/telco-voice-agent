"""
Function Handler - Smart Routing per Low Latency

Questo modulo implementa la logica di routing intelligente tra:
- Quick tools: esecuzione diretta, latency <500ms
- Complex reasoning: agent con RAG, latency 2-3s

Perché questa distinzione?
- Conversazione fluida richiede risposte veloci
- Non serve RAG+reasoning per ogni tool
- Solo diagnosi complesse necessitano agent completo

Decision Logic:
- verify_customer: QUICK (lookup semplice)
- reset_modem: QUICK (comando semplice)
- check_line_status: COMPLEX se serve interpretazione
- diagnose_problem: COMPLEX (sempre agent + RAG)
"""

import logging
from typing import Dict, Any, Optional, Callable
from enum import Enum

from app.radius_tools import (
    verify_customer,
    check_line_status,
    run_speed_test,
    reset_modem,
    change_wifi_password,
    change_wifi_channel
)

logger = logging.getLogger(__name__)


class ExecutionMode(Enum):
    """
    Modalità di esecuzione function.

    QUICK: Tool eseguito direttamente, senza agent
    COMPLEX: Tool + Agent reasoning con RAG
    """
    QUICK = "quick"
    COMPLEX = "complex"


class FunctionHandler:
    """
    Gestisce l'esecuzione intelligente delle function calls.

    Routing logic:
    - Analizza la function richiesta
    - Decide se serve reasoning complesso
    - Esegue in modalità appropriata
    - Ritorna risultato ottimizzato per voice
    """

    def __init__(self, support_agent=None):
        """
        Inizializza function handler.

        Args:
            support_agent: Istanza SupportAgent per complex reasoning (opzionale)
        """
        self.support_agent = support_agent

        # Mapping function → execution mode
        self.function_modes = {
            "verify_customer": ExecutionMode.QUICK,
            "reset_modem": ExecutionMode.QUICK,
            "change_wifi_password": ExecutionMode.QUICK,
            "change_wifi_channel": ExecutionMode.QUICK,
            "check_line_status": ExecutionMode.COMPLEX,  # Serve interpretazione
            "run_speed_test": ExecutionMode.COMPLEX,     # Serve analisi risultati
            "diagnose_connection": ExecutionMode.COMPLEX,  # Full reasoning
            "complex_troubleshooting": ExecutionMode.COMPLEX  # Full reasoning
        }

        # Quick tools mapping
        self.quick_tools = {
            "verify_customer": verify_customer,
            "reset_modem": reset_modem,
            "change_wifi_password": change_wifi_password,
            "change_wifi_channel": change_wifi_channel
        }

    async def execute(
        self,
        function_name: str,
        arguments: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Esegue function in modalità appropriata (quick vs complex).

        Args:
            function_name: Nome function da eseguire
            arguments: Argomenti function
            context: Contesto conversazionale opzionale

        Returns:
            Risultato strutturato per voice response

        Flow:
        1. Determina execution mode
        2. Se QUICK → esegui tool diretto
        3. Se COMPLEX → usa agent con RAG
        4. Formatta risultato per voice
        """
        mode = self._get_execution_mode(function_name)

        logger.info(f"Executing {function_name} in {mode.value} mode")

        try:
            if mode == ExecutionMode.QUICK:
                result = await self._execute_quick(function_name, arguments)
            else:
                result = await self._execute_complex(function_name, arguments, context)

            # Formatta per voice output
            return self._format_for_voice(function_name, result)

        except Exception as e:
            logger.error(f"Error executing {function_name}: {e}", exc_info=True)
            return {
                "success": False,
                "message": "Si è verificato un errore. Riprovo...",
                "error": str(e)
            }

    def _get_execution_mode(self, function_name: str) -> ExecutionMode:
        """
        Determina execution mode per function.

        Args:
            function_name: Nome function

        Returns:
            ExecutionMode (QUICK o COMPLEX)
        """
        return self.function_modes.get(function_name, ExecutionMode.COMPLEX)

    async def _execute_quick(
        self,
        function_name: str,
        arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Esegui tool in quick mode (diretto, no agent).

        Latency target: <500ms

        Args:
            function_name: Nome tool
            arguments: Argomenti tool

        Returns:
            Tool result
        """
        if function_name not in self.quick_tools:
            raise ValueError(f"No quick tool found for {function_name}")

        tool = self.quick_tools[function_name]

        # Esegui tool direttamente
        # LangChain tools usano .invoke()
        result = tool.invoke(arguments)

        return result

    async def _execute_complex(
        self,
        function_name: str,
        arguments: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Esegui function con agent reasoning complesso.

        Latency target: 2-3s (accettabile per diagnosi)

        Flow:
        1. Costruisci prompt per agent con context
        2. Agent usa RAG per retrieve knowledge
        3. Agent esegue tools necessari
        4. Agent reasoning su risultati
        5. Return structured response

        Args:
            function_name: Nome function
            arguments: Argomenti
            context: Contesto conversazione

        Returns:
            Agent reasoning result
        """
        if not self.support_agent:
            # Fallback se agent non disponibile
            logger.warning("Complex mode requested but no agent available")
            return await self._execute_quick(function_name, arguments)

        # Costruisci prompt per agent
        prompt = self._build_agent_prompt(function_name, arguments, context)

        # Agent processa con RAG + reasoning
        response = self.support_agent.process_message(prompt)

        return {
            "success": True,
            "analysis": response,
            "function": function_name
        }

    def _build_agent_prompt(
        self,
        function_name: str,
        arguments: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Costruisce prompt per agent based on function type.

        Il prompt guida l'agent a:
        - Usare RAG per conoscenza rilevante
        - Eseguire tools necessari
        - Analizzare risultati
        - Fornire raccomandazioni

        Args:
            function_name: Nome function
            arguments: Argomenti
            context: Contesto conversazione

        Returns:
            Prompt ottimizzato per agent
        """
        customer_id = arguments.get("customer_id", "unknown")

        if function_name == "check_line_status":
            return f"""Analizza lo stato della linea per cliente {customer_id}.

Usa check_line_status per ottenere dati tecnici.
Interpreta i risultati:
- Signal quality: cosa significa?
- Connection drops: è un problema?
- Cosa consigliare al cliente?

Rispondi in modo chiaro per conversazione vocale."""

        elif function_name == "run_speed_test":
            return f"""Esegui speed test per cliente {customer_id} e analizza risultati.

Usa run_speed_test e confronta con velocità contrattuale.
Spiega al cliente in modo semplice se la velocità è corretta o no."""

        elif function_name == "diagnose_connection":
            problem_description = arguments.get("problem_description", "")
            return f"""Cliente {customer_id} riporta: "{problem_description}"

Diagnosi completa:
1. Usa knowledge base per scenari simili
2. Esegui check_line_status
3. Analizza risultati
4. Proponi soluzione o escalation

Rispondi per conversazione vocale, massimo 3-4 frasi."""

        elif function_name == "complex_troubleshooting":
            issue_type = arguments.get("issue_type", "generic")
            details = arguments.get("details", "")

            return f"""Troubleshooting complesso per cliente {customer_id}.
Tipo problema: {issue_type}
Dettagli: {details}

Usa tutti i tools e knowledge base necessari per diagnosi approfondita.
Fornisci raccomandazione chiara."""

        else:
            # Generic complex task
            return f"Esegui {function_name} per cliente {customer_id} con argomenti: {arguments}"

    def _format_for_voice(
        self,
        function_name: str,
        result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Formatta risultato tool per voice output.

        Perché necessario?
        - Tool results sono tecnici/strutturati
        - Voice needs natural language
        - Serve conversione human-friendly

        Args:
            function_name: Nome function eseguita
            result: Raw result da tool/agent

        Returns:
            Formatted result con message per voice
        """
        if not result.get("success", True):
            # Error case
            return {
                "success": False,
                "message": result.get("message", "Operazione non riuscita"),
                "raw_result": result
            }

        # Format based on function type
        if function_name == "verify_customer":
            if result.get("found"):
                name = result.get("name", "")
                return {
                    "success": True,
                    "message": f"Cliente verificato: {name}",
                    "customer_id": result.get("customer_id"),
                    "raw_result": result
                }
            else:
                return {
                    "success": False,
                    "message": "Cliente non trovato. Può ripetere il codice?",
                    "raw_result": result
                }

        elif function_name == "reset_modem":
            return {
                "success": True,
                "message": "Modem in fase di riavvio. Attenda 2-3 minuti per il ripristino.",
                "raw_result": result
            }

        elif function_name == "check_line_status":
            # Se c'è analisi da agent, usala
            if "analysis" in result:
                return {
                    "success": True,
                    "message": result["analysis"],
                    "raw_result": result
                }
            # Altrimenti formatting semplice
            signal = result.get("signal_quality", 0)
            if signal > 80:
                message = f"Linea in ottime condizioni. Qualità segnale al {signal}%."
            elif signal > 60:
                message = f"Linea accettabile con qualità al {signal}%. Possibile lieve degrado."
            else:
                message = f"Rilevato problema sulla linea. Qualità segnale bassa al {signal}%."

            return {
                "success": True,
                "message": message,
                "raw_result": result
            }

        elif function_name == "run_speed_test":
            if "analysis" in result:
                return {
                    "success": True,
                    "message": result["analysis"],
                    "raw_result": result
                }

            download = result.get("download_speed", 0)
            contract = result.get("contract_speed", 100)
            percentage = (download / contract * 100) if contract > 0 else 0

            if percentage > 80:
                message = f"Velocità corretta: {download} Mbps, in linea con il contratto."
            else:
                message = f"Velocità ridotta: {download} Mbps invece di {contract} attesi."

            return {
                "success": True,
                "message": message,
                "raw_result": result
            }

        else:
            # Generic formatting
            if "analysis" in result:
                message = result["analysis"]
            elif "message" in result:
                message = result["message"]
            else:
                message = "Operazione completata."

            return {
                "success": True,
                "message": message,
                "raw_result": result
            }


# Helper per creare function definitions OpenAI Realtime format
def create_realtime_function_definitions() -> list:
    """
    Crea function definitions per OpenAI Realtime API.

    Queste sono le function che Realtime API può chiamare.
    L'API decide autonomamente quando chiamarle based on conversation.

    Returns:
        Lista function definitions in formato OpenAI
    """
    return [
        {
            "name": "verify_customer",
            "description": "Verify customer identity. ALWAYS call this FIRST before any other function.",
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
            "name": "diagnose_connection",
            "description": "Diagnose internet connection problems. Use when customer reports connectivity issues. This will check line status, analyze problems, and suggest solutions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "Customer ID from verify_customer"
                    },
                    "problem_description": {
                        "type": "string",
                        "description": "Brief description of the connection problem"
                    }
                },
                "required": ["customer_id", "problem_description"]
            }
        },
        {
            "name": "check_line_status",
            "description": "Check detailed line status and quality metrics. Use for technical diagnostics.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "Customer ID"
                    }
                },
                "required": ["customer_id"]
            }
        },
        {
            "name": "run_speed_test",
            "description": "Run speed test on customer line. Use when customer complains about slow internet.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "Customer ID"
                    }
                },
                "required": ["customer_id"]
            }
        },
        {
            "name": "reset_modem",
            "description": "Remotely reset customer modem. ALWAYS warn customer that internet will drop for 2-3 minutes BEFORE calling this.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "Customer ID"
                    }
                },
                "required": ["customer_id"]
            }
        },
        {
            "name": "change_wifi_password",
            "description": "Change WiFi password. Use when customer forgot password or wants to change it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string"
                    },
                    "new_password": {
                        "type": "string",
                        "description": "New password, minimum 8 characters"
                    }
                },
                "required": ["customer_id", "new_password"]
            }
        }
    ]
