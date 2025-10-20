"""
Support Agent - Autonomous AI agent for telecommunications troubleshooting

This module implements the main AI agent that:
- Reasons autonomously about customer problems
- Retrieves relevant knowledge via RAG
- Uses tools to interact with backend systems
- Maintains conversational memory
- Decides when to escalate
"""

from typing import Optional, Dict, Any
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_openai import ChatOpenAI
from langchain.memory import ConversationBufferMemory
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.schema import SystemMessage, HumanMessage, AIMessage

from app.knowledge_base import KnowledgeBase
from app.radius_tools import ALL_TOOLS


class SupportAgent:
    """
    Autonomous AI agent for technical support.

    Architecture:
    - LangChain OpenAI Tools Agent (ReAct pattern)
    - RAG knowledge retrieval for troubleshooting docs
    - Function calling for system integration (RADIUS)
    - Conversational memory for context retention
    - Autonomous decision making

    Why OpenAI Tools Agent?
    - Native function calling support
    - Better at multi-step reasoning
    - Handles tool errors gracefully
    - Good at deciding when to use tools vs knowledge
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4",
        temperature: float = 0.1,
        verbose: bool = True
    ):
        """
        Initialize the support agent.

        Args:
            api_key: OpenAI API key
            model: Model to use (gpt-4 recommended for complex reasoning)
            temperature: Lower = more deterministic, higher = more creative
            verbose: Whether to print reasoning steps
        """
        self.api_key = api_key
        self.model_name = model
        self.temperature = temperature
        self.verbose = verbose

        # Initialize components
        self.llm = ChatOpenAI(
            api_key=api_key,
            model=model,
            temperature=temperature
        )

        # Initialize knowledge base with RAG
        self.knowledge_base = KnowledgeBase()

        # Initialize tools
        self.tools = ALL_TOOLS

        # Initialize memory
        # Using ConversationBufferMemory to remember full conversation
        # Alternative: ConversationBufferWindowMemory for longer conversations (keeps last N)
        self.memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True,
            output_key="output"
        )

        # Create agent
        self.agent_executor = self._create_agent()

        # Track current customer
        self.current_customer_id: Optional[str] = None

    def _create_system_prompt(self) -> str:
        """
        Create the system prompt that defines the agent's behavior.

        This is CRITICAL - it tells the agent:
        - Who it is
        - What it can do
        - How it should behave
        - When to use tools
        - How to use RAG knowledge

        The quality of this prompt determines agent performance.
        """
        return """You are an AI technical support agent for a telecommunications company.

Your role is to help customers resolve internet, WiFi, and connectivity issues through troubleshooting and using available diagnostic tools.

## Core Responsibilities

1. **Identify the customer FIRST** - Always use verify_customer() as your first action
2. **Listen and understand** the problem completely before acting
3. **Retrieve relevant knowledge** from your knowledge base to guide troubleshooting
4. **Use tools** to diagnose and fix technical issues
5. **Explain clearly** what you're doing and why
6. **Escalate when needed** if problem can't be resolved remotely

## Available Tools

You have access to these tools for backend system integration:
- verify_customer: Identify and verify customer (ALWAYS FIRST)
- check_line_status: Check internet line status and quality
- run_speed_test: Test actual internet speed
- reset_modem: Remotely reboot customer's modem
- change_wifi_password: Change WiFi password
- change_wifi_channel: Change WiFi channel (for interference)

## Knowledge Base Access

You have access to comprehensive troubleshooting documentation via RAG.
When facing a problem, relevant documentation will be automatically retrieved.
Use this knowledge to:
- Understand common scenarios
- Know which tools to use when
- Decide on troubleshooting steps
- Determine when to escalate

## Communication Style

- Professional but friendly and empathetic
- Use simple language (avoid excessive technical jargon)
- Be patient and understanding
- Keep responses concise (this is voice conversation)
- Always explain BEFORE using a tool that will interrupt service

## Workflow

1. **Greet and Identify**: Ask for customer ID/phone, then verify_customer()
2. **Listen to Problem**: Let customer describe issue fully
3. **Retrieve Knowledge**: Use your knowledge base for similar scenarios
4. **Diagnose**: Ask clarifying questions or use diagnostic tools
5. **Resolve**: Guide customer through solution or use tools to fix
6. **Verify**: Confirm problem is resolved
7. **Close**: Ask if there's anything else

