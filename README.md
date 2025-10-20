# Voice Care Bot - Autonomous AI Support Agent

An intelligent voice-based customer support agent for telecommunications troubleshooting, powered by LangChain, RAG (Retrieval Augmented Generation), and autonomous decision-making.

## Overview

This project implements an AI agent that can autonomously handle technical support calls for internet connectivity issues. Unlike traditional chatbots with predefined decision trees, this agent:

- **Reasons autonomously** about customer problems using LLM-based decision making
- **Retrieves knowledge** from a technical documentation base via RAG
- **Uses tools** to interact with backend systems (RADIUS diagnostics, modem control)
- **Maintains conversation context** with memory
- **Decides when to escalate** to human operators

## Architecture

### Hybrid Low-Latency Design

```
Browser (Voice)
    ↓ WebSocket
FastAPI Server
    ↓ WebSocket
OpenAI Realtime API (GPT-4o voice-to-voice)
    ├─→ 80% Quick Conversation (<1s latency)
    └─→ 20% Complex Reasoning (2-3s with agent)
            ↓
        Function Handler (Smart Routing)
            ├─→ QUICK: Direct tool execution (<500ms)
            └─→ COMPLEX: Agent + RAG (2-3s)
                    ↓
                Support Agent (LangChain)
                    ├─→ RAG Knowledge Retrieval
                    ├─→ RADIUS Tools
                    └─→ Conversational Memory
```

**Why Hybrid?**
- Voice conversations demand low latency (<1s ideal)
- Realtime API handles 80% of conversation instantly
- Custom agent handles 20% complex diagnostics with deep reasoning
- Best of both: speed + intelligence

### Core Components

1. **Support Agent** (`app/support_agent.py`)
   - LangChain OpenAI Tools Agent with ReAct reasoning
   - Autonomous decision-making based on situation
   - Tool selection and execution
   - Conversational memory management

2. **RAG System** (`app/knowledge_base.py`)
   - Vector store with ChromaDB
   - Sentence-transformers embeddings (local, no API needed)
   - Retrieves relevant troubleshooting documentation dynamically
   - Chunks: 1000 chars with 200 overlap for context preservation

3. **Knowledge Base** (`knowledge_base/`)
   - Customer identification procedures
   - Connection troubleshooting scenarios
   - WiFi diagnostics and solutions
   - Speed issues and performance analysis
   - Agent behavior guidelines

4. **Function Handler** (`app/function_handler.py`) ⭐ **NEW**
   - Smart routing: quick vs complex execution
   - Quick mode: <500ms (direct tools)
   - Complex mode: 2-3s (agent + RAG)
   - Voice-optimized response formatting

5. **Realtime Client** (`app/realtime_client.py`) ⭐ **NEW**
   - OpenAI Realtime API integration
   - WebSocket audio streaming
   - Function calling management
   - Voice-to-voice conversation

6. **RADIUS Tools** (`app/radius_tools.py`)
   - Customer verification
   - Line status diagnostics
   - Speed testing
   - Remote modem reset
   - WiFi configuration (password, channel)

## Features

### ⚡ Low-Latency Voice Interface
Real-time voice conversation with intelligent latency optimization:
- **<1s** for 80% of interactions (quick conversation)
- **2-3s** for complex diagnostics (with "checking..." feedback)
- Hybrid architecture balances speed and intelligence
- Natural voice flow without awkward pauses

### Autonomous Reasoning
The agent doesn't follow fixed scripts. It analyzes each situation and decides:
- Which questions to ask
- When to use diagnostic tools
- How to interpret results
- When escalation is needed

### RAG-Powered Knowledge
Instead of hardcoding all knowledge in prompts, the agent retrieves relevant documentation on-demand:
- Efficient token usage
- Scalable to large knowledge bases
- Easy to update without code changes

### System Integration
Simulated RADIUS integration for:
- Line quality checks (signal strength, sync status)
- Remote diagnostics (connection drops, speeds)
- Remote actions (modem resets, WiFi config)

### Conversational Memory
Maintains full context of the conversation:
- Remembers customer details
- Tracks troubleshooting steps taken
- Avoids repeating questions

## Technology Stack

- **LangChain**: Agent orchestration and tool management
- **OpenAI GPT-4**: LLM for reasoning and decision-making
- **ChromaDB**: Vector database for RAG
- **Sentence Transformers**: Local embeddings (all-MiniLM-L6-v2)
- **FastAPI**: Web framework (planned)
- **OpenAI Realtime API**: Voice interface (planned)

## Installation

### Prerequisites
- Python 3.10+
- OpenAI API key

### Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/telco-voice-agent.git
cd telco-voice-agent
```

2. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment:
```bash
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

5. Build knowledge base (first time only):
```bash
python -c "from app.knowledge_base import KnowledgeBase; kb = KnowledgeBase(); kb._build_vectorstore()"
```

## Usage

### Testing the Agent (Text Mode)

