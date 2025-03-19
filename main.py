import yaml
import json
import requests
from fastapi import FastAPI, Request, HTTPException, Depends
from typing import Dict, List, Optional
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

# Define expected structure for Alertmanager webhook payload
class Alert(BaseModel):
    status: str  # Status of the alert (firing or resolved)
    labels: Dict[str, str]  # Labels attached to the alert
    annotations: Dict[str, str]  # Annotations with descriptions, summaries, etc.
    startsAt: str  # Alert start time
    endsAt: str  # Alert end time
    generatorURL: Optional[str] = ""  # URL to the alert in Prometheus (optional)

class AlertmanagerPayload(BaseModel):
    receiver: str  # Alert receiver name
    status: str  # Global status (firing or resolved)
    alerts: List[Alert]  # List of alerts in this batch
    externalURL: str  # URL to Alertmanager dashboard
    version: str  # Alertmanager API version
    groupKey: str  # Unique group key for alerts

@app.post("/{webhook_key}")
async def handle_alertmanager_webhook(webhook_key: str, request: Request, payload: AlertmanagerPayload):
    """Handle incoming Alertmanager webhook, transform payload, and forward to Microsoft Teams."""
    if webhook_key not in config:
        raise HTTPException(status_code=404, detail="Webhook not found")  # Return 404 if webhook key is not found in config
    
    verify_auth(webhook_key, request)  # Perform authentication check if required
    
    teams_webhook_url = config[webhook_key]['teams_url']  # Retrieve the Microsoft Teams webhook URL from config
    
    for alert in payload.alerts:
        # Extract details from Alertmanager payload
        title = alert.annotations.get("summary", "No summary")
        severity = alert.labels.get("severity", "unknown")
        instance = alert.labels.get("instance", "unknown")
        job = alert.labels.get("job", "unknown")
        cluster = alert.labels.get("cluster", "N/A")
        environment = alert.labels.get("environment", "N/A")
        host = alert.labels.get("host", "unknown")
        runbook_url = alert.generatorURL or payload.externalURL  # Use generator URL if available, fallback to external Alertmanager URL
        
        # Format the payload into Microsoft Teams Adaptive Card format
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
                            {"type": "TextBlock", "size": "Large", "weight": "Bolder", "text": f"🚨 Alert: {title}"},
                            {"type": "TextBlock", "text": f"📌 Severity: {severity}"},
                            {"type": "TextBlock", "text": f"🖥️ Host: {host}"},
                            {"type": "TextBlock", "text": f"🔧 Job: {job}"},
                            {"type": "TextBlock", "text": f"🏢 Cluster: {cluster}"},
                            {"type": "TextBlock", "text": f"🌍 Environment: {environment}"},
                            {"type": "TextBlock", "text": f"🔗 [View in Prometheus]({runbook_url})"},
                            {"type": "TextBlock", "text": f"📝 Description: {alert.annotations.get('description', 'No description')}"}
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
    
    return {"status": "success", "message": "Alerts successfully forwarded to Teams"}

