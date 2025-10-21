import json
from google.oauth2 import service_account
import google.auth.transport.requests

def get_access_token(json_path, scopes):
    credentials = service_account.Credentials.from_service_account_file(
        json_path,
        scopes=scopes
    )
    auth_req = google.auth.transport.requests.Request()
    credentials.refresh(auth_req)
    return credentials.token

if __name__ == "__main__":
    json_file = "./gen-lang-client-0859968110-7e4295cc002e.json"
    scopes = ["https://www.googleapis.com/auth/cloud-platform"]
    token = get_access_token(json_file, scopes)
    print(token)