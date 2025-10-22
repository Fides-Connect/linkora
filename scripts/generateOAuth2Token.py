"""
Usage:
    python generateOAuth2Token.py <service_account_json_path> <env_file_path>

Description:
    This script generates an OAuth 2 access token using a Google Cloud service account JSON key file.
    The token will have the 'cloud-platform' scope by default.
    It writes the generated token to the specified .env file as OAUTH_ACCESS_TOKEN=<token>.

Arguments:
    <service_account_json_path> : Path to your Google Cloud service account JSON key file.
    <env_file_path>            : Path to the .env file to update.

Example:
    python generateOAuth2Token.py /path/to/service-account.json /path/to/.env

Output:
    Writes the generated OAuth 2 access token to the specified .env file as OAUTH_ACCESS_TOKEN=<token>.
"""

from google.oauth2 import service_account
import google.auth.transport.requests
import sys
from dotenv import set_key

def get_access_token(json_path, scopes):
    credentials = service_account.Credentials.from_service_account_file(
        json_path,
        scopes=scopes
    )
    auth_req = google.auth.transport.requests.Request()
    credentials.refresh(auth_req)
    return credentials.token

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python generateOAuth2Token.py <service_account_json_path> <env_file_path>")
        sys.exit(1)
    json_file_path = sys.argv[1]
    env_file_path = sys.argv[2]
    scopes = ["https://www.googleapis.com/auth/cloud-platform"]
    token = get_access_token(json_file_path, scopes)
    set_key(env_file_path, "OAUTH_ACCESS_TOKEN", token)
    print(f"OAUTH_ACCESS_TOKEN updated in {env_file_path}:\n{token}")