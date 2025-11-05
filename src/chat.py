"""
Chat client for interacting with MCP server and LLM services.
"""

import json
import os
import sys
from typing import Optional
from pathlib import Path

# Add src directory to path for imports
sys.path.append(str(Path(__file__).parent))
from helper import PROJECT_ROOT

from fastmcp import Client as MCPClient
from predictionguard import PredictionGuard
from dotenv import load_dotenv
from loguru import logger

# Load environment variables
load_dotenv()

# Configure logging
(PROJECT_ROOT / "logs").mkdir(exist_ok=True)
logger.add(
    PROJECT_ROOT / "logs/chat_client.log",
    rotation="1 day",
    retention="7 days",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}"
)

logger.info("Chat client module initialized")

# Configuration
PREDICTIONGUARD_URL = os.getenv("PREDICTIONGUARD_URL", "https://api.predictionguard.com")
API_KEY = os.getenv("PREDICTIONGUARD_API_KEY")
MODEL = os.getenv("PREDICTIONGUARD_DEFAULT_MODEL", "gpt-oss-120b")
MAX_COMPLETION_TOKENS = int(os.getenv("MAX_COMPLETION_TOKENS", 10000))
TEMPERATURE = float(os.getenv("TEMPERATURE", 0.5))

# Determine MCP URL based on current file location
MCP_URL = os.getenv("MCP_URL", "http://localhost:8000/mcp")


async def list_tools_from_mcp(server_path: str, auth_token: Optional[str] = None):
    """
    List available tools from the MCP server.
    
    Args:
        server_path (str): Path to the MCP server script.
        auth_token (str, optional): JWT authentication token.
        
    Returns:
        list: List of available tools.
    """
    logger.info(f"Connecting to MCP server at: {server_path}")
    try:
        # Pass auth token to MCPClient if provided
        if auth_token:
            logger.debug("Using JWT authentication for MCP connection")
            async with MCPClient(server_path, auth=auth_token) as mcp_client:
                tools = await mcp_client.list_tools()
        else:
            async with MCPClient(server_path) as mcp_client:
                tools = await mcp_client.list_tools()
                
        logger.info(f"Successfully retrieved {len(tools)} tools from MCP server")
        logger.debug(f"Available tools: {[tool.name for tool in tools]}")
        # print("Available Tools:\n\n - " + '\n - '.join([tool.name for tool in tools]))
        return tools
    except Exception as e:
        logger.error(f"Failed to list tools from MCP server: {e}")
        raise


async def generate_available_tools(mcp_url: str, auth_token: Optional[str] = None):
    """
    Generates JSON for available tools from MCP that can be passed directly to PG models.
    
    Args:
        mcp_url (str): URL/path to the MCP server.
        auth_token (str, optional): JWT authentication token.
        
    Returns:
        list: List of tools formatted for the LLM API.
    """
    logger.info(f"Generating available tools from MCP server: {mcp_url}")
    try:
        tools = await list_tools_from_mcp(mcp_url, auth_token)
        available_tools = []

        for tool in tools:
            tool_dict = {}
            tool_dict["type"] = "function"
            tool_dict["name"] = tool.name
            tool_dict["description"] = tool.description
            tool_dict["parameters"] = tool.inputSchema
            available_tools.append({"type": "function", "function": tool_dict, "strict": True})

        logger.info(f"Successfully formatted {len(available_tools)} tools for LLM API")
        return available_tools
    except Exception as e:
        logger.error(f"Failed to generate available tools: {e}")
        raise


