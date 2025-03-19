# Webhook Forwarder for Microsoft Teams

## Preface

This webhook forwader is designed to handle posting webhooks between AlertManager and Microsoft Teams following the change to the way Microsoft are allowing webhooks. This forwarder will reformat the standard AlertManager output and paste it to Microsoft Temas

## Dislaimer

This script was written largely in conjunction with ChatGPT. This was a quick and dirty solution that *should* work.

## File Breakdown

- **config.yaml** - Configuration file which stores your destination webhook, and a basic bearer authentication for the inbound webhook
- **main.py** - Python script
- **README.md** - This file
- **requirements.txt** - Python requirements file (generated from pip freeze)
- **webhook-forwader.service** - Service file to be installed in /etc/systemd/system/

## Requirements

- Python3

- Port 8000 available - this can be changed in the .service file

This forwarder has been tested on Ubuntu 24.04 and RHEL 9, but should work on others.

**WARNING:** This service is designed to forward webhooks sent to it locally to an external Teams Endpoint. While you 'could' use this as an external http port forwarder, there is no TLS layer - you will need to provide this yourself via traefik or nginx or another reverse proxy.

## Installation

### Manual execution

```bash
sudo mkdir /opt/webhook-forwader
```

- Create the python virtual environment

```bash
python3 -m venv /opt/webhook-forwader/.venv
```

- Activate the Python Virtual Environment
```bash
. /opt/webhook-forwader/.venv/bin/activate
```bash

- Upgrade PIP and Install the python requirements

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

- Deactivate the Python Virtual Environment

```bash
deactivate
```

- Download the main.py file into /opt/webhook-forwader

- Make file executable

```bash
sudo chmod +x /opt/webhook-forwarder
```

### As a service - systemd

- Create a new system user for the webhook forwader

```bash
sudo useradd --system --no-create-home --shell /sbin/nologin webhook-forwarder
```

- Create a webhook-forwader directory in /opt

```bash
sudo mkdir /opt/webhook-forwader
```

- Create the python virtual environment

```bash
python3 -m venv /opt/webhook-forwader/.venv
```

- Activate the Python Virtual Environment

```bash
. /opt/webhook-forwader/.venv/bin/activate
```

- Upgrade PIP and Install the python requirements

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

- Deactivate the Python Virtual Environment

```bash
deactivate
```

- Download the main.py file into /opt/webhook-forwader

- Make file executable

```bash
sudo chmod +x /opt/webhook-forwarder
```

- Create the configuration file - `/opt/webhook-forwader/config.yaml`

```yaml
webhook1:
  teams_url: "https://prod-105.westeurope.logic.azure.com:443/workflows/..."
  auth: "mysecrettoken"

webhook2:
  teams_url: "http://path.to-another-teams-webhook.com"
```

Note that the 'auth' field is optional, but recommended.

- Change ownership of all files

```bash
sudo chmod -R webhook-forwader: /opt/webhook-forwader
```

- Copy the service file into systemd, set its permissions, reload systemd and start/enable the service

```bash
sudo cp webhook-forwarder.service /etc/systemd/system/webhook/webhook-forwarder.service
sudo chown root: /etc/systemd/system/webhook/webhook-forwarder.service
sudo systemctl daemon-reload
sudo systemctl enable webhook-forwarder
sudo systemctl start webhook-forwarder
sudo systemctl status webhook-forwarder
```

- Verify that it is running

```bash
journalctl -u webhook-forwarder -f
```


## Configure Alert Manager

Modify your Alertmanager configuration file (alertmanager.yml) to include a webhook receiver pointing to your FastAPI webhook forwarder

```yaml
global:
  resolve_timeout: 5m

route:
  receiver: 'teams_webhook'
  group_by: ['alertname', 'service']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 3h

receivers:
  - name: 'teams_webhook'
    webhook_configs:
      - url: 'http://your-webhook-server:8000/alertmanager_teams'
        send_resolved: true
        http_config:
          bearer_token: "your_auth_token_here"

```

 Ensure FastAPI Configuration Matches Alertmanager

In your config.yaml for FastAPI, you need to define the corresponding webhook key:

```yaml
alertmanager_teams:
  teams_url: "https://outlook.office.com/webhook/YOUR_TEAMS_WEBHOOK_URL"
  auth: "your_auth_token_here"

```

- Restart Alert Manager

After modifying the configuration, restart Alertmanager to apply the changes:

```bash
systemctl restart alertmanager
```

Check logs to ensure there are no errors


```bash
journalctl -u alertmanager -f
```

- Test an Alert

Trigger a test alert in Prometheus, or manually send a payload to Alertmanager:

```bash
curl -X POST -H "Content-Type: application/json" -d '{
  "receiver": "teams_webhook",
  "status": "firing",
  "alerts": [
    {
      "status": "firing",
      "labels": {
        "alertname": "TestAlert",
        "service": "backend",
        "severity": "critical"
      },
      "annotations": {
        "summary": "Test Alert",
        "description": "This is a test alert to verify the webhook."
      },
      "startsAt": "2025-03-19T10:00:00Z",
      "endsAt": "0001-01-01T00:00:00Z",
      "generatorURL": "http://prometheus.example.com/graph"
    }
  ],
  "externalURL": "http://alertmanager.example.com",
  "version": "4"
}' "http://your-alertmanager-server:9093/api/v1/alerts"

```

- Verify Alert in Microsoft Teams

If everything is configured correctly, you should see an Adaptive Card message in your Teams channel.

If there are issues, check the logs of both Alertmanager and FastAPI.


## Troubleshooting

Check FastAPI logs:

```bash
journalctl -u webhook-forwarder -f
```

Check Alertmanager logs:

```bash
journalctl -u alertmanager -f
```

If FastAPI is not receiving alerts, try sending a direct request to its webhook:

```bash
curl -X POST "http://your-webhook-server:8000/alertmanager_teams" \
  -H "Authorization: Bearer your_auth_token_here" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Test Alert",
    "severity": "Critical",
    "instance": "server1.example.com",
    "runbook_url": "https://example.com/runbook"
  }'
```
