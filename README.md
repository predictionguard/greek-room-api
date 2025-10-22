# Greek Room API & MCP Server

This repository provides the FastAPI and MCP endpoints for the Greek Room tools, along with a Streamlit chat app as an LLM-powered demo.

## Architecture Overview

- **Greek Room Functions**: Utilities from the [Greek Room repository](https://github.com/BibleNLP/greek-room/tree/main)
- **MCP Server**: Exposes Greek Room tools as callable MCP (Model Context Protocol) tools, enabling tool discovery and tool calls by LLMs.
- **Streamlit Chat App**: Interactive web UI demo for uploading files, running analyses, and chatting with the system. The chat is powered by Prediction Guard LLM and can call Greek Room MCP tools for analysis.
- **FastAPI Service**: Exposes REST endpoints for Greek Room functions.
- **WhatsApp Bot**: Twilio WhatsApp integration for chat-based interactions using the same LLM and MCP tools.

## Key Features

- **MCP Server**: Allows Greek Room tools to be discoverable and callable by LLMs programmatically.
- **LLM Integration**: Leverages Prediction Guard LLM for chat interactions, tool calling and analysis.
- **FastAPI Endpoints**: Provides REST endpoints for Greek Room functionalities.
- **Streamlit UI**: User-friendly web interface for file uploads, analyses, and chat interactions.
- **WhatsApp Bot**: Twilio integration for chat-based interactions using the same LLM and MCP tools.

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

## Quick Start with Docker (Local)

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

## MCP Server Deployment with Authentication

The MCP server includes JWT-based authentication using HMAC symmetric key verification for secure deployments.

### Authentication Setup

1. **Generate a secure secret key** (already configured in `.env_mcpserver`):
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(64))"
   ```

2. **Configure environment variables** in `.env_mcpserver`:
   ```env
   # FastMCP JWT Authentication (HMAC Symmetric Key)
   JWT_SECRET_KEY=your-generated-secret-key-here
   JWT_ALGORITHM=HS256
   JWT_ISSUER=greek-room-mcp
   JWT_AUDIENCE=greek-room-client
   ```

3. **Generate JWT tokens** for authorized clients:
   ```bash
   python src/generate_token.py --client-id "my-client" --expires-days 365
   ```
   
   This will output a JWT token that clients must include in their requests. In our case, we will append this in the `.env` file under `MCP_AUTH_TOKEN`:
   ```
   MCP_AUTH_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
   ```


### Using the Authenticated MCP Server

Clients must include the JWT token and proper Accept headers in all requests to the MCP server.

**Important**: FastMCP HTTP transport requires the Accept header to include **both** `application/json` and `text/event-stream`.

#### Complete MCP Client Example

```python
import requests

# Step 1: Initialize MCP session
headers = {
    "Authorization": "Bearer YOUR_JWT_TOKEN_HERE",
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream"  # Both are required!
}

init_response = requests.post(
    "http://localhost:8000/mcp",
    json={
        "jsonrpc": "2.0",
        "method": "initialize",
        "id": 1,
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "my-client",
                "version": "1.0.0"
            }
        }
    },
    headers=headers
)

# Extract session ID from response header
session_id = init_response.headers.get("mcp-session-id")

# Step 2: Send initialized notification
requests.post(
    "http://localhost:8000/mcp",
    json={
        "jsonrpc": "2.0",
        "method": "notifications/initialized",
        "params": {}
    },
    headers={
        **headers,
        "mcp-session-id": session_id
    }
)

# Step 3: Call MCP methods (e.g., list tools)
response = requests.post(
    "http://localhost:8000/mcp",
    json={
        "jsonrpc": "2.0",
        "method": "tools/list",
        "id": 2
    },
    headers={
        **headers,
        "mcp-session-id": session_id
    }
)
```

### Testing Authentication

Run the test suite to verify authentication is working:

```bash
python src/test_auth.py
```

Expected results:
- ✅ Requests without tokens → 401 Unauthorized
- ✅ Requests with valid tokens → Authenticated
- ✅ Requests with invalid tokens → 401 Unauthorized

### Using ChatClient with Authentication

```python
from chat import ChatClient

# Initialize with your pre-generated client-side MCP JWT Authentication token
client = ChatClient(
    mcp_url="http://localhost:8000/mcp",
    auth_token="MCP_AUTH_TOKEN"  # Your JWT token here
)

# Initialize and run analysis
await client.initialize()
result = await client.chat("Check this text for repeated words: [...]")
```

## Local Development Setup

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
    - Configure JWT authentication variables (see MCP Server Deployment section above)

4. **Run the FastAPI server**:
	```sh
	uvicorn src.app:app --port 8001
	```

5. **Run the MCP server** (with authentication):
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

## Current Deployment on GCP Cloud Run
- MCP Server with Authentication: <to be filled in>
- Whatsapp Bot Webhook: <to be filled in>
## License

MIT License