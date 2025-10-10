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

from typing import Optional, Dict, Any
import uvicorn
import json

 # using wb_file_props directly from Greek Room PyPI package
from greekroom.gr_utilities import wb_file_props

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
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)