#!/usr/bin/env python3
"""
Admin Token Generator
Generates a secure random token for the admin interface.

Usage:
    python scripts/generate_admin_token.py
"""
import secrets

def generate_admin_token():
    """Generate a secure admin token."""
    token = secrets.token_urlsafe(32)
    print("=" * 70)
    print("Generated Admin Token:")
    print("=" * 70)
    print(token)
    print("=" * 70)
    print("\nAdd this to your .env file:")
    print(f"ADMIN_SECRET_KEY={token}")
    print("\nOr set as environment variable:")
    print(f"export ADMIN_SECRET_KEY='{token}'")
    print("=" * 70)
    return token

if __name__ == '__main__':
    generate_admin_token()
