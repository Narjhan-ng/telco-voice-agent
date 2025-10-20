"""
FastAPI Server for Voice Agent

Server principale che espone:
- WebSocket per browser client (voice streaming)
- REST endpoints per health check e config
- Bridge tra browser e OpenAI Realtime API
- Function execution tramite FunctionHandler

Architecture:
Browser ↔ WebSocket ↔ FastAPI ↔ Realtime API
                         ↓
                   FunctionHandler
                         ↓
                   Agent (quando complex)
"""

import os
import logging
import asyncio
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from app.support_agent import SupportAgent
from app.function_handler import FunctionHandler
from app.realtime_client import RealtimeClient

# Load environment
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Application lifecycle
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestisce startup e shutdown.
    """
    logger.info("🚀 Starting Voice Care Bot server...")

    # Verify OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY not set")

    logger.info("✅ Voice Care Bot ready")

    yield

    logger.info("👋 Shutting down...")


# Initialize FastAPI
app = FastAPI(
    title="Voice Care Bot",
    description="Autonomous AI support agent with voice interface",
    version="0.4.0",
    lifespan=lifespan
)

# CORS for browser testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files (per web UI)
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except RuntimeError:
    logger.warning("Static directory not found, skipping mount")


# Global instances (in production usare dependency injection)
_agent: Optional[SupportAgent] = None
_function_handler: Optional[FunctionHandler] = None


def get_agent() -> SupportAgent:
    """Get or create agent instance."""
    global _agent

    if _agent is None:
        api_key = os.getenv("OPENAI_API_KEY")
        model = os.getenv("AGENT_MODEL", "gpt-4")
        temperature = float(os.getenv("AGENT_TEMPERATURE", "0.1"))

        logger.info(f"Initializing agent with model: {model}")
        _agent = SupportAgent(api_key=api_key, model=model, temperature=temperature)

    return _agent


def get_function_handler() -> FunctionHandler:
    """Get or create function handler."""
    global _function_handler

    if _function_handler is None:
        agent = get_agent()
        _function_handler = FunctionHandler(support_agent=agent)

    return _function_handler


@app.get("/")
async def root():
    """Root endpoint - redirect to web UI."""
    return FileResponse("static/index.html") if os.path.exists("static/index.html") else {
        "service": "Voice Care Bot",
        "version": "0.4.0",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "voice_websocket": "/ws/voice",
            "test_ui": "/test"
        }
    }


@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    """
    try:
        agent = get_agent()

        return {
            "status": "healthy",
            "agent_ready": agent is not None,
            "model": os.getenv("AGENT_MODEL", "gpt-4"),
            "realtime_model": os.getenv("REALTIME_MODEL")
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/test")
async def test_ui():
    """
    Simple test UI HTML.
    """
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Voice Care Bot Test</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 800px;
                margin: 50px auto;
                padding: 20px;
                background: #f5f5f5;
            }
            .container {
                background: white;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            h1 {
                color: #333;
                text-align: center;
            }
            .status {
                padding: 15px;
                margin: 20px 0;
                border-radius: 5px;
                text-align: center;
                font-weight: bold;
            }
            .status.disconnected {
                background: #ffebee;
                color: #c62828;
            }
            .status.connected {
                background: #e8f5e9;
                color: #2e7d32;
            }
            button {
                width: 100%;
                padding: 15px;
                margin: 10px 0;
                font-size: 16px;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                font-weight: bold;
            }
            .start-btn {
                background: #4CAF50;
                color: white;
            }
            .start-btn:hover {
                background: #45a049;
            }
            .stop-btn {
                background: #f44336;
                color: white;
            }
            .stop-btn:hover {
                background: #da190b;
            }
            .stop-btn:disabled, .start-btn:disabled {
                opacity: 0.5;
                cursor: not-allowed;
            }
            .info {
                background: #e3f2fd;
                padding: 15px;
                border-radius: 5px;
                margin: 20px 0;
            }
            .transcript {
                margin-top: 20px;
                padding: 15px;
                background: #fafafa;
                border: 1px solid #e0e0e0;
                border-radius: 5px;
                max-height: 300px;
                overflow-y: auto;
            }
            .message {
                margin: 10px 0;
                padding: 10px;
                border-radius: 5px;
            }
            .user {
                background: #c8e6c9;
                text-align: right;
            }
            .assistant {
                background: #bbdefb;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎙️ Voice Care Bot</h1>

            <div class="status disconnected" id="status">
                Disconnesso
            </div>

            <div class="info">
                <strong>Istruzioni:</strong>
                <ol>
                    <li>Click "Inizia Conversazione"</li>
                    <li>Permetti l'accesso al microfono</li>
                    <li>Parla normalmente (italiano)</li>
                    <li>L'agente risponderà vocalmente</li>
                </ol>
                <p><strong>Codice test:</strong> CL123456 (Mario Rossi, linea ok)</p>
                <p><strong>Codice test 2:</strong> CL789012 (Laura Bianchi, linea degradata)</p>
            </div>

            <button class="start-btn" id="startBtn" onclick="startConversation()">
                Inizia Conversazione
            </button>

            <button class="stop-btn" id="stopBtn" onclick="stopConversation()" disabled>
                Termina Conversazione
            </button>

            <div class="transcript" id="transcript"></div>
        </div>

        <script>
            let ws = null;
            let mediaRecorder = null;
            let audioContext = null;
            let audioQueue = [];
            let isPlaying = false;

            function updateStatus(text, connected) {
                const status = document.getElementById('status');
                status.textContent = text;
                status.className = 'status ' + (connected ? 'connected' : 'disconnected');
            }

            function addMessage(role, content) {
                const transcript = document.getElementById('transcript');
                const message = document.createElement('div');
                message.className = 'message ' + role;
                message.textContent = (role === 'user' ? 'Tu: ' : 'Assistente: ') + content;
                transcript.appendChild(message);
                transcript.scrollTop = transcript.scrollHeight;
            }

            async function startConversation() {
                try {
                    updateStatus('Connessione in corso...', false);

                    // Initialize audio context
                    audioContext = new (window.AudioContext || window.webkitAudioContext)({
                        sampleRate: 24000
                    });

                    // Get microphone access
                    const stream = await navigator.mediaDevices.getUserMedia({
                        audio: {
                            sampleRate: 24000,
                            channelCount: 1,
                            echoCancellation: true,
                            noiseSuppression: true
                        }
                    });

                    // Connect WebSocket
                    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                    ws = new WebSocket(`${protocol}//${window.location.host}/ws/voice`);

                    ws.onopen = () => {
                        updateStatus('Connesso - Parla pure!', true);
                        document.getElementById('startBtn').disabled = true;
                        document.getElementById('stopBtn').disabled = false;
                        startRecording(stream);
                    };

                    ws.onmessage = async (event) => {
                        const data = JSON.parse(event.data);

                        if (data.type === 'audio') {
                            // Audio from AI - play it
                            const audioData = base64ToArrayBuffer(data.audio);
                            playAudio(audioData);
                        } else if (data.type === 'transcript') {
                            // Transcript from AI
                            addMessage('assistant', data.text);
                        } else if (data.type === 'user_transcript') {
                            // What user said
                            addMessage('user', data.text);
                        }
                    };

                    ws.onerror = (error) => {
                        console.error('WebSocket error:', error);
                        updateStatus('Errore connessione', false);
                    };

                    ws.onclose = () => {
                        updateStatus('Disconnesso', false);
                        document.getElementById('startBtn').disabled = false;
                        document.getElementById('stopBtn').disabled = true;
                        if (mediaRecorder && mediaRecorder.state === 'recording') {
                            mediaRecorder.stop();
                        }
                    };

                } catch (error) {
                    console.error('Error starting conversation:', error);
                    alert('Errore: ' + error.message);
                    updateStatus('Errore', false);
                }
            }

            function startRecording(stream) {
                // Create MediaRecorder for capturing audio
                mediaRecorder = new MediaRecorder(stream);

                mediaRecorder.ondataavailable = async (event) => {
                    if (event.data.size > 0 && ws && ws.readyState === WebSocket.OPEN) {
                        // Convert to PCM16 and send
                        const arrayBuffer = await event.data.arrayBuffer();
                        const audioData = await convertToPCM16(arrayBuffer);
                        const base64Audio = arrayBufferToBase64(audioData);

                        ws.send(JSON.stringify({
                            type: 'audio',
                            audio: base64Audio
                        }));
                    }
                };

                // Send audio chunks every 100ms
                mediaRecorder.start(100);
            }

            function stopConversation() {
                if (ws) {
                    ws.close();
                }
                if (mediaRecorder && mediaRecorder.state === 'recording') {
                    mediaRecorder.stop();
                }
                if (audioContext) {
                    audioContext.close();
                }
                updateStatus('Disconnesso', false);
            }

            async function convertToPCM16(arrayBuffer) {
                // Decode audio to AudioBuffer
                const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);

                // Get PCM data
                const pcmData = audioBuffer.getChannelData(0);

                // Convert float32 to int16
                const pcm16 = new Int16Array(pcmData.length);
                for (let i = 0; i < pcmData.length; i++) {
                    pcm16[i] = Math.max(-32768, Math.min(32767, Math.floor(pcmData[i] * 32768)));
                }

                return pcm16.buffer;
            }

            async function playAudio(arrayBuffer) {
                if (!audioContext) return;

                // Convert PCM16 to AudioBuffer
                const int16Array = new Int16Array(arrayBuffer);
                const float32Array = new Float32Array(int16Array.length);

                for (let i = 0; i < int16Array.length; i++) {
                    float32Array[i] = int16Array[i] / 32768.0;
                }

                const audioBuffer = audioContext.createBuffer(1, float32Array.length, 24000);
                audioBuffer.getChannelData(0).set(float32Array);

                const source = audioContext.createBufferSource();
                source.buffer = audioBuffer;
                source.connect(audioContext.destination);
                source.start();
            }

            function base64ToArrayBuffer(base64) {
                const binaryString = atob(base64);
                const bytes = new Uint8Array(binaryString.length);
                for (let i = 0; i < binaryString.length; i++) {
                    bytes[i] = binaryString.charCodeAt(i);
                }
                return bytes.buffer;
            }

            function arrayBufferToBase64(buffer) {
                const bytes = new Uint8Array(buffer);
                let binary = '';
                for (let i = 0; i < bytes.byteLength; i++) {
                    binary += String.fromCharCode(bytes[i]);
                }
                return btoa(binary);
            }
        </script>
    </body>
    </html>
    """

    return HTMLResponse(content=html_content)


@app.websocket("/ws/voice")
async def voice_websocket(websocket: WebSocket):
    """
    WebSocket endpoint per voice streaming.

    Flow:
    1. Browser si connette
    2. Inizializziamo Realtime API client
    3. Browser invia audio → forward a Realtime API
    4. Realtime API response audio → forward a browser
    5. Realtime API chiama functions → execute via FunctionHandler
    """
    await websocket.accept()
    logger.info("Browser WebSocket connected")

    realtime_client: Optional[RealtimeClient] = None
    function_handler = get_function_handler()

    try:
        # Initialize Realtime API client
        api_key = os.getenv("OPENAI_API_KEY")
        model = os.getenv("REALTIME_MODEL", "gpt-4o-realtime-preview-2024-10-01")
        voice = os.getenv("REALTIME_VOICE", "alloy")

        # Function handler callback
        async def handle_function_call(function_name: str, arguments: dict):
            """Execute function via FunctionHandler."""
            logger.info(f"Executing function: {function_name}")
            result = await function_handler.execute(function_name, arguments)
            return result

        realtime_client = RealtimeClient(
            api_key=api_key,
            model=model,
            voice=voice,
            function_handler=handle_function_call
        )

        # Setup callbacks
        async def on_audio_delta(audio_bytes: bytes):
            """Forward AI audio to browser."""
            import base64
            audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
            await websocket.send_json({
                "type": "audio",
                "audio": audio_base64
            })

        async def on_transcript(text: str):
            """Forward AI transcript to browser."""
            await websocket.send_json({
                "type": "transcript",
                "text": text
            })

        realtime_client.set_audio_callback(on_audio_delta)
        realtime_client.set_transcript_callback(on_transcript)

        # Connect to Realtime API
        await realtime_client.connect()

        # Start listening to Realtime API (background task)
        listen_task = asyncio.create_task(realtime_client.listen())

        # Forward audio from browser to Realtime API
        while True:
            data = await websocket.receive_json()

            if data.get("type") == "audio":
                # Audio from browser
                import base64
                audio_base64 = data.get("audio")
                audio_bytes = base64.b64decode(audio_base64)

                await realtime_client.send_audio(audio_bytes)

            elif data.get("type") == "commit":
                # User finished speaking, request response
                await realtime_client.commit_audio()

    except WebSocketDisconnect:
        logger.info("Browser WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
    finally:
        # Cleanup
        if realtime_client:
            await realtime_client.close()

        # Cancel listen task
        if 'listen_task' in locals():
            listen_task.cancel()


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("APP_PORT", "8000"))

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )
