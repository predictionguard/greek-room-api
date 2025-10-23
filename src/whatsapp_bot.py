"""
WhatsApp Bot for Greek Room Analysis
Integrates with MCP server and LLM services via Twilio WhatsApp API
"""

import os
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, Form
from fastapi.responses import Response
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client as TwilioClient
from dotenv import load_dotenv
from loguru import logger
import sys

# Add src directory to path for imports
sys.path.append(str(Path(__file__).parent))
from helper import PROJECT_ROOT
from chat import ChatClient

from contextlib import asynccontextmanager

# Load environment variables
load_dotenv()

# Configure logging
(PROJECT_ROOT / "logs").mkdir(exist_ok=True)
logger.add(
    PROJECT_ROOT / "logs/whatsapp_bot.log",
    rotation="1 day",
    retention="7 days",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}"
)
# Twilio Configuration
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")

# Initialize Twilio client
twilio_client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Session storage for user conversations (in production, use Redis or database)
user_sessions = {}

chat_client = None
async def initialize_chat_client():
    """Initialize the chat client with MCP tools."""
    global chat_client
    
    if chat_client is None:
        try:
            logger.info("Initializing chat client for WhatsApp bot...")
            mcp_path = os.getenv("MCP_URL", "http://localhost:8000")
            mcp_auth = os.getenv("MCP_AUTH_TOKEN", None)
            logger.debug(f"MCP server path: {mcp_path}")

            chat_client = ChatClient(mcp_url=mcp_path, auth_token=mcp_auth)
            await chat_client.initialize()

            logger.info("Chat client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize chat client: {e}")
            raise

    return chat_client

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler to initialize chat client on startup."""
    global chat_client
    logger.info("Starting WhatsApp bot...")
    chat_client = await initialize_chat_client()
    logger.info("WhatsApp bot ready!")
    yield

wa_app = FastAPI(title="WhatsApp Bot for Greek Room Analysis", lifespan=lifespan)

def get_user_session(phone_number: str) -> dict:
    """Get or create a user session."""
    if phone_number not in user_sessions:
        user_sessions[phone_number] = {
            "messages": [],
            "uploaded_file": None,
            "file_name": None
        }
        logger.info(f"Created new session for user: {phone_number}")
    return user_sessions[phone_number]


def send_whatsapp_message(to: str, message: str, media_url: Optional[str] = None):
    """
    Send a WhatsApp message via Twilio.
    
    Args:
        to: Recipient phone number (format: whatsapp:+1234567890)
        message: Text message to send
        media_url: Optional media URL to attach
    """
    try:
        params = {
            "from_": TWILIO_WHATSAPP_NUMBER,
            "body": message,
            "to": to
        }
        
        if media_url:
            params["media_url"] = [media_url]
        
        message = twilio_client.messages.create(**params)
        logger.info(f"Sent WhatsApp message to {to}: {message.sid}")
        return message
    except Exception as e:
        logger.error(f"Failed to send WhatsApp message: {e}")
        raise


def format_response_for_whatsapp(text: str, max_length: int = 1600) -> list:
    """
    Format long responses into WhatsApp-friendly chunks.
    WhatsApp messages have a 1600 character limit.
    
    Args:
        text: The text to format
        max_length: Maximum length per message
        
    Returns:
        list: List of message chunks
    """
    if len(text) <= max_length:
        return [text]
    
    # Split by paragraphs first
    paragraphs = text.split('\n\n')
    chunks = []
    current_chunk = ""
    
    for paragraph in paragraphs:
        if len(current_chunk) + len(paragraph) + 2 <= max_length:
            current_chunk += paragraph + "\n\n"
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = paragraph + "\n\n"
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    # If a single paragraph is too long, split by sentences
    final_chunks = []
    for chunk in chunks:
        if len(chunk) <= max_length:
            final_chunks.append(chunk)
        else:
            sentences = chunk.split('. ')
            current = ""
            for sentence in sentences:
                if len(current) + len(sentence) + 2 <= max_length:
                    current += sentence + ". "
                else:
                    if current:
                        final_chunks.append(current.strip())
                    current = sentence + ". "
            if current:
                final_chunks.append(current.strip())
    
    return final_chunks


async def process_message(phone_number: str, message_text: str, media_url: Optional[str] = None) -> list:
    """
    Process incoming message and generate response.
    
    Args:
        phone_number: User's phone number
        message_text: The text message received
        media_url: Optional media URL (for file uploads)
        
    Returns:
        list: List of response messages
    """
    logger.info(f"Processing message from {phone_number}: '{message_text[:100]}'")
    
    # Get or create user session
    session = get_user_session(phone_number)
    
    # Handle file uploads (images of text files)
    if media_url:
        logger.info(f"User uploaded media: {media_url}")
        session["uploaded_file"] = media_url
        # return ["📁 File received! You can now ask questions about it. Try: 'Analyze this file' or 'What's the script direction?'"]
    
    # Handle special commands
    if message_text.lower() in ['/start', 'start', 'help', '/help']:
        return [
            "👋 Welcome to Greek Room Analysis Bot!\n\n"
            "I can help you analyze biblical texts and translations.\n\n"
            "📝 *What I can do:*\n"
            "• Analyze script direction (LTR/RTL)\n"
            "• Check punctuation styles\n"
            "• Answer questions about the Bible\n"
            "• Analyze text files\n\n"
            "💡 *How to use:*\n"
            "• Send me a text file to analyze\n"
            "• Ask questions like:\n"
            "  - 'What's the script direction?'\n"
            "  - 'Analyze punctuation'\n"
            "  - 'Tell me about John 3:16'\n\n"
            "Type '/clear' to start a new conversation."
        ]
    
    if message_text.lower() in ['/clear', 'clear', 'reset']:
        session["messages"] = []
        session["uploaded_file"] = None
        logger.info(f"Cleared session for {phone_number}")
        return ["🗑️ Conversation cleared! Starting fresh."]
    
    try:
        # Prepare query
        query = message_text
        
        # If user has uploaded a file, include it in the query
        if session["uploaded_file"]:
            logger.info("Including uploaded file in analysis")
            query += f"\n\nThe user has provided a file at: {session['uploaded_file']}. Please analyze it."
        
        # Get response from chat client
        logger.info("Sending query to chat client...")
        response = await chat_client.initiate_chat(user_query=query)
        
        # Extract assistant's message
        assistant_message = response['choices'][0]['message']['content']
        
        # Execute any tool calls
        tool_results = []
        if response['choices'][0]['message'].get('tool_calls'):
            logger.info("Executing tool calls...")
            tool_results = await chat_client.execute_tool_calls(response)
            logger.info(f"Tool execution completed: {len(tool_results)} results")
        
        # Format response
        responses = []
        
        if assistant_message:
            # Split long messages into chunks
            message_chunks = format_response_for_whatsapp(assistant_message)
            responses.extend(message_chunks)
        
        # Add tool results
        if tool_results:
            responses.append("\n📊 *Analysis Results:*")
            
            for result in tool_results:
                if "error" in result:
                    responses.append(f"❌ Error in {result['tool_name']}: {result['error']}")
                else:
                    result_text = ""
                    if hasattr(result['result'], 'content') and result['result'].content:
                        result_text = result['result'].content[0].text
                    else:
                        result_text = str(result['result'])
                    
                    # Format tool results
                    tool_response = f"\n🔧 *{result['tool_name']}*\n{result_text}"
                    result_chunks = format_response_for_whatsapp(tool_response)
                    responses.extend(result_chunks)
        
        # Store in session history
        session["messages"].append({"role": "user", "content": message_text})
        session["messages"].append({"role": "assistant", "content": assistant_message})
        
        logger.info(f"Successfully processed message, sending {len(responses)} response chunks")
        return responses
        
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        return [f"❌ Sorry, I encountered an error: {str(e)}\n\nPlease try again or type 'help' for assistance."]


@wa_app.post("/webhook")
async def webhook(
    Body: str = Form(...),
    From: str = Form(...),
    NumMedia: int = Form(...), 
    MediaUrl0: Optional[str] = Form(None),
):
    """
    Handle incoming WhatsApp messages via Twilio webhook.
    We point to this endpoint from the Twilio console for WhatsApp ("When a message comes in").
    """
    try:
        incoming_msg = Body.strip()
        num_media = int(NumMedia)
        from_number = From
        media_url = MediaUrl0
        
        logger.info(f"Received message from {from_number}: '{incoming_msg[:100]} with {num_media} media: {media_url}'")
        
        if media_url:
            logger.info(f"User uploaded media: {media_url}")
            
        # Process the message asynchronously
        responses = await process_message(from_number, incoming_msg, media_url)
        
        # Send first response via TwiML (immediate response)
        resp = MessagingResponse()
        if responses:
            resp.message(responses[0])
        
        # Send additional responses via Twilio API (if any)
        if len(responses) > 1:
            for response in responses[1:]:
                send_whatsapp_message(from_number, response)
        
        return Response(content=str(resp), media_type="application/xml")
        
    except Exception as e:
        logger.error(f"Error in webhook handler: {e}")
        resp = MessagingResponse()
        resp.message("❌ Sorry, I encountered an error. Please try again later.")
        return Response(content=str(resp), media_type="application/xml")



@wa_app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "service": "whatsapp-bot"}


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("WHATSAPP_PORT", 5001))
    logger.info(f"Starting WhatsApp FastAPI endpoints on port {port}")
    uvicorn.run(wa_app, host="0.0.0.0", port=port)
