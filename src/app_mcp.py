import os
from pathlib import Path
from fastapi import Request
from loguru import logger
import sys
# Add src directory to path for imports
sys.path.append(str(Path(__file__).parent))
from helper import PROJECT_ROOT

from docx import Document

from fastmcp import FastMCP
from fastmcp.server.auth.providers.jwt import JWTVerifier
from typing import Optional, Dict, Any, Annotated, List
import json
import asyncio
import re
import tempfile

 # using wb_file_props directly from Greek Room PyPI package
import greekroom
from greekroom.gr_utilities import wb_file_props
from greekroom.owl import repeated_words

# usfm_check.py ships as a standalone script (bare `from ualign_utilities import ...`, writes outputs to cwd),
# so we run it as a subprocess per request instead of importing it.
USFM_CHECK_SCRIPT = Path(greekroom.__file__).parent / "usfm" / "usfm_check.py"
USFM_CHECK_TIMEOUT_S = 300
MAX_USFM_REPORT_CHARS = 20000

# Import our custom markdown writer
from markdown_writer import generate_markdown_string, generate_whatsapp_friendly_string

from predictionguard import PredictionGuard
from dotenv import load_dotenv
import uuid

from starlette.requests import Request
from starlette.responses import PlainTextResponse

import unicodedata as ud

load_dotenv()

# test_dict_str = """
# {"script-direction": {"direction": "left-to-right", "counts": {"L": 3229280, "WS": 752507, "CS": 105303, "B": 41899, "ON": 20427, "ES": 3217, "R": 21, "AL": 0}, "report": "Determined script direction for English to be left-to-right with character direction counts 3229280:21 in favor."}, "punct-style": {"quotation-pairs": [], "counts": {"\u2019": {"n_start_word": 0, "n_start2_word": 0, "n_end_word": 317, "n_end2_word": 317, "n_in_word": 1682, "total": 1999}}, "pair-counts": {}}, "number-style": {"style": {}, "counts": {}, "examples": {}}, "n-chars": 4152654, "lang-code": "eng", "lang-name": "English"}
# """

# test_dict = json.loads(test_dict_str)
# test_dict


# # using UD, let's find the longest unicode name
# longest_unicode_name = ""
# codepoint = ""
# for codepoint in range(0x110000):
#     try:
#         name = ud.name(chr(codepoint))
#         if len(name) > len(longest_unicode_name):
#             longest_unicode_name = name
#     except ValueError:
#         continue

# print("Longest Unicode name found:")
# print(codepoint)
# print(longest_unicode_name)
# print("Length:", len(longest_unicode_name))

def generate_script_punct_report(analysis_dict: Dict[str, Any]) -> str:
    """
    Generate a formatted text report from script and punctuation analysis results.
    
    Args:
        analysis_dict: Dictionary containing script direction, punctuation style, 
                      and number style analysis results
    
    Returns:
        Formatted string report
    """
    report_lines = ["General"]
    
    # Language info
    lang_code = analysis_dict.get("lang-code", "")
    lang_name = analysis_dict.get("lang-name", "")
    report_lines.append(f"Language code: {lang_code}")
    report_lines.append(f"Language name: {lang_name}")
    
    # Script direction section
    script_dir = analysis_dict.get("script-direction", {})
    report_lines.append("Script direction")
    report_lines.append(f"Direction: {script_dir.get('direction', 'N/A')}")
    report_lines.append(f"Counts: {script_dir.get('counts', {})}")
    report_lines.append(f"Report: {script_dir.get('report', 'N/A')}")
    
    # Punctuation style section
    punct_style = analysis_dict.get("punct-style", {})
    report_lines.append("Punctuation style")
    report_lines.append("\t Counts")
    
    # # Table header
    # report_lines.append("Punct\tUnicode name\tTotal\tStart+\tStart\tInside\tEnd\tEnd+")
    
    # Punctuation rows
    punct_counts = punct_style.get("counts", {})
    for punct_char, data in punct_counts.items():
        # Get Unicode name (simplified for now)
        unicode_name = ud.name(punct_char, "")
        total = data.get("total")
        start_plus = data.get("n_start2_word")
        start = data.get("n_start_word")
        inside = data.get("n_in_word")
        end = data.get("n_end_word")
        end_plus = data.get("n_end2_word")
        
        report_lines.append(f"""\t\t Punct: {punct_char}
\t\t Unicode Name: {unicode_name}
\t\t Total: {total}
\t\t Start+: {start_plus}
\t\t Start: {start}
\t\t Inside: {inside}
\t\t End: {end}
\t\t End+: {end_plus}
""")

    # TODO: To add in Digital Number Style section if needed

    # return as a 
    return "```" + "\n".join(report_lines) + "```"

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