async def call_tool(mcp_url: str, tool_name: str, tool_args: dict, available_tools: list, auth_token: Optional[str] = None):
    """
    Calls the specified tool on the MCP server with the given arguments.

    Args:
        mcp_url (str): The MCP server URL/path.
        tool_name (str): The name of the tool to call.
        tool_args (dict): Arguments to pass to the tool.
        available_tools (list): List of available tools.
        auth_token (str, optional): JWT authentication token.

    Returns:
        CallToolResult: The result of the tool call.
        
    Raises:
        ValueError: If the tool is not found on the MCP server.
    """
    logger.info(f"Attempting to call tool: {tool_name} with args: {tool_args}")
    
    tool = next((t['function']['name'] for t in available_tools if t['function']['name'] == tool_name), None)
    if not tool:
        error_msg = f"Tool '{tool_name}' not found on MCP server."
        logger.error(error_msg)
        raise ValueError(error_msg)
   
    try:
        # Pass auth token to MCPClient if provided
        if auth_token:
            logger.debug("Using JWT authentication for tool call")
            async with MCPClient(mcp_url, auth=auth_token) as mcp_client:
                result = await mcp_client.call_tool(tool, tool_args)
        else:
            async with MCPClient(mcp_url) as mcp_client:
                result = await mcp_client.call_tool(tool, tool_args)
                
        logger.info(f"Successfully executed tool: {tool_name}")
        logger.debug(f"Tool result: {result}")
        return result
    except Exception as e:
        logger.error(f"Failed to execute tool {tool_name}: {e}")
        raise


