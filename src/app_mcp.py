import os
from pathlib import Path
from loguru import logger
import sys
# Add src directory to path for imports
sys.path.append(str(Path(__file__).parent))
from helper import PROJECT_ROOT

from fastmcp import FastMCP
from typing import Optional, Dict, Any, Annotated

 # using wb_file_props directly from Greek Room PyPI package
from greekroom.gr_utilities import wb_file_props

from predictionguard import PredictionGuard
from dotenv import load_dotenv

load_dotenv()

(PROJECT_ROOT / "logs").mkdir(exist_ok=True)
logger.add(
    PROJECT_ROOT / "logs/mcp.log",
    rotation="1 day",
    retention="7 days",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}"
)

# Initialize Prediction Guard
pg_client = PredictionGuard()
MODEL = os.getenv("PREDICTIONGUARD_DEFAULT_MODEL", "gpt-oss-120b")

# Initialize the MCP server
mcp = FastMCP("Greek Room Analysis MCP Server")

UPLOAD_FOLDER = PROJECT_ROOT / "storage"
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)



async def upload_text_file(file) -> Dict[str, Any]:
    """
    Uploads a text file and returns its storage path and metadata.
    Files are stored in the storage directory and can be accessed by their filename for analysis.
    """
    logger.info(f"Upload path: {UPLOAD_FOLDER}")

    try:
        # Validate file extension
        file_extension = os.path.splitext(file.filename)[1].lower()
        if file_extension != '.txt':
            return {
                "status": "error",
                "message": "Only .txt files are supported",
                "file_type": file_extension,
                "file_path": None
            }

        # Save file to storage directory
        file_path = UPLOAD_FOLDER / file.filename
        content = await file.read()
        with open(file_path, "wb") as buffer:
            buffer.write(content)

        # Return success response with file info
        return {
            "status": "success",
            "message": f"File {file.filename} uploaded successfully",
            "file_path": file_path.as_posix(),
            "file_type": "txt"
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "file_path": None,
            "file_type": None
        }


@mcp.tool(name="analyze_script_punct",
            title="Script and Punctuation Analysis",
           description="Analyze script direction and punctuation style, either with a text file or a text input string.")
async def analyze_script_punct(
    input_filename: Annotated[Optional[str], "Path to the input text file. This must be present if input_string is None"],
    input_string: Annotated[Optional[str], "Input text string to analyze. This must be present if input_filename is None"],
    lang_code: Annotated[Optional[str], "Language code for the input text. You can infer it based on ISO 639 codes"],
    lang_name: Annotated[Optional[str], "Language name for the input text. You can infer it based on ISO 639 codes"]
) -> Dict[str, Any]:
    """
    Analyzes the script direction and punctuation style of a given text file and/or text input.
    """

    if input_filename is None and input_string is None:
        raise Exception("Either input_filename or input_string must be provided")
    
    if input_filename:
        logger.info(f"Analyzing file: {input_filename}")
    if input_string:
        logger.info(f"Analyzing input string: {len(input_string)}")
    analysis_result = wb_file_props.script_punct(
        input_filename=input_filename,
        input_string=input_string,
        lang_code=lang_code,
        lang_name=lang_name
    )

    return analysis_result


@mcp.tool(name="llm_chat",
          title="LLM Chat Completion",
          description="Get chat completion from an LLM model.")
async def llm_chat(prompt: str) -> Dict[str, Any]:
    """
    Get chat completion from an LLM model using Prediction Guard.
    """
    try:
        response = pg_client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            max_completion_tokens=1000
        )
        return {
            "status": "success",
            "response": response
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


if __name__ == "__main__":
    mcp.run()