# Configure JWT Authentication with HMAC
jwt_verifier = JWTVerifier(
    public_key=os.getenv("JWT_SECRET_KEY"),  # Despite the name, this accepts symmetric secrets for HMAC
    issuer=os.getenv("JWT_ISSUER", "greek-room-mcp"),
    audience=os.getenv("JWT_AUDIENCE", "greek-room-client"),
    algorithm=os.getenv("JWT_ALGORITHM", "HS256")  # Use HMAC algorithm
)

# Initialize the MCP server with authentication
mcp = FastMCP("Greek Room Analysis MCP Server", auth=jwt_verifier)

UPLOAD_FOLDER = PROJECT_ROOT / "storage"
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

def read_docx_file(file_path: str) -> str:
    """
    Reads a .docx file and returns its text content as a string.
    """
    doc = Document(file_path)
    full_text = []
    for para in doc.paragraphs:
        full_text.append(para.text)
    return '\n'.join(full_text)

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
           description="Analyze script direction and punctuation style, either with a word document file (.docx) or a text input string.")
async def analyze_script_punct(
    # input_filename: Annotated[Optional[str], "Path to the input text file (in '.docx'). This must be present if input_string is None"],
    input_string: Annotated[Optional[str], "Input text string to analyze. This must be present if input_filename is None"],
    lang_code: Annotated[Optional[str], "Language code for the input text. You can infer it based on ISO 639 codes"],
    lang_name: Annotated[Optional[str], "Language name for the input text. You can infer it based on ISO 639 codes"]
) -> Dict[str, Any]:
    """
    Analyzes the script direction and punctuation style of a given text file and/or text input.
    """

    # if input_filename is None and input_string is None:
    #     raise Exception("Either input_filename or input_string must be provided")
    
    # if input_filename:
    #     logger.info(f"Analyzing file: {input_filename}")
    if input_string:
        logger.info(f"Analyzing input string: {len(input_string)}")

    # if input_filename.split(".")[-1].lower() == "doc":
    #     raise Exception(".doc file format is not supported. Please use .docx format instead.")
    # elif input_filename.split(".")[-1].lower() == "docx":
    #     # read the doc/docx file content
    #     docx_txt = read_docx_file(input_filename)
    #     # save to a temporary txt file for analysis
    #     temp_txt_path = UPLOAD_FOLDER / (Path(input_filename).stem + "_temp.txt")
    #     with open(temp_txt_path, "w", encoding="utf-8") as f:
    #         f.write(docx_txt)
    #     input_filename = temp_txt_path.as_posix()

    analysis_result = wb_file_props.script_props(
        input_filename=None,
        input_string=input_string,
        lang_code=lang_code,
        lang_name=lang_name
    )

    # reformat the result (in dict) to be readable
    res = generate_script_punct_report(analysis_result)

    return {
        "punctuation_analysis_report": res,
        "note_to_LLM": "Return the punctuation_analysis_report field directly back to the user, VERBATIM including the ````` markers."
    }



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
) -> Dict[str, Any]:
    """
    Checks for repeated words in a given scripture corpus for a specific language and project.
    Returns a dictionary of results including a whatsapp-formatted report.
    """
    res_md = run_repeated_words(lang_code, lang_name, check_corpus, project_id, project_name, explicit_data_filenames)

    return {"repeated_words_report": res_md,
            "note_to_LLM": "Return the repeated_words_report field directly back to the user, VERBATIM including all formatting."}


def run_repeated_words(
    lang_code: str,
    lang_name: str,
    check_corpus: List[Dict],
    project_id: Optional[str] = None,
    project_name: Optional[str] = None,
    explicit_data_filenames: Optional[List[str]] = None
) -> str:
    """ Run the Greek Room repeated words check and return a whatsapp-formatted report """
    #TODO: The `repeated_words.check_mcp` needs to be refactored. It was an attempt by the Greek Room maintainers to create an MCP-compliant script. Essentially, we don't need to really generate JSON, or to `get_feedback`. We can refactor the repeated_words module to return the feedback directly.

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
        verbose=True
    )

    corpus = repeated_words.new_corpus(id)
    mcp_d, misc_data_dict, check_corpus_list = repeated_words.check_mcp(task_s, data_filename_dict, corpus)
    feedback = repeated_words.get_feedback(mcp_d, 'GreekRoom', 'RepeatedWords')
    corpus = repeated_words.update_corpus_if_empty(corpus, check_corpus_list)

    return generate_whatsapp_friendly_string(feedback, misc_data_dict, corpus, lang_code, lang_name, project_name)


