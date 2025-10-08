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
MAX_COMPLETION_TOKENS = 10000
TEMPERATURE = None

# Determine MCP URL based on current file location
MCP_URL = PROJECT_ROOT / "src/app_mcp.py"


async def list_tools_from_mcp(server_path: str):
    """
    List available tools from the MCP server.
    
    Args:
        server_path (str): Path to the MCP server script.
        
    Returns:
        list: List of available tools.
    """
    logger.info(f"Connecting to MCP server at: {server_path}")
    try:
        async with MCPClient(server_path) as mcp_client:
            tools = await mcp_client.list_tools()
        logger.info(f"Successfully retrieved {len(tools)} tools from MCP server")
        logger.debug(f"Available tools: {[tool.name for tool in tools]}")
        print("Available Tools:\n\n - " + '\n - '.join([tool.name for tool in tools]))
        return tools
    except Exception as e:
        logger.error(f"Failed to list tools from MCP server: {e}")
        raise


async def generate_available_tools(mcp_url: str):
    """
    Generates JSON for available tools from MCP that can be passed directly to PG models.
    
    Args:
        mcp_url (str): URL/path to the MCP server.
        
    Returns:
        list: List of tools formatted for the LLM API.
    """
    logger.info(f"Generating available tools from MCP server: {mcp_url}")
    try:
        tools = await list_tools_from_mcp(mcp_url)
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


async def call_tool(mcp_url: str, tool_name: str, tool_args: dict, available_tools: list):
    """
    Calls the specified tool on the MCP server with the given arguments.

    Args:
        mcp_url (str): The MCP server URL/path.
        tool_name (str): The name of the tool to call.
        tool_args (dict): Arguments to pass to the tool.
        available_tools (list): List of available tools.

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
    """
    
    def __init__(self, mcp_url: str = None):
        """
        Initialize the chat client.
        
        Args:
            mcp_url (str, optional): Path to MCP server. Defaults to MCP_URL.
        """
        self.mcp_url = mcp_url or MCP_URL
        logger.info(f"Initializing ChatClient with MCP URL: {self.mcp_url}")
        
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
        logger.debug("ChatClient initialization completed")
    
    async def initialize(self):
        """Initialize the client by loading available tools."""
        logger.info("Initializing ChatClient tools...")
        try:
            self.available_tools = await generate_available_tools(self.mcp_url)
            logger.info(f"ChatClient initialized with {len(self.available_tools)} available tools")
        except Exception as e:
            logger.error(f"Failed to initialize ChatClient tools: {e}")
            raise
    
    async def initiate_chat(self, user_query: Optional[str] = None, file_name: Optional[str] = None):
        """
        Initiate a chat session with the LLM.
        
        Args:
            user_query (str, optional): The user's query.
            file_name (str, optional): Uploaded file path.
            
        Returns:
            dict: The LLM response including any tool calls.
        """
        logger.info(f"Initiating chat with query: {user_query[:100] if user_query else 'None'}...")
        
        if self.available_tools is None:
            logger.info("Tools not initialized, initializing now...")
            await self.initialize()
            
        system_prompt = """You are an expert bible translator and consultant.\
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
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query}
        ]
        
        logger.debug(f"Sending request to LLM with {len(self.available_tools)} available tools")
        
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
            if res.get('choices') and res['choices'][0]['message'].get('tool_calls'):
                tool_calls = res['choices'][0]['message']['tool_calls']
                logger.info(f"LLM requested {len(tool_calls)} tool calls")
            
            return res
        except Exception as e:
            logger.error(f"Failed to get response from LLM: {e}")
            raise
    
    async def execute_tool_calls(self, response):
        """
        Execute tool calls from an LLM response.
        
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
                result = await call_tool(self.mcp_url, tool_name, tool_args, self.available_tools)
                results.append({
                    'tool_name': tool_name,
                    'args': tool_args,
                    'result': result
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
        
        logger.info(f"Completed tool execution: {len([r for r in results if 'error' not in r])} successful, {len([r for r in results if 'error' in r])} failed")
        return results

