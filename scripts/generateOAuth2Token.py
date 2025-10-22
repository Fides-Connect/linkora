"""
Usage:
    python generateOAuth2Token.py <service_account_json_path> [env_file_path]

Description:
    This script generates an OAuth 2 access token using a Google Cloud service account JSON key file.
    The token will have the 'cloud-platform' scope by default.

Arguments:
    <service_account_json_path> : Path to your Google Cloud service account JSON key file.
    [env_file_path]            : Optional path to the .env file to update. Defaults to '.env'.

Example:
    python generateOAuth2Token.py /path/to/service-account.json
    python generateOAuth2Token.py /path/to/service-account.json /path/to/.env

Output:
    Prints the generated OAuth 2 access token to stdout.
"""

import json
from google.oauth2 import service_account
import google.auth.transport.requests
import sys
import os

def get_access_token(json_path, scopes):
    credentials = service_account.Credentials.from_service_account_file(
        json_path,
        scopes=scopes
    )
    auth_req = google.auth.transport.requests.Request()
    credentials.refresh(auth_req)
    return credentials.token

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python generateOAuth2Token.py <service_account_json_path>")
        sys.exit(1)
    json_file_path = sys.argv[1]
    scopes = ["https://www.googleapis.com/auth/cloud-platform"]
    token = get_access_token(json_file_path, scopes)
    os.environ["OAUTH_ACCESS_TOKEN"] = token
    print(f"OAUTH_ACCESS_TOKEN environment variable set to:\n{token}")