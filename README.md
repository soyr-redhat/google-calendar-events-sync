# Google Calendar Event Sync

Syncs AI Developer Marketing events from a Google Spreadsheet to Google Calendar, running as an OpenShift CronJob.

## How It Works

1. Reads event data from Google Sheets using a **Service Account**
2. Writes to Google Calendar using **OAuth** (your Red Hat Google account)
3. Filters to incomplete (upcoming) events
4. Creates, updates, or deletes events in Google Calendar
5. Color-codes events by type (Grassroots=Green, Corporate=Blue, Meetups=Yellow, Developer Days=Orange, Research=Red)

## Prerequisites

- A GCP project with Calendar API and Sheets API enabled
- A GCP Service Account with a JSON key
- The [events spreadsheet](https://docs.google.com/spreadsheets/d/1hGQ9PMMuMe_IcYlerJsm65BhqvvntMpwUyShRKJ9OaM/edit#gid=1024066477) shared with the service account email (Viewer)
- Access to the `daam-shared` OpenShift namespace
- A quay.io repository for the container image

## Setup

### 1. Create a GCP Service Account

1. Go to [Google Cloud Console](https://console.cloud.google.com/) — project: `itpc-gcp-product-all-claude`
2. Navigate to "IAM & Admin" > "Service Accounts"
3. Click "Create Service Account", name it (e.g., `gcal-sync`)
4. Create a JSON key and download it

### 2. Enable APIs

In the GCP project, enable:
- Google Calendar API
- Google Sheets API

### 3. Share the Spreadsheet

Share the events spreadsheet with the service account email
(e.g., `gcal-sync@itpc-gcp-product-all-claude.iam.gserviceaccount.com`) as **Viewer**.

### 4. Generate OAuth Token

Run the one-time setup script to authenticate your Google account for calendar access:

```bash
uv sync --extra setup
uv run setup_oauth.py
```

This opens a browser for Google login and saves `oauth-token.json`.

### 5. Deploy to OpenShift

```bash
# Create secrets
oc create secret generic gcal-sync-sa-key \
  --from-file=service-account.json=/path/to/key.json \
  -n daam-shared

oc create secret generic gcal-sync-oauth-token \
  --from-file=oauth-token.json=oauth-token.json \
  -n daam-shared

# Edit k8s/configmap.yaml — set your CALENDAR_ID
# Edit k8s/cronjob.yaml — set your quay.io image path

# Apply manifests
oc apply -f k8s/ -n daam-shared
```

### 6. Set Up CI/CD

1. Create a quay.io repository named `gcal-sync`
2. In the GitHub repo settings, add secrets:
   - `QUAY_USERNAME` — your quay.io username or robot account
   - `QUAY_PASSWORD` — your quay.io password or robot token
3. Push to `main` to trigger the first build

## Configuration

| Environment Variable | Description | Default |
|---|---|---|
| `CALENDAR_ID` | Target Google Calendar ID | **(required)** |
| `GOOGLE_SHEET_ID` | Google Spreadsheet ID | `1hGQ9PMMuMe_IcYlerJsm65BhqvvntMpwUyShRKJ9OaM` |
| `SHEET_NAME` | Sheet tab name | `Events` |
| `EVENT_YEAR` | Year for date parsing | Current year |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to service account key | `/etc/secrets/service-account.json` |
| `OAUTH_TOKEN_PATH` | Path to OAuth token JSON | `/etc/secrets/oauth/oauth-token.json` |

## Local Development

```bash
uv sync

export CALENDAR_ID="your-calendar-id@group.calendar.google.com"
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
export OAUTH_TOKEN_PATH="oauth-token.json"

uv run main.py
```

## Manual Trigger on OpenShift

```bash
oc create job gcal-sync-manual --from=cronjob/gcal-sync -n daam-shared
oc logs -f job/gcal-sync-manual -n daam-shared
```

## Token Refresh

The OAuth refresh token lasts as long as it's used within 6 months. The monthly CronJob
keeps it alive. If the GCP project's OAuth consent screen is in "Testing" mode, tokens
expire after 7 days — set it to "Production" mode to avoid this.
