# Greek Room API & MCP Server

This repository provides the FastAPI and MCP endpoints for the Greek Room tools, along with a Streamlit chat app as an LLM-powered demo.

## Architecture Overview

- **Greek Room Functions**: Utilities from the [Greek Room repository](https://github.com/BibleNLP/greek-room/tree/main)
- **MCP Server**: Exposes Greek Room tools as callable MCP (Model Context Protocol) tools, enabling tool discovery and tool calls by LLMs.
- **Streamlit Chat App**: Interactive web UI demo for uploading files, running analyses, and chatting with the system. The chat is powered by Prediction Guard LLM and can call Greek Room MCP tools for analysis.
- **FastAPI Service**: Exposes REST endpoints for Greek Room functions.

## Key Features

- **MCP Server**: Allows Greek Room tools to be discoverable and callable by LLMs programmatically.
- **LLM Integration**: Leverages Prediction Guard LLM for chat interactions, tool calling and analysis.
- **FastAPI Endpoints**: Provides REST endpoints for Greek Room functionalities.

## Quick Start

1. **Install dependencies** (Python 3.12+):
	```sh
	uv sync
	```

2. **Activate the virtual environment**:
    ```sh
    source .venv/bin/activate
    ```

3. **Set up environment variables**:
    - Update the `PREDICTIONGUARD_API_KEY` key in the `.env` file.

4. **Run the FastAPI server (optional)**:
	```sh
	uvicorn src.app:app
	```
    
    - Access the API docs at `http://localhost:8000/docs`

5. **Run the MCP server (optional)**:
	```sh
	python src/app_mcp.py
	```

    - MCP server is accessible at `http://localhost:8001/mcp`

5. **Launch the Streamlit chat app**:
	```sh
	streamlit run src/streamlit_app.py
	```
    - By default, this connects to the MCP server through the MCP file path (`./src/app_mcp.py`).
    - Access the chat app at `http://localhost:8501`

## Data for Testing
- Sample text files are available in the `data/` directory for testing file upload and analysis features.

## Configuration

- Set Prediction Guard API keys and model in a `.env` file for LLM features.
- All logs are stored in the `logs/` directory.

## Potential Areas for Improvement
- Add more Greek Room tools as MCP endpoints.
- Develop WhatsApp interface for chat interactions, instead of Streamlit.
- Enhance eval and error handling mechanisms in LLM tool calls:
    - For example, in the `analyze_script_punct` MCP tool, add tests to ensure valid file paths and input texts by passing in user queries and Streamlit's path.
- Enhance the prompt to ensure the LLM understands how to call the tools effectively.
- Use of structured outputs to ensure secure and predictable LLM responses.

## License

MIT License