import os
from pathlib import Path
from loguru import logger
import sys
# Add src directory to path for imports
sys.path.append(str(Path(__file__).parent))
from helper import PROJECT_ROOT

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from typing import Optional, Dict, Any, List
import uvicorn
import json
import uuid

 # using wb_file_props directly from Greek Room PyPI package
from greekroom.gr_utilities import wb_file_props
from greekroom.owl import repeated_words

# Import our custom markdown writer
from markdown_writer import generate_markdown_string

(PROJECT_ROOT / "logs").mkdir(exist_ok=True)
logger.add(
    PROJECT_ROOT / "logs/fastapi.log",
    rotation="1 day",
    retention="7 days",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}"
)

UPLOAD_FOLDER = PROJECT_ROOT / "storage"
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
logger.info(f"Upload path: {UPLOAD_FOLDER}")

app = FastAPI(
    title="Greek Room Analysis API",
    description="Unified API endpoints to access the tools for Greek Room tools",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

def generate_json_repeated_words(
        id: str,
        lang_code: str, 
        lang_name: str, 
        project_id: str, 
        project_name: str, 
        check_corpus: List[Dict]
        ) -> str:
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

@app.post("/check-repeated-words", summary="Check for repeated words in text")
async def check_repeated_words(
        lang_code: str,
        lang_name: str,
        check_corpus: List[Dict[str, str]],        
        project_id: Optional[str]=None,
        project_name: Optional[str]=None,
        explicit_data_filenames: Optional[List[str]]=None
        ) -> Dict[str, Any]:
    
    """
        Checks for repeated words in a given corpus for a specific language and project.
        Args:
            lang_code (str): The language code (e.g., 'en').
            lang_name (str): The full name of the language ('English').
            project_id (str): The unique identifier for the project.
            project_name (str): The name of the project.
            check_corpus (List[Dict[str, str]]): The corpus to check, as a list of dictionaries.
            explicit_data_filenames (Optional[Dict[str], optional): Optional explicit filenames for data sources. If not provided, it will search for files owl/data/legitimate_duplicates.jsonl in directories "greekroom", "$XDG_DATA_HOME", "/usr/share", "$HOME/.local/share"
        Returns:
            Dict[str]: {"result": Markdown string with the results of the repeated words check}
    """
    
    if project_id is None:
        project_id = lang_name + "-" + str(uuid.uuid4())[:4]
    
    id = project_id + "-" + str(uuid.uuid4())[:2]

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
        verbose=True # we'll do verbose by default for debugging
    )

    corpus = repeated_words.new_corpus(id)
    mcp_d, misc_data_dict, check_corpus_list = repeated_words.check_mcp(task_s, data_filename_dict, corpus)
    feedback = repeated_words.get_feedback(mcp_d, 'GreekRoom', 'RepeatedWords')
    corpus = repeated_words.update_corpus_if_empty(corpus, check_corpus_list)
    
    res_md = generate_markdown_string(feedback, misc_data_dict, corpus, lang_code, lang_name, project_name)

    return {"result": res_md}

@app.post("/analyze-script-punct", summary="Analyze script direction and punctuation style")
async def analyze_script_punct(
    file: Optional[UploadFile] = None,
    input_string: Optional[str] = None,
    lang_code: Optional[str] = None,
    lang_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Analyzes the script direction and punctuation style of a given text file and/or text input.
    """
    logger.info("Received request for /analyze-script-punct")
    if file is None and input_string is None:
        logger.warning("No file or input_string provided")
        raise HTTPException(
            status_code=400,
            detail="Either file or input_string must be provided"
        )

    if file:
        logger.info(f"File upload detected: {file.filename}")
        # upload file using upload_text_file function
        upload_response = await upload_text_file(file)
        if upload_response.status_code != 200:
            logger.error(f"File upload failed: {file.filename}")
            raise HTTPException(
                status_code=upload_response.status_code,
                detail="File upload failed"
            )
        input_filename = json.loads(upload_response.body.decode())["file_path"]
        logger.info(f"Upload response: {upload_response}")
    else:
        logger.info("No file uploaded, using input_string")
        input_filename = None
        
    logger.info(f"Calling script_punct with input_filename={input_filename}, lang_code={lang_code}, lang_name={lang_name}")
    analysis_result = wb_file_props.script_punct(
        input_filename=input_filename,
        input_string=input_string,
        lang_code=lang_code,
        lang_name=lang_name
    )
    logger.info(f"Analysis result: {analysis_result}")

    return analysis_result

async def upload_text_file(file: UploadFile = File(...)) -> JSONResponse:
    """
    Uploads a text file and analyzes its content for script direction and punctuation style.
    Files are stored in the storage directory and can be accessed by their filename for analysis.
    """
    logger.info(f"Uploading file: {file.filename}")

    try:
        # Validate file extension
        file_extension = os.path.splitext(file.filename)[1].lower()
        if file_extension not in ['.txt']:
            logger.warning(f"Unsupported file extension: {file_extension}")
            raise HTTPException(
                status_code=400,
                detail="Only .txt files are supported"
            )

        # Save file to storage directory
        file_path = UPLOAD_FOLDER / file.filename
        logger.info(f"Saving file to: {file_path}")
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        logger.info(f"File {file.filename} saved successfully")

        # Return success response with file info
        return JSONResponse({
            "status": "success",
            "message": f"File {file.filename} uploaded successfully",
            "file_path": file_path.as_posix(),
            "file_type": "txt"
        })

    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        raise HTTPException(status_code=400, detail=str(e))

if __name__ == "__main__":
    logger.info("Starting FastAPI server")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)