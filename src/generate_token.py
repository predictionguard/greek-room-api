#!/usr/bin/env python3
"""
Script to generate JWT tokens for authenticating with the Greek Room MCP Server.
Usage: python generate_token.py [--client-id CLIENT_ID] [--expires-days DAYS]
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
import jwt
from dotenv import load_dotenv
import argparse

# Add src directory to path for imports
sys.path.append(str(Path(__file__).parent))

# Load environment variables
load_dotenv()

def generate_jwt_token(
    client_id: str = "default-client",
    expires_days: int = 365,
    subject: str = None,
    additional_claims: dict = None
) -> str:
    """
    Generate a JWT token for MCP server authentication.
    
    Args:
        client_id: Unique identifier for the client
        expires_days: Number of days until token expires
        subject: Subject claim (usually user/client identifier)
        additional_claims: Additional claims to include in the token
    
    Returns:
        JWT token string
    """
    secret = os.getenv("JWT_SECRET_KEY")
    algorithm = os.getenv("JWT_ALGORITHM", "HS256")
    issuer = os.getenv("JWT_ISSUER", "greek-room-mcp")
    audience = os.getenv("JWT_AUDIENCE", "greek-room-client")
    
    if not secret:
        raise ValueError("JWT_SECRET_KEY not found in environment variables")
    
    # Token expiration time (UTC, timezone-aware)
    now = datetime.now(timezone.utc)
    exp = now + timedelta(days=expires_days)
    
    # Build token payload
    payload = {
        "iss": issuer,
        "aud": audience,
        "sub": subject or client_id,
        "client_id": client_id,
        "exp": exp,
        "iat": now,
    }
    
    # Add any additional claims
    if additional_claims:
        payload.update(additional_claims)
    
    # Generate token
    token = jwt.encode(payload, secret, algorithm=algorithm)
    
    return token

def main():
    parser = argparse.ArgumentParser(
        description="Generate JWT tokens for Greek Room MCP Server authentication"
    )
    parser.add_argument(
        "--client-id",
        type=str,
        default="default-client",
        help="Unique identifier for the client (default: default-client)"
    )
    parser.add_argument(
        "--expires-days",
        type=int,
        default=365,
        help="Number of days until token expires (default: 365)"
    )
    parser.add_argument(
        "--subject",
        type=str,
        help="Subject claim (usually user/client identifier)"
    )
    parser.add_argument(
        "--scopes",
        type=str,
        help="Comma-separated list of scopes (e.g., 'read,write')"
    )
    
    args = parser.parse_args()
    
    # Build additional claims
    additional_claims = {}
    if args.scopes:
        additional_claims["scopes"] = args.scopes.split(",")
    
    try:
        token = generate_jwt_token(
            client_id=args.client_id,
            expires_days=args.expires_days,
            subject=args.subject,
            additional_claims=additional_claims if additional_claims else None
        )
        
        exp_date = (datetime.now(timezone.utc) + timedelta(days=args.expires_days)).strftime("%Y-%m-%d")
        
        print("\n" + "="*80)
        print("JWT TOKEN GENERATED SUCCESSFULLY")
        print("="*80)
        print(f"\nClient ID: {args.client_id}")
        print(f"Expires: {exp_date} ({args.expires_days} days from now)")
        if args.scopes:
            print(f"Scopes: {args.scopes}")
        print("\n" + "-"*80)
        print("TOKEN:")
        print("-"*80)
        print(token)
        print("-"*80)
        print("\nUSAGE:")
        print("Include this token in the Authorization header of your requests:")
        print(f"Authorization: Bearer {token}")
        print("\nOr configure your MCP client with this token.")
        print("="*80 + "\n")
        
    except Exception as e:
        print(f"Error generating token: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
