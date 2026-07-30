#!/usr/bin/env python3
"""One-time setup: run locally to capture OAuth refresh token for calendar access."""
import json
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/calendar']

flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
creds = flow.run_local_server(port=0)

token_data = {
    'refresh_token': creds.refresh_token,
    'client_id': creds.client_id,
    'client_secret': creds.client_secret,
}

with open('oauth-token.json', 'w') as f:
    json.dump(token_data, f, indent=2)

print("Saved oauth-token.json")
print("Store this as an OpenShift secret:")
print("  oc create secret generic gcal-sync-oauth-token \\")
print("    --from-file=oauth-token.json=oauth-token.json \\")
print("    -n daam-shared")