async def run_usfm_check(usfm_content: str, filename: str, lang_code: Optional[str]) -> Dict[str, Any]:
    """
    Run Greek Room's usfm_check.py on a single USFM file in an isolated temp directory.
    Returns the text report, scorecard and the extracted (versified) corpus rows.
    """
    with tempfile.TemporaryDirectory(prefix="usfm_check_") as tmp:
        in_dir, out_dir = Path(tmp) / "in", Path(tmp) / "out"
        in_dir.mkdir()
        out_dir.mkdir()
        (in_dir / filename).write_text(usfm_content, encoding="utf-8")

        cmd = [sys.executable, str(USFM_CHECK_SCRIPT), "-d", str(in_dir)]
        if lang_code:
            cmd += ["--lc", lang_code]
        proc = await asyncio.create_subprocess_exec(
            *cmd, cwd=out_dir, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        try:
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=USFM_CHECK_TIMEOUT_S)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise RuntimeError(f"USFM check timed out after {USFM_CHECK_TIMEOUT_S}s")
        if proc.returncode != 0:
            logger.error(f"usfm_check failed: {stderr.decode(errors='replace')[-2000:]}")
            raise RuntimeError("USFM check failed. The file may not be valid USFM.")

        report_path = out_dir / "usfm_check.txt"
        scorecard_path = out_dir / "usfm_scorecard.json"
        extract_path = out_dir / "extract.jsonl"
        report = report_path.read_text(encoding="utf-8") if report_path.exists() else ""
        scorecard = json.loads(scorecard_path.read_text(encoding="utf-8")) if scorecard_path.exists() else {}
        extract = []
        if extract_path.exists():
            with open(extract_path, encoding="utf-8") as f:
                extract = [json.loads(line) for line in f if line.strip()]

    return {"report": report, "scorecard": scorecard, "extract": extract}


@mcp.tool(name="check_usfm",
          title="Greek Room USFM Check",
          description="Run Greek Room checks on a USFM (Paratext) scripture file: USFM structure/tag checks, repeated words, and script/punctuation analysis. Pass the full USFM file content as text.")
async def check_usfm(
    usfm_content: Annotated[str, "The full text content of the USFM (.usfm/.sfm) file, unmodified."],
    lang_code: Annotated[str, "ISO 639-3 language code of the text (e.g. 'zlm' for Malay). Infer from lang_name; if ambiguous, refer back to the user."],
    lang_name: Annotated[str, "Full name of the language (e.g. 'Malay')."],
    book_code: Annotated[Optional[str], "3-letter USFM book code (e.g. 'JHN'). Only needed if the file has no \\id line."] = None,
    filename: Annotated[Optional[str], "Original filename, if known (e.g. 'JHN_chapter2_draft1.usfm')."] = None,
    project_name: Annotated[Optional[str], "The name of the project. Optional unless user provides one"] = None,
) -> Dict[str, Any]:
    """
    Runs the Greek Room USFM checker on the file, then runs the repeated words check and the
    script/punctuation analysis on the extracted verse texts (footnotes and headings excluded).
    """
    filename = Path(filename).name if filename else "input.usfm"
    if not filename.lower().endswith("sfm"):  # usfm_check only picks up *sfm files
        filename += ".usfm"

    try:
        usfm_result = await run_usfm_check(usfm_content, filename, lang_code)
    except RuntimeError as e:
        return {"status": "error", "message": str(e)}

    # Book code: from \id in the file, else the argument, else a filename prefix like "JHN_..."
    filename_match = re.match(r"^([1-4]?[A-Z]{2,3})(?=[_\-. ])", filename.upper())
    fallback_book = (book_code or (filename_match.group(1) if filename_match else "UNK")).upper()

    check_corpus = [
        {"snt-id": f"{row.get('bk') or fallback_book} {row.get('c')}:{row.get('v')}", "text": row["txt"].strip()}
        for row in usfm_result["extract"]
        if row.get("type") == "v" and row.get("txt", "").strip()
    ]

    usfm_report = usfm_result["report"]
    if len(usfm_report) > MAX_USFM_REPORT_CHARS:
        usfm_report = usfm_report[:MAX_USFM_REPORT_CHARS] + "\n... [report truncated]"

    result: Dict[str, Any] = {
        "status": "success",
        "n_verses_extracted": len(check_corpus),
        "usfm_scorecard": usfm_result["scorecard"],
        "usfm_check_report": usfm_report,
    }

    if check_corpus:
        repeated_report = run_repeated_words(lang_code, lang_name, check_corpus, project_name=project_name)
        if len(repeated_report) > MAX_USFM_REPORT_CHARS:
            repeated_report = repeated_report[:MAX_USFM_REPORT_CHARS] + "\n... [report truncated]"
        result["repeated_words_report"] = repeated_report
        script_props = wb_file_props.script_props(
            input_string="\n".join(row["text"] for row in check_corpus),
            lang_code=lang_code,
            lang_name=lang_name,
        )
        result["punctuation_analysis_report"] = generate_script_punct_report(script_props)
    else:
        result["message"] = "No verse text (\\v) found in the input, so only the USFM structure check was run."

    result["note_to_LLM"] = (
        "Present each report to the user under its own heading: USFM check (summarise the scorecard and list the "
        "errors/warnings from usfm_check_report; tag statistics can be summarised), then repeated_words_report and "
        "punctuation_analysis_report VERBATIM including all formatting."
    )
    return result

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
    
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> PlainTextResponse:
    return PlainTextResponse("OK")


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000)