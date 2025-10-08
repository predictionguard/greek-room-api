import asyncio
import os
from pprint import pp
from fastmcp import Client
import json 
from typing import Optional
from pathlib import Path

import sys
# Add src directory to path for imports
sys.path.append(str(Path(__file__).parent))
from helper import PROJECT_ROOT

MCP_CLIENT_FILE = PROJECT_ROOT / "src/app_mcp.py"

async def call_tool(    
            input_filename: Optional[str] = None,
            input_string: Optional[str] = None,
            lang_code: Optional[str] = None,
            lang_name: Optional[str] = None
            ):
    async with Client(MCP_CLIENT_FILE) as client:
        await client.ping()
        result = await client.call_tool("analyze_script_punct", {
            "input_filename": input_filename,
            "input_string": input_string,
            "lang_code": lang_code,
            "lang_name": lang_name
        })
        print(result)


test_string = "This is a test string."
res = asyncio.run(call_tool(None, test_string, "en", "English"))
pp(res)