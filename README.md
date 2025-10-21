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

## Services Overview

The repository includes four containerized services:

1. **FastAPI Service** - Port 8001
   - Main REST API for Greek Room analysis tools
   - API documentation at http://localhost:8001/docs

2. **MCP Server** - Port 8000
   - Model Context Protocol server for tool discovery and execution
   - Used by LLMs to call Greek Room tools programmatically

3. **WhatsApp Bot** - Port 5001
   - Twilio WhatsApp integration for chat-based interactions
   - Requires Twilio credentials in `.env` file

4. **Streamlit App** - Port 8501
   - Interactive web UI for file uploads and chat-based analysis
   - Access at http://localhost:8501

## Quick Start with Docker (Recommended)

### Prerequisites

- Docker and Docker Compose installed
- `.env` file with required API keys (see `.env.example`)

### Environment Variables

Required in `.env` file:

```env
# Prediction Guard (required for all services)
PREDICTIONGUARD_API_KEY=your_api_key_here
PREDICTIONGUARD_DEFAULT_MODEL=gpt-oss-120b

# Twilio (required for WhatsApp bot only)
TWILIO_ACCOUNT_SID=your_twilio_sid
TWILIO_AUTH_TOKEN=your_twilio_token
TWILIO_WHATSAPP_NUMBER=whatsapp:+your_twilio_whatsapp_number
```

### Start All Services

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f

# View logs for specific service
docker-compose logs -f streamlit
```

### Start Individual Services

```bash
# Start only FastAPI service
docker-compose up -d fastapi

# Start only MCP server
docker-compose up -d mcp-server

# Start WhatsApp bot (automatically starts MCP server due to dependency)
docker-compose up -d whatsapp-bot

# Start Streamlit app (automatically starts MCP server due to dependency)
docker-compose up -d streamlit
```

### Stop Services

```bash
# Stop all services
docker-compose down

# Stop specific service
docker-compose stop streamlit
```

### Access the Services

- **Streamlit Chat App**: http://localhost:8501
- **FastAPI Docs**: http://localhost:8001/docs
- **MCP Server**: http://localhost:8000
- **WhatsApp Bot**: http://localhost:5001

Note that the WhatsApp bot (the `webhook` endpoint) needs to be publicly accessible for receiving messages from Twilio Whatsapp (via Settings -> "When a message comes in"). 
Locally, we can use a tool like [ngrok](https://ngrok.com/) to expose the webhook endpoint, but in production, it should be hosted on a public server with proper and secured authentications.

## Local Development Setup (Alternative)

If you prefer to run services locally without Docker:

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

4. **Run the FastAPI server**:
	```sh
	uvicorn src.app:app --port 8001
	```

5. **Run the MCP server**:
	```sh
	python src/app_mcp.py
	```

6. **Launch the Streamlit chat app**:
	```sh
	streamlit run src/streamlit_app.py
	```

## Data for Testing
- Sample text files are available in the `data/` directory for testing file upload and analysis features.

## Configuration

- Set Prediction Guard API keys and model in a `.env` file for LLM features.
- All logs are stored in the `logs/` directory.
- Shared volumes (Docker): `./logs`, `./data`, `./storage`

## Docker Troubleshooting

### View Service Logs
```bash
docker-compose logs -f [service-name]
```

### Restart a Service
```bash
docker-compose restart [service-name]
```

### Rebuild After Code Changes
```bash
docker-compose up -d --build
```

### Check Service Status
```bash
docker-compose ps
```

### Access Service Shell
```bash
docker-compose exec [service-name] /bin/bash
```

## Potential Areas for Improvement
~~- Add more Greek Room tools as MCP endpoints.~~
~~- Develop WhatsApp interface for chat interactions, instead of Streamlit.~~  
- Enhance eval and error handling mechanisms in LLM tool calls:
    - For example, in the `analyze_script_punct` MCP tool, add tests to ensure valid file paths and input texts by passing in user queries and Streamlit's path.
- Enhance the prompt to ensure the LLM understands how to call the tools effectively.
- Use of structured outputs to ensure secure and predictable LLM responses.

## License

MIT License