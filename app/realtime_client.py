"""
OpenAI Realtime API Client

Questo modulo gestisce la connessione WebSocket con OpenAI Realtime API.

Responsabilità:
- Connessione e autenticazione con Realtime API
- Invio/ricezione messaggi audio e events
- Gestione function calling
- Error handling e reconnection
- Audio streaming bidirezionale

Protocollo OpenAI Realtime API:
- WebSocket connection a wss://api.openai.com/v1/realtime
- Eventi: session.update, conversation.item.create, response.create, etc.
- Audio: base64-encoded PCM16 24kHz mono
- Function calling: integrato nel protocollo
"""

import os
import json
import asyncio
import logging
import base64
from typing import Dict, Any, Optional, Callable
from enum import Enum

import websockets
from websockets.client import WebSocketClientProtocol

logger = logging.getLogger(__name__)


class RealtimeEventType(Enum):
    """
    Tipi di eventi Realtime API.

    Eventi principali:
    - session.update: configura sessione
    - input_audio_buffer.append: invia audio user
    - response.create: richiedi response AI
    - conversation.item.created: nuovo messaggio
    - response.audio.delta: chunk audio AI
    - response.function_call_arguments.done: function call da eseguire
    """
    SESSION_UPDATE = "session.update"
    INPUT_AUDIO_APPEND = "input_audio_buffer.append"
    INPUT_AUDIO_COMMIT = "input_audio_buffer.commit"
    RESPONSE_CREATE = "response.create"
    RESPONSE_CANCEL = "response.cancel"
    CONVERSATION_ITEM_CREATE = "conversation.item.create"


