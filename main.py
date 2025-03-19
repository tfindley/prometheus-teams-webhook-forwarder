#!/opt/webhook-forwarder/.venv/bin/python

import yaml
import json
import requests
from fastapi import FastAPI, Request, HTTPException, Depends
from typing import Dict
from pydantic import BaseModel

# Initialize FastAPI app
app = FastAPI()

# Path to configuration file
CONFIG_FILE = "config.yaml"

def load_config():
    """Load webhook configuration from YAML file."""
    with open(CONFIG_FILE, "r") as file:
        return yaml.safe_load(file)  # Read and parse the YAML file

# Load configuration at startup
config = load_config()

def verify_auth(webhook_key: str, request: Request):
    """Verify authentication token if required for a webhook."""
    if 'auth' in config[webhook_key]:  # Check if authentication is configured
        expected_token = config[webhook_key]['auth']  # Retrieve expected token
        received_token = request.headers.get("Authorization")  # Extract token from request headers

        # Validate the received token against expected token
        if not received_token or received_token != f"Bearer {expected_token}":
            raise HTTPException(status_code=401, detail="Unauthorized")  # Return unauthorized error if invalid

# Define expected payload structure
class WebhookPayload(BaseModel):
    title: str       # Title of the alert message
    severity: str    # Severity level (e.g., Critical, Warning, Info)
    instance: str    # The instance that triggered the alert
    runbook_url: str # URL to the runbook or documentation for resolution

@app.post("/{webhook_key}")
async def handle_webhook(webhook_key: str, request: Request, payload: WebhookPayload):
    """Handle incoming webhook, validate authentication, transform payload, and forward it to Microsoft Teams."""
    if webhook_key not in config:
        raise HTTPException(status_code=404, detail="Webhook not found")  # Return 404 if webhook key is not found in config

    verify_auth(webhook_key, request)  # Perform authentication check if required

    teams_webhook_url = config[webhook_key]['teams_url']  # Retrieve the Microsoft Teams webhook URL from config

    # Format the incoming payload into Microsoft Teams Adaptive Card format
    teams_payload = {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",  # Set the content type for adaptive cards
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",  # Schema definition
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": [
                        {"type": "TextBlock", "size": "Large", "weight": "Bolder", "text": f"🚨 Alert: {payload.title}"},
                        {"type": "TextBlock", "text": f"📌 Severity: {payload.severity}"},
                        {"type": "TextBlock", "text": f"🖥️ Instance: {payload.instance}"},
                        {"type": "TextBlock", "text": f"🔗 [View Runbook]({payload.runbook_url})"}
                    ]
                }
            }
        ]
    }

    # Send the formatted message to the Microsoft Teams webhook
    response = requests.post(teams_webhook_url, json=teams_payload, headers={"Content-Type": "application/json"})

    # Check if the request to Microsoft Teams was successful
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=f"Failed to send Teams webhook: {response.text}")

    return {"status": "success", "message": "Webhook successfully forwarded to Teams"}

