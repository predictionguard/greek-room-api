import os
from pathlib import Path
from loguru import logger
import sys
# Add src directory to path for imports
sys.path.append(str(Path(__file__).parent))
from helper import PROJECT_ROOT

from fastmcp import FastMCP
from typing import Optional, Dict, Any, Annotated, List
import json

 # using wb_file_props directly from Greek Room PyPI package
from greekroom.gr_utilities import wb_file_props
from greekroom.owl import repeated_words

# Import our custom markdown writer
from markdown_writer import generate_markdown_string

from predictionguard import PredictionGuard
from dotenv import load_dotenv
import uuid

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

def generate_json_repeated_words(
        id: str,
        lang_code: str, 
        lang_name: str, 
        project_id: str, 
        project_name: str, 
        check_corpus: List[Dict]
        ) -> str:
    
    """ Generate the JSON-RPC task string for repeated words check """

    task = {
        "jsonrpc": "2.0",
        "id": id,
        "method": "BibleTranslationCheck",
        "params": [{
            "lang-code": lang_code,
            "lang-name": lang_name,
            "project-id": project_id,
            "project-name": project_name,
            "selectors": [{
                "tool": "GreekRoom",
                "checks": ["RepeatedWords"]
            }],
            "check-corpus": check_corpus
        }]
    }
    return json.dumps(task)

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

@mcp.tool(name="check_repeated_words", 
          title="Check for Repeated Words",
          description="Check for repeated words in text. It will return back a markdown string with the results.")
async def check_repeated_words(
    lang_code: Annotated[str, "The language code (e.g., 'en'). You can infer it based on ISO 639-3 codes based on lang_name. If ambiguous, such as whether to choose `azw` or `arb`, refer back to the user."],
    lang_name: Annotated[str, "The full name of the language (e.g., 'English'). You can infer it based on ISO 639-3 codes. If ambiguous, such as whether to choose `Hijazi Arabic` or `Standard Arabic`, refer back to the user."],
    check_corpus: Annotated[list[dict], "Scripture corpus to check. For example [{'snt-id': 'GEN 1:1', 'text': 'In in the beginning'}, {'snt-id': 'JHN 12:24', 'text': 'Truly truly, I say to you'}]"],
    project_id: Annotated[Optional[str], "The unique identifier for the project. Optional unless user provides one"] = None,
    project_name: Annotated[Optional[str], "The name of the project. Optional unless user provides one"] = None,
    explicit_data_filenames: Annotated[Optional[list[str]], "Optional explicit filenames for data sources"] = None
) -> str:
    """
    Checks for repeated words in a given scripture corpus for a specific language and project.
    Returns a markdown string with the results of the repeated words check.
    """

    if project_id is None:
        project_id = lang_name + "-" + str(uuid.uuid4())[:4]

    id = project_id + "-" + str(uuid.uuid4())[:2]

    # Assuming generate_json_repeated_words is defined elsewhere
    task_s = generate_json_repeated_words(
        id=id,
        lang_code=lang_code,
        lang_name=lang_name,
        project_id=project_id,
        project_name=project_name,
        check_corpus=check_corpus
    )

    data_filename_dict = repeated_words.load_data_filename(
        explicit_data_filenames,
        verbose=True
    )

    corpus = repeated_words.new_corpus(id)
    mcp_d, misc_data_dict, check_corpus_list = repeated_words.check_mcp(task_s, data_filename_dict, corpus)
    feedback = repeated_words.get_feedback(mcp_d, 'GreekRoom', 'RepeatedWords')
    corpus = repeated_words.update_corpus_if_empty(corpus, check_corpus_list)

    res_md = generate_markdown_string(feedback, misc_data_dict, corpus, lang_code, lang_name, project_name)

    return res_md

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