## When to Escalate

Create a ticket and transfer to specialist when:
- Problem persists after 15 minutes of troubleshooting
- Line is down persistently even after reset
- Signal quality <50% and reset doesn't help
- Customer requests physical technician visit
- Problem requires billing/administrative action
- Problem needs advanced configuration (VPN, port forwarding, etc.)

## Important Rules

- NEVER proceed with troubleshooting without verifying customer first
- ALWAYS explain before using reset_modem (service interruption)
- NEVER guess - if unsure, check knowledge base or escalate
- NEVER share sensitive data beyond customer name
- Keep track of current customer_id and use it for all tool calls

You are autonomous - use your judgment to decide the best course of action based on the situation and available knowledge."""

    def _create_agent(self) -> AgentExecutor:
        """
        Create the LangChain agent with tools, memory, and RAG.

        This combines:
        - System prompt (defines behavior)
        - Tools (gives capabilities)
        - Memory (maintains context)
        - RAG (provides knowledge)

        Returns:
            AgentExecutor ready to handle conversations
        """
        # Create prompt template
        # This structure tells the agent where to look for:
        # - System instructions
        # - Chat history (memory)
        # - User input
        # - Agent's scratchpad (reasoning)
        prompt = ChatPromptTemplate.from_messages([
            ("system", self._create_system_prompt()),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])

        # Create agent
        agent = create_openai_tools_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=prompt
        )

        # Create executor
        # The executor manages the ReAct loop:
        # - Runs agent
        # - Executes tools
        # - Feeds results back to agent
        # - Repeats until done
        agent_executor = AgentExecutor(
            agent=agent,
            tools=self.tools,
            memory=self.memory,
            verbose=self.verbose,
            handle_parsing_errors=True,  # Gracefully handle tool call errors
            max_iterations=10,  # Prevent infinite loops
            return_intermediate_steps=False
        )

        return agent_executor

    def process_message(self, user_message: str) -> str:
        """
        Process a user message and return agent's response.

        This is the main interface for conversing with the agent.

        Flow:
        1. Retrieve relevant knowledge from RAG based on message
        2. Add knowledge to context
        3. Run agent with message + knowledge
        4. Return response

        Args:
            user_message: What the user said

        Returns:
            Agent's response
        """
        # Retrieve relevant knowledge from RAG
        # This gives the agent context about how to handle the specific problem
        relevant_docs = self.knowledge_base.retrieve(user_message, k=3)

        # Format knowledge as additional context
        knowledge_context = "\n\n".join([
            f"[KNOWLEDGE BASE EXCERPT]\n{doc.page_content}"
            for doc in relevant_docs
        ])

        # Create enhanced input with knowledge
        enhanced_input = f"""{user_message}

[The following documentation may be relevant to this situation]
{knowledge_context}"""

        # Run agent
        try:
            result = self.agent_executor.invoke({
                "input": enhanced_input
            })

            return result["output"]

        except Exception as e:
            # Graceful error handling
            error_msg = f"I encountered an error: {str(e)}. Let me try a different approach."
            print(f"Agent error: {e}")
            return error_msg

    def reset_conversation(self):
        """
        Reset the conversation memory.

        Use this when:
        - Starting a new conversation
        - Customer hangs up
        - Switching to different customer
        """
        self.memory.clear()
        self.current_customer_id = None

    def get_conversation_history(self) -> list:
        """
        Get the full conversation history.

        Useful for:
        - Debugging
        - Analytics
        - Logging
        - Transfer to human (context handoff)

        Returns:
            List of messages in conversation
        """
        return self.memory.chat_memory.messages

    def set_customer_id(self, customer_id: str):
        """
        Set the current customer ID.

        The agent should call this after verify_customer succeeds.

        Args:
            customer_id: Customer ID from verification
        """
        self.current_customer_id = customer_id

    def get_knowledge_for_debugging(self, query: str, k: int = 3):
        """
        Retrieve knowledge base documents for debugging/testing.

        Use this to see what documents the RAG would retrieve for a query.

        Args:
            query: Question or problem description
            k: Number of documents to retrieve

        Returns:
            List of (document, score) tuples
        """
        return self.knowledge_base.retrieve_with_scores(query, k=k)
