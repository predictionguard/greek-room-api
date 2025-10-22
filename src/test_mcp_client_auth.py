#!/usr/bin/env python3
"""
Example usage of ChatClient with JWT authentication.
"""

import asyncio
import os
from dotenv import load_dotenv
from chat import ChatClient

load_dotenv()

# Your pre-generated JWT token
# Generate one using: python src/generate_token.py
AUTH_TOKEN = os.getenv("MCP_AUTH_TOKEN") or None
async def main():
    # Initialize ChatClient with authentication token
    client = ChatClient(
        mcp_url="http://localhost:8000/mcp",
        auth_token=AUTH_TOKEN
    )
    
    # Initialize and load tools
    await client.initialize()
    
    # Example 1: Simple chat with tool usage
    print("\n" + "="*80)
    print("Example 1: Analyzing repeated words")
    print("="*80)
    
    result = await client.chat(
        user_query="""
        Please check for repeated words in this scripture text:
        
        [{'snt-id': 'GEN 1:1', 'text': 'In in the beginning'}, 
         {'snt-id': 'JHN 12:24', 'text': 'Truly truly, I say to you'}]
        
        Language: English (eng)
        """
    )
    
    # Print the final response
    final_response = result['response']['choices'][0]['message']
    print("\nFinal Response:")
    print(final_response.get('content', 'No content'))
    
    # Example 2: Continue conversation
    print("\n" + "="*80)
    print("Example 2: Follow-up question")
    print("="*80)
    
    result = await client.chat(
        user_query="Can you explain what repeated words are and why they matter?"
    )
    
    final_response = result['response']['choices'][0]['message']
    print("\nFinal Response:")
    print(final_response.get('content', 'No content'))
    
    # Example 3: Reset conversation and start fresh
    print("\n" + "="*80)
    print("Example 3: New conversation (reset)")
    print("="*80)
    
    client.reset_conversation()
    
    result = await client.chat(
        user_query="What tools do you have available?"
    )
    
    final_response = result['response']['choices'][0]['message']
    print("\nFinal Response:")
    print(final_response.get('content', 'No content'))
    
    # Example 4: Update token if needed
    print("\n" + "="*80)
    print("Example 4: Update authentication token")
    print("="*80)
    
    # If you have a new token, you can update it
    # new_token = "your_new_token_here"
    # client.set_auth_token(new_token)
    print("Token can be updated using: client.set_auth_token(new_token)")

if __name__ == "__main__":
    asyncio.run(main())