```python
from app.support_agent import SupportAgent
import os
from dotenv import load_dotenv

load_dotenv()

# Initialize agent
agent = SupportAgent(
    api_key=os.getenv("OPENAI_API_KEY"),
    model="gpt-4",
    verbose=True
)

# Simulate conversation
response = agent.process_message("Buongiorno, il mio codice cliente è CL123456")
print(response)

response = agent.process_message("Non ho internet, la connessione non funziona")
print(response)

# Reset for new conversation
agent.reset_conversation()
```

### Available Mock Customers

For testing, two mock customers are available:

**Customer 1 - Good Connection:**
- Code: `CL123456`
- Name: Mario Rossi
- Type: FTTH 1000 Mbps
- Status: Active, good signal (85%)

**Customer 2 - Degraded Line:**
- Code: `CL789012`
- Name: Laura Bianchi
- Type: FTTC 200 Mbps
- Status: Active, poor signal (45%), 12 connection drops

## Project Structure

```
telco-voice-agent/
├── app/
│   ├── __init__.py
│   ├── main.py               # FastAPI server + WebSocket
│   ├── support_agent.py      # LangChain agent
│   ├── knowledge_base.py     # RAG system
│   ├── radius_tools.py       # Backend tools
│   ├── function_handler.py   # Smart routing (quick/complex)
│   └── realtime_client.py    # OpenAI Realtime API client
├── knowledge_base/
│   ├── customer_identification.md
│   ├── connection_issues.md
│   ├── wifi_issues.md
│   ├── speed_issues.md
│   └── agent_guidelines.md
├── docs/
│   ├── progress.md           # Development log
│   └── deployment_guide.md   # Setup and testing guide
├── .env.example
├── .gitignore
├── requirements.txt
├── claude.md                 # Project guidelines
└── README.md
```

## How It Works

### 1. Customer Identification
Every conversation starts with identity verification:
```
User: "Il mio codice è CL123456"
Agent: [uses verify_customer tool]
Agent: "Grazie Mario Rossi, ho verificato. Come posso aiutarla?"
```

### 2. Problem Understanding
Agent listens and retrieves relevant knowledge:
```
User: "Internet non funziona"
Agent: [RAG retrieves connection_issues.md]
Agent: "Vedo che ha problemi di connessione. Il modem ha le luci accese?"
```

### 3. Diagnosis with Tools
Agent decides which tools to use:
```
User: "Sì ma la luce internet è rossa"
Agent: [decides to use check_line_status tool]
Agent: "Controllo lo stato della sua linea..."
Agent: [interprets results]
Agent: "Rilevo un problema di qualità del segnale..."
```

### 4. Resolution or Escalation
Agent attempts fix or escalates:
```
Agent: [uses reset_modem tool]
Agent: "Ho resettato il modem. Attenda 2-3 minuti..."
```

## Design Decisions

### Why Autonomous Agent vs. Decision Tree Bot?

**Decision Tree Bot:**
- Fixed paths
- Predictable but inflexible
- Can't handle unexpected cases
- Hard to maintain and scale

**Autonomous Agent:**
- Reasons about each situation
- Adapts to unexpected scenarios
- Uses knowledge base for guidance
- More natural conversations

### Why RAG?

- **Token Efficiency**: Only retrieves relevant docs, not entire knowledge base
- **Scalability**: Can handle large documentation without context window limits
- **Maintainability**: Update docs without touching code
- **Performance**: Faster than including everything in prompts

### Why Local Embeddings?

Using sentence-transformers instead of OpenAI embeddings:
- **Cost**: Free, no API calls for embeddings
- **Privacy**: Data doesn't leave the system
- **Speed**: No network latency
- **Offline**: Works without internet (except LLM calls)

## Roadmap

- [x] Core agent with RAG and tools
- [x] Knowledge base with troubleshooting docs
- [x] Mock RADIUS integration
- [x] Smart function routing (quick vs complex)
- [x] Voice interface (OpenAI Realtime API)
- [x] FastAPI WebSocket server
- [x] Web UI for testing
- [x] Deployment and testing guide
- [ ] Production optimization (caching, monitoring)
- [ ] Real RADIUS integration
- [ ] Telephony integration (Twilio + FreePBX)
- [ ] Multi-language support
- [ ] Call analytics and quality monitoring

## Development

This is a learning project demonstrating:
- LangChain agent orchestration
- RAG system implementation
- Function calling / tool use
- Conversational AI design
- Voice AI with low-latency optimization
- Hybrid architecture (speed + intelligence)
- Production-ready patterns

**Key Technical Decisions:**
- Hybrid architecture for latency optimization
- Smart routing between quick and complex execution
- Voice-native integration (Realtime API)
- Local embeddings for cost/privacy
- Telephony-agnostic WebSocket interface

See `docs/progress.md` for detailed development notes and `docs/deployment_guide.md` for setup instructions.

## License

MIT License - see LICENSE file for details

## Contributing

This is a portfolio/learning project. Feel free to fork and experiment!

## Author

Nicola Gnasso - AI Engineering Portfolio Project

## Acknowledgments

- LangChain community for excellent documentation
- OpenAI for GPT-4 and upcoming Realtime API integration
- Anthropic Claude for development assistance
