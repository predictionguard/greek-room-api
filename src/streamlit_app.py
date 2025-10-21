"""
Streamlit Chat App for Greek Room Analysis
Integrates with MCP server and LLM services for text analysis
"""

import streamlit as st
import asyncio
import tempfile
import os
import json
import sys
from loguru import logger
from pathlib import Path

# Add src directory to path for imports
sys.path.append(str(Path(__file__).parent))
from helper import PROJECT_ROOT

# Import the chat client
from chat import ChatClient

# Configure logging for Streamlit app
(PROJECT_ROOT / "logs").mkdir(exist_ok=True)
logger.add(
    PROJECT_ROOT / "logs/streamlit_app.log",
    rotation="1 day",
    retention="7 days",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}"
)

# Create logs directory if it doesn't exist
os.makedirs(PROJECT_ROOT / "logs", exist_ok=True)

logger.info("Starting Streamlit Greek Room Analysis Chat App")

# Configure the Streamlit page
st.set_page_config(
    page_title="Greek Room Analysis Chat",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
    logger.info("Initialized chat messages session state")
if "chat_client" not in st.session_state:
    st.session_state.chat_client = None
    logger.debug("Initialized chat client session state")
if "tools_initialized" not in st.session_state:
    st.session_state.tools_initialized = False
    logger.debug("Initialized tools state")

# Async wrapper for Streamlit
async def initialize_chat_client():
    """Initialize the chat client with MCP tools."""
    logger.info("Initializing chat client...")
    if st.session_state.chat_client is None:
        try:
            # Use absolute path for MCP server
            mcp_path = os.getenv("MCP_URL", "http://localhost:8000/mcp")
            logger.debug(f"MCP server path: {mcp_path}")
            
            st.session_state.chat_client = ChatClient(mcp_url=mcp_path)
            await st.session_state.chat_client.initialize()
            st.session_state.tools_initialized = True
            
            logger.info("Chat client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize chat client: {e}")
            raise

def run_async(coro):
    """Run async function in Streamlit."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


# Ensure chat client is initialized at app startup
if not st.session_state.tools_initialized:
    run_async(initialize_chat_client())

def is_markdown(text):
    """
    Detect if text contains markdown formatting.
    
    Args:
        text: String to check for markdown patterns
        
    Returns:
        bool: True if markdown patterns are detected
    """
    if not isinstance(text, str):
        return False
    
    markdown_patterns = [
        r'#{1,6}\s',  # Headers
        r'\*\*.*\*\*',  # Bold
        r'\*.*\*',  # Italic
        r'^\s*[-*+]\s',  # Unordered lists
        r'^\s*\d+\.\s',  # Ordered lists
        r'\[.*\]\(.*\)',  # Links
        r'```',  # Code blocks
        r'`[^`]+`',  # Inline code
        r'^\s*>',  # Blockquotes
        r'^\s*\|.*\|',  # Tables
    ]
    
    import re
    for pattern in markdown_patterns:
        if re.search(pattern, text, re.MULTILINE):
            return True
    return False

def display_tool_result(result_text):
    """
    Display tool result with appropriate formatting.
    
    Args:
        result_text: The text content to display
    """
    try:
        # Try to parse as JSON for better formatting
        result_json = json.loads(result_text)
        st.json(result_json)
        logger.debug("JSON result displayed")
    except (json.JSONDecodeError, ValueError):
        # If not JSON, check if it's markdown
        if is_markdown(result_text):
            st.markdown(result_text)
            logger.debug("Markdown result displayed")
        else:
            # Display as plain text
            st.text(result_text)
            logger.debug("Text result displayed")

# Sidebar for quick actions only
with st.sidebar:
    st.header("� Quick Actions")
    
    # Clear chat button
    if st.button("🗑️ Clear Chat"):
        logger.info("User cleared chat history")
        st.session_state.messages = []
        st.rerun()
    
    st.divider()
    
    st.markdown("### 💡 Tips")
    st.markdown("""
    - Upload a file and ask about its analysis
    - Try: "Analyze the script direction"
    - Try: "What's the punctuation style?"
    - Ask follow-up questions about results
    """)

# Main chat interface
st.title("📚 Greek Room Analysis Chat")
st.markdown("Ask questions about the bible or translation analysis.")

# File upload in main interface
uploaded_file = st.file_uploader(
    "📁 Upload a text file for analysis",
    type=['txt'],
    help="Upload a .txt file to analyze its script direction and punctuation style"
)

if uploaded_file is not None:
    logger.info(f"File uploaded: {uploaded_file.name} ({uploaded_file.size} bytes)")
    
    # Save uploaded file to temporary location
    with tempfile.NamedTemporaryFile(mode="w+", suffix=".txt", delete=False) as f:
        content = uploaded_file.read()
        if isinstance(content, bytes):
            content = content.decode('utf-8')
        f.write(content)
        temp_file_path = f.name
        st.session_state.file_snippet = content[:50] # Store first 50 chars for reference 

    logger.debug(f"File saved to temporary path: {temp_file_path}")
    
    st.success(f"File '{uploaded_file.name}' uploaded successfully!")
    st.session_state.uploaded_file_path = temp_file_path
    st.session_state.uploaded_file_name = uploaded_file.name
    
    logger.info(f"File content length: {len(content)} characters")
    
    # Show file preview
    with st.expander("File Preview"):
        st.text_area("Content:", content[:500] + "..." if len(content) > 500 else content, height=100, disabled=True)

# Initialize chat client
if not st.session_state.tools_initialized:
    with st.spinner("Initializing chat client and MCP tools..."):
        try:
            run_async(initialize_chat_client())
            st.success("✅ Chat client initialized successfully!")
        except Exception as e:
            st.error(f"❌ Failed to initialize chat client: {str(e)}")
            st.stop()

# Display chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message["role"] == "assistant" and "tool_results" in message:
            # Display tool results
            st.markdown(message["content"])
            if message["tool_results"]:
                with st.expander("🔧 Tool Execution Details"):
                    for result in message["tool_results"]:
                        if "error" in result:
                            st.error(f"Error in {result['tool_name']}: {result['error']}")
                        else:
                            st.success(f"**{result['tool_name']}** executed successfully")
                            if hasattr(result['result'], 'content') and result['result'].content:
                                display_tool_result(result['result'].content[0].text)
        else:
            st.markdown(message["content"])

# Chat input
if prompt := st.chat_input("Ask a question or request an analysis..."):
    logger.info(f"User submitted prompt: '{prompt[:100]}'")
    
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Display user message
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Generate assistant response
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                # Prepare the query based on uploaded file
                query = prompt
                
                # If file is uploaded, modify the query to include file analysis
                if hasattr(st.session_state, 'uploaded_file_path'):
                    logger.info(f"Including uploaded file in analysis: {st.session_state.uploaded_file_name}")

                    query += f"""\nThe user has also provided an uploaded file at this path '{st.session_state.uploaded_file_path}'.\
Here's a snippet of the file content for context: '{st.session_state.file_snippet}'. Please analyze the file as part of your response."""
                
                logger.debug(f"Final query to LLM: '{query}'")
                
                # Get response from chat client
                logger.info("Sending query to chat client...")
                response = run_async(st.session_state.chat_client.initiate_chat(user_query=query))
                
                # Extract the assistant's message
                assistant_message = response['choices'][0]['message']['content']
                # logger.info(f"Received assistant message: {len(assistant_message) if assistant_message else 0} characters")
                
                # Execute any tool calls
                tool_results = []
                if response['choices'][0]['message'].get('tool_calls'):
                    logger.info("Executing tool calls...")
                    with st.spinner("Executing tools..."):
                        tool_results = run_async(st.session_state.chat_client.execute_tool_calls(response))
                    logger.info(f"Tool execution completed: {len(tool_results)} results")
                
                # Display response
                if assistant_message:
                    st.markdown(assistant_message)
                    logger.debug("Assistant message displayed")
                
                # Display tool results
                if tool_results:
                    st.markdown("### 🔧 Analysis Results")
                    logger.info(f"Displaying {len(tool_results)} tool results")
                    
                    for result in tool_results:
                        if "error" in result:
                            st.error(f"Error in {result['tool_name']}: {result['error']}")
                            logger.warning(f"Tool error displayed: {result['tool_name']} - {result['error']}")
                        else:
                            with st.expander(f"📊 {result['tool_name']} Results", expanded=True):
                                if hasattr(result['result'], 'content') and result['result'].content:
                                    result_text = result['result'].content[0].text
                                    display_tool_result(result_text)
                                    logger.debug(f"Result displayed for {result['tool_name']}")
                                else:
                                    st.write(result['result'])
                                    logger.debug(f"Raw result displayed for {result['tool_name']}")
                
                # Prepare full response for chat history
                full_response = assistant_message or "Analysis completed. See tool results below."
                
                # Add assistant message to chat history
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": full_response,
                    "tool_results": tool_results
                })
                
                logger.info("Response processing completed successfully")
                
            except Exception as e:
                error_msg = f"❌ Error: {str(e)}"
                logger.error(f"Error in chat processing: {e}")
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})

# Footer
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: gray;'>
    Greek Room Analysis Chat - Powered by Prediction Guard
    </div>
    """, 
    unsafe_allow_html=True
)

# Cleanup temporary files on app restart
if hasattr(st.session_state, 'uploaded_file_path'):
    try:
        if os.path.exists(st.session_state.uploaded_file_path):
            pass  # Keep file for session duration
    except Exception:
        pass