class RealtimeClient:
    """
    Client per OpenAI Realtime API.

    Gestisce connessione WebSocket e protocollo eventi.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-realtime-preview-2024-10-01",
        voice: str = "alloy",
        function_handler: Optional[Callable] = None
    ):
        """
        Inizializza Realtime client.

        Args:
            api_key: OpenAI API key
            model: Realtime model name
            voice: Voice ID (alloy, echo, fable, onyx, nova, shimmer)
            function_handler: Callback per function calls
        """
        self.api_key = api_key
        self.model = model
        self.voice = voice
        self.function_handler = function_handler

        self.ws: Optional[WebSocketClientProtocol] = None
        self.connected = False
        self.session_id: Optional[str] = None

        # Callbacks per eventi
        self.on_audio_delta: Optional[Callable] = None
        self.on_transcript: Optional[Callable] = None
        self.on_error: Optional[Callable] = None

    async def connect(self):
        """
        Connette a OpenAI Realtime API.

        WebSocket URL: wss://api.openai.com/v1/realtime
        Headers: Authorization + OpenAI-Beta
        """
        url = "wss://api.openai.com/v1/realtime"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "OpenAI-Beta": "realtime=v1"
        }

        params = f"?model={self.model}"

        try:
            logger.info(f"Connecting to Realtime API: {url}{params}")

            self.ws = await websockets.connect(
                f"{url}{params}",
                extra_headers=headers,
                ping_interval=20,
                ping_timeout=10
            )

            self.connected = True
            logger.info("Connected to Realtime API")

            # Configura sessione
            await self._configure_session()

        except Exception as e:
            logger.error(f"Connection failed: {e}", exc_info=True)
            self.connected = False
            raise

    async def _configure_session(self):
        """
        Configura sessione Realtime API.

        Invia session.update con:
        - Voice settings
        - Turn detection (quando l'user finisce di parlare)
        - Function definitions
        - Instructions (system prompt)
        """
        from app.function_handler import create_realtime_function_definitions

        config = {
            "type": "session.update",
            "session": {
                "modalities": ["text", "audio"],
                "voice": self.voice,
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "input_audio_transcription": {
                    "model": "whisper-1"
                },
                "turn_detection": {
                    "type": "server_vad",  # Voice Activity Detection
                    "threshold": 0.5,
                    "prefix_padding_ms": 300,
                    "silence_duration_ms": 500
                },
                "tools": create_realtime_function_definitions(),
                "tool_choice": "auto",
                "temperature": 0.8,
                "max_response_output_tokens": 4096,
                "instructions": self._get_system_instructions()
            }
        }

        await self._send_event(config)
        logger.info("Session configured")

    def _get_system_instructions(self) -> str:
        """
        System instructions per Realtime API.

        Definisce comportamento agente:
        - Tono e stile
        - Quando usare functions
        - Come gestire conversazione

        Returns:
            System prompt string
        """
        return """Sei un assistente virtuale per supporto tecnico telecomunicazioni.

RUOLO:
- Aiuti clienti con problemi internet, WiFi, connessione
- Tono professionale ma cordiale
- Risposte BREVI (conversazione vocale, max 2-3 frasi)
- Parli in ITALIANO

WORKFLOW OBBLIGATORIO:
1. SEMPRE come prima cosa: verifica cliente con verify_customer()
2. Ascolta il problema
3. Usa functions appropriate per diagnosi
4. Proponi soluzione o escalation

FUNCTIONS DISPONIBILI:
- verify_customer: SEMPRE prima di tutto
- diagnose_connection: per problemi connessione (usa quando non sai causa)
- check_line_status: controllo tecnico linea
- run_speed_test: test velocità
- reset_modem: riavvio modem (AVVISA prima che internet cadrà 2-3 min!)
- change_wifi_password: cambio password WiFi

QUANDO USARE FUNCTIONS:
- User dice codice cliente → verify_customer()
- "Internet non funziona" → diagnose_connection()
- "Internet lento" → run_speed_test()
- Dopo aver verificato → reset_modem() se necessario

IMPORTANTE:
- BREVITÀ: max 2-3 frasi per risposta
- Mentre function lavora, di' "un momento, controllo..."
- Se user frustrato o problema persistente: proponi operatore umano
- Non fare supposizioni tecniche, usa functions per dati reali

STILE CONVERSAZIONE:
User: "Ciao"
Tu: "Buongiorno! Codice cliente o numero di telefono?"

User: "CL123456"
Tu: [usa verify_customer("CL123456")]
Tu: "Grazie Mario, come posso aiutarla?"

User: "Internet non va"
Tu: "Controllo subito la sua linea..." [usa diagnose_connection()]
"""

    async def _send_event(self, event: Dict[str, Any]):
        """
        Invia evento a Realtime API.

        Args:
            event: Event dictionary
        """
        if not self.ws or not self.connected:
            raise RuntimeError("Not connected")

        try:
            await self.ws.send(json.dumps(event))
            logger.debug(f"Sent event: {event.get('type')}")
        except Exception as e:
            logger.error(f"Error sending event: {e}", exc_info=True)
            raise

    async def send_audio(self, audio_data: bytes):
        """
        Invia audio chunk a Realtime API.

        Args:
            audio_data: PCM16 audio bytes (24kHz mono)
        """
        # Encode to base64
        audio_base64 = base64.b64encode(audio_data).decode('utf-8')

        event = {
            "type": "input_audio_buffer.append",
            "audio": audio_base64
        }

        await self._send_event(event)

    async def commit_audio(self):
        """
        Commit audio buffer e richiedi response.

        Dopo aver inviato audio chunks, commit triggera l'AI response.
        """
        # Commit audio buffer
        await self._send_event({
            "type": "input_audio_buffer.commit"
        })

        # Request response
        await self._send_event({
            "type": "response.create"
        })

    async def listen(self):
        """
        Ascolta eventi da Realtime API (loop principale).

        Eventi gestiti:
        - session.created: sessione iniziata
        - response.audio.delta: chunk audio da inviare a user
        - response.audio.transcript.done: trascrizione completa
        - response.function_call_arguments.done: function da eseguire
        - error: errori
        """
        if not self.ws or not self.connected:
            raise RuntimeError("Not connected")

        try:
            async for message in self.ws:
                event = json.loads(message)
                event_type = event.get("type")

                logger.debug(f"Received event: {event_type}")

                await self._handle_event(event)

        except websockets.exceptions.ConnectionClosed:
            logger.warning("WebSocket connection closed")
            self.connected = False
        except Exception as e:
            logger.error(f"Error in listen loop: {e}", exc_info=True)
            if self.on_error:
                await self.on_error(e)

    async def _handle_event(self, event: Dict[str, Any]):
        """
        Gestisce evento da Realtime API.

        Args:
            event: Event dictionary
        """
        event_type = event.get("type")

        if event_type == "session.created":
            self.session_id = event.get("session", {}).get("id")
            logger.info(f"Session created: {self.session_id}")

        elif event_type == "response.audio.delta":
            # Audio chunk da AI
            audio_base64 = event.get("delta")
            if audio_base64 and self.on_audio_delta:
                audio_bytes = base64.b64decode(audio_base64)
                await self.on_audio_delta(audio_bytes)

        elif event_type == "response.audio.transcript.done":
            # Trascrizione AI response
            transcript = event.get("transcript", "")
            if transcript and self.on_transcript:
                await self.on_transcript(transcript)

        elif event_type == "response.function_call_arguments.done":
            # Function call da eseguire
            await self._handle_function_call(event)

        elif event_type == "response.done":
            # Response completata
            logger.debug("Response completed")

        elif event_type == "error":
            error = event.get("error", {})
            logger.error(f"Realtime API error: {error}")
            if self.on_error:
                await self.on_error(error)

        elif event_type == "input_audio_buffer.speech_started":
            logger.debug("User started speaking")

        elif event_type == "input_audio_buffer.speech_stopped":
            logger.debug("User stopped speaking")

        # Altri eventi: log ma non gestiti specificamente
        else:
            logger.debug(f"Unhandled event type: {event_type}")

    async def _handle_function_call(self, event: Dict[str, Any]):
        """
        Gestisce function call da Realtime API.

        Flow:
        1. Realtime API decide di chiamare function
        2. Invia evento con function name e arguments
        3. Noi eseguiamo function (tramite FunctionHandler)
        4. Ritorniamo risultato a Realtime API
        5. Realtime API continua conversazione con risultato

        Args:
            event: Function call event
        """
        call_id = event.get("call_id")
        function_name = event.get("name")
        arguments_json = event.get("arguments", "{}")

        try:
            arguments = json.loads(arguments_json)
        except json.JSONDecodeError:
            logger.error(f"Invalid function arguments JSON: {arguments_json}")
            arguments = {}

        logger.info(f"Function call: {function_name}({arguments})")

        if not self.function_handler:
            logger.warning("No function handler configured")
            result = {"error": "Function handler not available"}
        else:
            # Esegui function tramite handler
            try:
                result = await self.function_handler(function_name, arguments)
            except Exception as e:
                logger.error(f"Function execution error: {e}", exc_info=True)
                result = {"error": str(e)}

        # Invia risultato a Realtime API
        await self._send_function_result(call_id, result)

    async def _send_function_result(self, call_id: str, result: Dict[str, Any]):
        """
        Invia risultato function call a Realtime API.

        Args:
            call_id: ID della function call
            result: Risultato function
        """
        event = {
            "type": "conversation.item.create",
            "item": {
                "type": "function_call_output",
                "call_id": call_id,
                "output": json.dumps(result)
            }
        }

        await self._send_event(event)

        # Richiedi nuova response con function result
        await self._send_event({
            "type": "response.create"
        })

    async def close(self):
        """
        Chiude connessione WebSocket.
        """
        if self.ws:
            await self.ws.close()
            self.connected = False
            logger.info("Connection closed")

    def set_audio_callback(self, callback: Callable):
        """
        Imposta callback per audio chunks da AI.

        Args:
            callback: async function(audio_bytes)
        """
        self.on_audio_delta = callback

    def set_transcript_callback(self, callback: Callable):
        """
        Imposta callback per trascrizioni.

        Args:
            callback: async function(transcript_text)
        """
        self.on_transcript = callback

    def set_error_callback(self, callback: Callable):
        """
        Imposta callback per errori.

        Args:
            callback: async function(error)
        """
        self.on_error = callback
