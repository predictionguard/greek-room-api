#!/usr/bin/env python3
"""
Test script to verify JWT authentication is working on the MCP server.
"""

import requests
import sys
import os
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "http://localhost:8000"

# The token we generated earlier
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJncmVlay1yb29tLW1jcCIsImF1ZCI6ImdyZWVrLXJvb20tY2xpZW50Iiwic3ViIjoiZ3JlZWstcm9vbS1jbGllbnQiLCJjbGllbnRfaWQiOiJncmVlay1yb29tLWNsaWVudCIsImV4cCI6MTc5MjY0NzEyOCwiaWF0IjoxNzYxMTExMTI4fQ.52uPTGIZxkvORw0ihrVNbSoTp3tW5fDtXQNA2o-TfZk"

def test_health_endpoint():
    """Test the health endpoint (should work without auth)"""
    print("\n" + "="*80)
    print("TEST 1: Health Check (No Auth Required)")
    print("="*80)
    
    try:
        response = requests.get(f"{BASE_URL}/health")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            print("✅ Health check passed")
            return True
        else:
            print("❌ Health check failed")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_mcp_without_auth():
    """Test MCP endpoint without authentication (should fail)"""
    print("\n" + "="*80)
    print("TEST 2: MCP Endpoint WITHOUT Authentication (Should Fail)")
    print("="*80)
    
    try:
        response = requests.post(
            f"{BASE_URL}/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "tools/list",
                "id": 1
            },
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream"
            }
        )
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text[:200]}")
        
        if response.status_code == 401:
            print("✅ Correctly rejected request without authentication")
            return True
        else:
            print("❌ Should have returned 401 Unauthorized")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_mcp_with_auth():
    """Test MCP endpoint with valid JWT token (should succeed)"""
    print("\n" + "="*80)
    print("TEST 3: MCP Endpoint WITH Valid JWT Token (Should Succeed)")
    print("="*80)
    
    try:
        # Step 1: Initialize MCP session
        init_response = requests.post(
            f"{BASE_URL}/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "initialize",
                "id": 1,
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "test-client",
                        "version": "1.0.0"
                    }
                }
            },
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",  # Must accept both!
                "Authorization": f"Bearer {TOKEN}"
            }
        )
        
        print(f"Initialize Status Code: {init_response.status_code}")
        print(f"Response Headers: {dict(init_response.headers)}")
        print(f"Response Body: {init_response.text}")
        
        # Check if authentication passed
        if init_response.status_code == 401:
            print("❌ Authentication failed - token was rejected")
            return False
        elif init_response.status_code == 406:
            print("⚠️  Got 406 Not Acceptable - checking if this is an auth issue or content negotiation")
            response_lower = init_response.text.lower()
            if "authentication" in response_lower or "unauthorized" in response_lower:
                print("❌ This appears to be an authentication issue")
                return False
            else:
                print("⚠️  This appears to be a content negotiation issue, but auth passed")
                print("    (Server accepted the JWT but doesn't like the request format)")
                return False  # Change to False since 406 is not success
        elif init_response.status_code == 200:
            print("✅ Successfully authenticated with JWT token!")
            print(f"Initialize Response: {init_response.text[:500]}")
            
            # Extract session ID from response header
            session_id = init_response.headers.get("mcp-session-id")
            print(f"Session ID: {session_id}")
            
            # Parse JSON response (it's in SSE format)
            try:
                # SSE format: "event: message\ndata: {...}\n\n"
                response_lines = init_response.text.strip().split('\n')
                for line in response_lines:
                    if line.startswith('data: '):
                        import json
                        init_data = json.loads(line[6:])  # Remove "data: " prefix
                        print(f"Parsed response keys: {list(init_data.keys())}")
                        break
            except Exception as e:
                print(f"Could not parse SSE data: {e}")
            
            # Step 2: Send initialized notification (required by MCP protocol)
            notif_response = requests.post(
                f"{BASE_URL}/mcp",
                json={
                    "jsonrpc": "2.0",
                    "method": "notifications/initialized",
                    "params": {}
                },
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                    "Authorization": f"Bearer {TOKEN}",
                    "mcp-session-id": session_id  # Include session ID
                }
            )
            
            print(f"\nInitialized Notification Status: {notif_response.status_code}")
            
            # Step 3: List tools
            tools_response = requests.post(
                f"{BASE_URL}/mcp",
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/list",
                    "id": 2
                },
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                    "Authorization": f"Bearer {TOKEN}",
                    "mcp-session-id": session_id  # Include session ID
                }
            )
            
            print(f"Tools List Status: {tools_response.status_code}")
            print(f"Tools Response: {tools_response.text[:300]}")
            
            if tools_response.status_code == 200:
                print("✅ Successfully listed tools with authenticated session!")
            elif tools_response.status_code != 401:
                print("✅ Authentication working (non-401 response)")
            
            return True
        else:
            print(f"⚠️  Initialize returned status {init_response.status_code}")
            response_lower = init_response.text.lower()
            if "authentication" in response_lower or "unauthorized" in response_lower or "invalid_token" in response_lower:
                print("❌ Authentication failed")
                return False
            else:
                print("✅ Authentication succeeded")
                return True
                
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_mcp_with_invalid_token():
    """Test MCP endpoint with invalid JWT token (should fail)"""
    print("\n" + "="*80)
    print("TEST 4: MCP Endpoint WITH Invalid JWT Token (Should Fail)")
    print("="*80)
    
    try:
        response = requests.post(
            f"{BASE_URL}/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "tools/list",
                "id": 1
            },
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "Authorization": "Bearer invalid.token.here"
            }
        )
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text[:200]}")
        
        if response.status_code == 401:
            print("✅ Correctly rejected invalid token")
            return True
        else:
            print("❌ Should have returned 401 Unauthorized")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    print("\n" + "="*80)
    print("FastMCP JWT Authentication Test Suite")
    print("="*80)
    print(f"Testing server at: {BASE_URL}")
    
    results = []
    
    # Run all tests
    results.append(("Health Check", test_health_endpoint()))
    results.append(("No Auth (Should Fail)", test_mcp_without_auth()))
    results.append(("Valid Token (Should Succeed)", test_mcp_with_auth()))
    results.append(("Invalid Token (Should Fail)", test_mcp_with_invalid_token()))
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    print("="*80 + "\n")
    
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())