class ChatClient:
    """
    A chat client that integrates MCP tools with LLM services.
    Supports multi-turn conversations with conversation history.
    Includes JWT authentication for secure MCP server access.
    """
    
    def __init__(
        self, 
        mcp_url: str = None,
        auth_token: str = None,
        whatsapp: bool = True
    ):
        """
        Initialize the chat client.
        
        Args:
            mcp_url (str, optional): Path to MCP server. Defaults to MCP_URL.
            auth_token (str, optional): JWT authentication token for MCP server.
                If not provided, client will attempt to connect without authentication.
                Use generate_token.py with the secret key from the MCP server side to create a token if needed.
            whatsapp (bool): Whether the query is from WhatsApp. Defaults to True.
        """
        self.mcp_url = mcp_url or MCP_URL
        self.auth_token = auth_token
        self.whatsapp = whatsapp

        logger.info(f"Initializing ChatClient with MCP URL: {self.mcp_url}")
        
        if auth_token:
            logger.info("Using provided JWT authentication token")
        else:
            logger.warning("No authentication token provided. MCP calls may fail if server requires auth.")
        
        try:
            self.client = PredictionGuard(
                api_key=API_KEY,
                url=PREDICTIONGUARD_URL
            )
            logger.info("PredictionGuard client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize PredictionGuard client: {e}")
            raise
            
        self.available_tools = None
        self.conversation_history = []  # Store conversation history for multi-turn
        self.system_prompt = """You are an expert bible translator and consultant.\
You are responsible for analyzing translation tasks and provide accurate analysis and recommendations.\
You can either use the tools provided to you or use `llm_call` if you want to answer directly.\

Here are some important guidelines to follow:
- First, determine if the user query indicates some kind of analysis is needed. If yes, then use the appropriate tool. Otherwise, you can respond directly.
- If the user query indicates a text analysis is needed, intelligently demarcate the `input_text` to be analyzed.
    i) DO NOT truncate or summarize the `input_text` arbitrarily. Instead, include the full text that is relevant to the user query.
- If the user uploaded a file, make sure to include the `input_filename` in your tool call.
- If user query indicates a text analysis AND a file is uploaded:
    i) Check to see if the snippet of the file content is relevant to the user query. If yes, include the `input_text` and `input_filename` in your tool call.
    ii) If the snippet is not relevant, only include the `input_text` that you have demarcated from the user query. 
- If the user query is ambiguous, ask clarifying questions before proceeding with analysis.
- If the user requests to analyze a text AND has provided a file, make sure to include both the `input_text` and the `input_filename` in your tool call.
- Do not make up your own analysis, only use the tools provided.

"""
        if self.whatsapp:
            self.system_prompt += """- Remember that the user is interacting with you via WhatsApp. Make sure your responses are concise and formatted clearly for WhatsApp.
- Use simple language and avoid complex formatting that may not render well on WhatsApp.
- Keep responses brief and to the point, as WhatsApp users prefer quick interactions.   
- Avoid using excessive emojis.
- Avoid using Markdown formatting as it may not render properly on WhatsApp.
- Bold important terms using asterisks (*) instead of Markdown syntax, and use underscores (_) for italics.
- Use line breaks sparingly to enhance readability without overwhelming the user.
            """
        logger.debug("ChatClient initialization completed")
    
    async def initialize(self):
        """Initialize the client by loading available tools."""
        logger.info("Initializing ChatClient tools...")
        try:
            self.available_tools = await generate_available_tools(self.mcp_url, self.auth_token)
            logger.info(f"ChatClient initialized with {len(self.available_tools)} available tools")
            # Initialize conversation with system prompt
            if not self.conversation_history:
                self.conversation_history = [
                    {"role": "system", "content": self.system_prompt}
                ]
        except Exception as e:
            logger.error(f"Failed to initialize ChatClient tools: {e}")
            raise
    
    def reset_conversation(self):
        """Reset the conversation history."""
        logger.info("Resetting conversation history")
        self.conversation_history = [
            {"role": "system", "content": self.system_prompt}
        ]
    
    def get_conversation_history(self):
        """Get the current conversation history."""
        return self.conversation_history.copy()
    
    def set_auth_token(self, token: str):
        """
        Set or update the authentication token.
        
        Args:
            token (str): JWT authentication token.
        """
        self.auth_token = token
        logger.info("Authentication token updated")
    
    async def initiate_chat(self, user_query: Optional[str] = None, file_name: Optional[str] = None, use_history: bool = True):
        """
        Initiate a chat session with the LLM.
        
        Args:
            user_query (str, optional): The user's query.
            file_name (str, optional): Uploaded file path.
            use_history (bool): Whether to use conversation history. Defaults to True.
            
        Returns:
            dict: The LLM response including any tool calls.
        """
        logger.info(f"Initiating chat with query: {user_query[:100] if user_query else 'None'}...")
        
        if self.available_tools is None:
            logger.info("Tools not initialized, initializing now...")
            await self.initialize()
        
        # Add user message to history
        if user_query:
            self.conversation_history.append({"role": "user", "content": user_query})
        
        # Use either full history or just system + current message
        if use_history:
            messages = self.conversation_history.copy()
        else:
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_query}
            ]
        
        logger.debug(f"Sending request to LLM with {len(messages)} messages and {len(self.available_tools)} available tools")
        
        try:
            res = self.client.chat.completions.create(
                    model=MODEL,
                    messages=messages,
                    tools=self.available_tools,
                    tool_choice="auto", 
                    max_completion_tokens=MAX_COMPLETION_TOKENS,
                    temperature=TEMPERATURE
                )
            
            logger.info("Successfully received response from LLM")
            
            # Add assistant response to history
            assistant_message = res['choices'][0]['message']
            self.conversation_history.append(assistant_message)
            
            if assistant_message.get('tool_calls'):
                tool_calls = assistant_message['tool_calls']
                logger.info(f"LLM requested {len(tool_calls)} tool calls")
            
            return res
        except Exception as e:
            logger.error(f"Failed to get response from LLM: {e}")
            return f"Error getting response from LLM: {str(e)}"
    
    async def execute_tool_calls(self, response):
        """
        Execute tool calls from an LLM response and add results to conversation history.
        
        Args:
            response (dict): The LLM response containing tool calls.
            
        Returns:
            list: Results from tool executions.
        """
        logger.info("Executing tool calls from LLM response...")
        
        if not response.get('choices') or not response['choices'][0]['message'].get('tool_calls'):
            logger.info("No tool calls found in response")
            return []
        
        tool_calls = response['choices'][0]['message']['tool_calls']
        results = []
        
        logger.info(f"Processing {len(tool_calls)} tool calls")
        
        for i, tool_call in enumerate(tool_calls):
            tool_name = tool_call['function']['name']
            tool_args = json.loads(tool_call['function']['arguments'])
            
            logger.info(f"Executing tool call {i+1}/{len(tool_calls)}: {tool_name}")
            
            try:
                result = await call_tool(self.mcp_url, tool_name, tool_args, self.available_tools, self.auth_token)
                results.append({
                    'tool_name': tool_name,
                    'args': tool_args,
                    'result': result
                })
                
                # Add tool result to conversation history
                self.conversation_history.append({
                    "role": "tool",
                    "tool_call_id": tool_call.get('id', f"call_{i}"),
                    "name": tool_name,
                    "content": json.dumps(result.model_dump() if hasattr(result, 'model_dump') else str(result))
                })
                
                logger.info(f"Successfully executed tool: {tool_name}")
            except Exception as e:
                error_msg = f"Failed to execute tool {tool_name}: {str(e)}"
                logger.error(error_msg)
                results.append({
                    'tool_name': tool_name,
                    'args': tool_args,
                    'error': str(e)
                })
                
                # Add error to conversation history
                self.conversation_history.append({
                    "role": "tool",
                    "tool_call_id": tool_call.get('id', f"call_{i}"),
                    "name": tool_name,
                    "content": json.dumps({"error": str(e)})
                })
        
        logger.info(f"Completed tool execution: {len([r for r in results if 'error' not in r])} successful, {len([r for r in results if 'error' in r])} failed")
        return results
    
    async def continue_conversation(self, include_tool_results: bool = True):
        """
        Continue the conversation after tool calls have been executed.
        This allows the LLM to process tool results and respond.
        
        Args:
            include_tool_results (bool): Whether tool results are already in history. Defaults to True.
            
        Returns:
            dict: The LLM response.
        """
        logger.info("Continuing conversation with tool results...")
        
        try:
            res = self.client.chat.completions.create(
                model=MODEL,
                messages=self.conversation_history,
                tools=self.available_tools,
                tool_choice="auto",
                max_completion_tokens=MAX_COMPLETION_TOKENS,
                temperature=TEMPERATURE
            )
            
            logger.info("Successfully received continued response from LLM")
            
            # Add assistant response to history
            assistant_message = res['choices'][0]['message']
            self.conversation_history.append(assistant_message)
            
            if assistant_message.get('tool_calls'):
                tool_calls = assistant_message['tool_calls']
                logger.info(f"LLM requested {len(tool_calls)} additional tool calls")
            
            return res
        except Exception as e:
            logger.error(f"Failed to continue conversation: {e}")
            raise
    
    async def chat(self, user_query: str, max_turns: int = 5):
        """
        Complete chat interaction with automatic tool execution and continuation.
        This method handles the full conversation flow including multiple tool call rounds.
        
        Args:
            user_query (str): The user's query.
            max_turns (int): Maximum number of assistant turns. Defaults to 5.
            
        Returns:
            dict: Final response with conversation summary.
        """
        logger.info(f"Starting complete chat interaction with max {max_turns} turns")
        
        # Initial query
        response = await self.initiate_chat(user_query)
        turn_count = 0
        all_tool_results = []
        
        while turn_count < max_turns:
            # Check if there are tool calls to execute
            if response.get('choices') and response['choices'][0]['message'].get('tool_calls'):
                # Execute tools
                tool_results = await self.execute_tool_calls(response)
                all_tool_results.extend(tool_results)
                
                # Continue conversation with tool results
                response = await self.continue_conversation()
                turn_count += 1
            else:
                # No more tool calls, conversation complete
                logger.info(f"Conversation completed after {turn_count} turns")
                break
        
        if turn_count >= max_turns:
            logger.warning(f"Reached maximum turns ({max_turns})")
        
        return {
            'response': response,
            'turns': turn_count,
            'tool_results': all_tool_results,
            'conversation_history': self.conversation_history
        }


