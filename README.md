# Google Calendar Event Sync

## This readme is here in the event that I'm not around to make the update for people and the cron stuff isnt working

Syncs AI Developer Events from the spreadsheet to Google Calendar.

## Features

- Downloads and parses events from the AI Developer Marketing events spreadsheet
- Filters to only incomplete events (not over yet)
- Extracts: event status, name, dates, location, and attendees
- Creates Google Calendar events for new events
- Updates existing calendar events with latest information
- Includes attendee names in event descriptions
- Color-codes events by type (Grassroots, Corporate, Meetups, etc.)

## Setup

### 1. Install dependencies

Using uv (recommended):
```bash
uv sync
```

Or using pip:
```bash
pip install -r requirements.txt
```

### 2. Get Google Calendar API credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. Enable the Google Calendar API:
   - Go to "APIs & Services" > "Library"
   - Search for "Google Calendar API"
   - Click "Enable"
4. Create OAuth 2.0 credentials:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth client ID"
   - Configure OAuth consent screen if prompted
   - Application type: "Desktop app"
   - Download the credentials
   - Save as `credentials.json` in this directory

**Note:** `credentials.json` is in `.gitignore` and will not be committed to the repository.

### 3. Download the latest CSV

1. Open the [events spreadsheet](https://docs.google.com/spreadsheets/d/1hGQ9PMMuMe_IcYlerJsm65BhqvvntMpwUyShRKJ9OaM/edit#gid=1024066477)
2. Go to the "Events" tab
3. File → Download → CSV
4. Save to `~/Downloads/AI BU Developer Marketing_Advocacy 2026 Events - Events.csv`

## Usage

Run the sync script:

```bash
uv run main.py
```

Or with python directly:
```bash
python main.py
```

On first run, it will:
1. Open a browser for Google authentication
2. Ask you to authorize calendar access
3. Save credentials to `token.pickle` for future runs (also in `.gitignore`)

The script will:
- Read the CSV from your Downloads folder
- Filter to incomplete events only
- Check which events already exist in your calendar
- Create new calendar events for missing ones
- Update existing calendar events with latest information
- Include attendee names in event descriptions

## Event Data Extracted

- **Complete**: Whether the event is over (TRUE/FALSE)
- **Event Name**: Name of the event
- **Dates**: Start and end dates
- **Location**: City, Country
- **Attendees**: Who from RH is going
- **Activities**: Talks, booths, workshops, etc.
- **Type**: Grassroots, Corporate, Meetups, Developer Days, Research

## Event Colors

Events are color-coded by type:
- Grassroots: Green
- Corporate: Blue
- Meetups: Yellow
- Developer Days: Orange
- Research: Red
