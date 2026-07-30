#!/usr/bin/env python3
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from google.oauth2.credentials import Credentials as UserCredentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SHEET_SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
CALENDAR_SCOPES = ['https://www.googleapis.com/auth/calendar']

EVENT_COLORS = {
    'Grassroots': '10',
    'Corporate': '9',
    'Meetups': '5',
    'Developer Days': '6',
    'Research': '11'
}


def parse_date(date_str, year=None):
    if year is None:
        year = int(os.environ.get('EVENT_YEAR', datetime.now().year))

    if not date_str or date_str.strip() in ['', 'TBD']:
        return None

    date_str = date_str.strip()

    if date_str.lower() in ['january', 'february', 'march', 'april', 'may', 'june',
                             'july', 'august', 'september', 'october', 'november', 'december']:
        return None

    if 'TBD' in date_str or 'week' in date_str.lower():
        return None

    try:
        clean_date = re.sub(r'(st|nd|rd|th)\s*$', '', date_str)
        dt = datetime.strptime(f"{clean_date} {year}", "%B %d %Y")
        return dt
    except Exception:
        pass

    return None


def get_sheet_credentials():
    sa_path = os.environ.get(
        'GOOGLE_APPLICATION_CREDENTIALS',
        '/etc/secrets/service-account.json'
    )
    if not os.path.exists(sa_path):
        print(f"Error: Service account key not found at {sa_path}")
        sys.exit(1)

    return ServiceAccountCredentials.from_service_account_file(sa_path, scopes=SHEET_SCOPES)


def get_calendar_credentials():
    token_path = os.environ.get('OAUTH_TOKEN_PATH', '/etc/secrets/oauth-token.json')
    if not os.path.exists(token_path):
        print(f"Error: OAuth token not found at {token_path}")
        sys.exit(1)

    with open(token_path) as f:
        token_data = json.load(f)

    creds = UserCredentials(
        token=None,
        refresh_token=token_data['refresh_token'],
        client_id=token_data['client_id'],
        client_secret=token_data['client_secret'],
        token_uri='https://oauth2.googleapis.com/token',
        scopes=CALENDAR_SCOPES,
    )
    creds.refresh(Request())
    return creds


def fetch_sheet_data(creds):
    sheet_id = os.environ.get('GOOGLE_SHEET_ID', '1hGQ9PMMuMe_IcYlerJsm65BhqvvntMpwUyShRKJ9OaM')
    sheet_name = os.environ.get('SHEET_NAME', 'Events')

    service = build('sheets', 'v4', credentials=creds)
    result = service.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range=sheet_name,
    ).execute()

    rows = result.get('values', [])
    if not rows:
        print("Error: No data found in spreadsheet")
        return []

    headers = rows[0]
    data = []
    for row in rows[1:]:
        padded = row + [''] * (len(headers) - len(row))
        data.append(dict(zip(headers, padded)))

    return data


def clean_event_data(rows, year=None):
    if year is None:
        year = int(os.environ.get('EVENT_YEAR', datetime.now().year))

    events = []

    for row in rows:
        if not row.get('Event Name') or row['Event Name'].strip() in ['', 'Q1', 'Q2', 'Q3', 'Q4']:
            continue

        complete = row.get('Complete', '').upper() == 'TRUE'
        event_type = row.get('Type', '')
        event_name = row.get('Event Name', '').strip()
        start_dates = row.get('Start Date', '').strip()
        end_dates = row.get('End Date', '').strip()
        city = row.get('City', '').strip()
        country = row.get('Country', '').strip()
        attendees = row.get('AI BU On-Site Staff', '').strip()
        description = row.get('Description', '').strip()
        activities = row.get('Activities', '').strip()

        if not event_name:
            continue

        start_date = parse_date(start_dates, year)
        end_date = parse_date(end_dates, year)

        if not start_date:
            print(f"Warning: Could not parse start date for event '{event_name}'")
            continue

        if not end_date:
            print(f"Oops! End date not found, using start date for one day event")
            end_date = start_date

        location_parts = [p for p in [city, country] if p]
        location = ', '.join(location_parts) if location_parts else ''

        events.append({
            'complete': complete,
            'type': event_type,
            'name': event_name,
            'start_date': start_date,
            'end_date': end_date,
            'location': location,
            'attendees': attendees,
            'description': description,
            'activities': activities
        })

    return events


def find_existing_event(service, calendar_id, event_name, start_date):
    time_min = (start_date - timedelta(days=7)).isoformat() + 'Z'
    time_max = (start_date + timedelta(days=7)).isoformat() + 'Z'

    try:
        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            q=event_name,
            singleEvents=True
        ).execute()

        events = events_result.get('items', [])

        for event in events:
            if event.get('summary', '') == event_name:
                return event

        return None
    except Exception as e:
        print(f"Error checking for existing event: {e}")
        return None


def build_event_body(event_data):
    description_parts = []
    if event_data['description']:
        description_parts.append(event_data['description'])
    if event_data['activities']:
        description_parts.append(f"Activities: {event_data['activities']}")
    if event_data['attendees']:
        description_parts.append(f"RH Attendees: {event_data['attendees']}")

    description = '\n\n'.join(description_parts)

    event = {
        'summary': event_data['name'],
        'location': event_data['location'],
        'description': description,
        'start': {
            'date': event_data['start_date'].strftime('%Y-%m-%d'),
            'timeZone': 'America/New_York',
        },
        'end': {
            'date': (event_data['end_date'] + timedelta(days=1)).strftime('%Y-%m-%d'),
            'timeZone': 'America/New_York',
        },
    }

    if event_data['type'] in EVENT_COLORS:
        event['colorId'] = EVENT_COLORS[event_data['type']]

    return event


def create_calendar_event(service, calendar_id, event_data):
    event = build_event_body(event_data)

    try:
        created_event = service.events().insert(calendarId=calendar_id, body=event).execute()
        return created_event
    except Exception as e:
        print(f"Error creating event: {e}")
        return None


def update_calendar_event(service, calendar_id, existing_event, event_data):
    event = build_event_body(event_data)

    try:
        updated_event = service.events().update(
            calendarId=calendar_id,
            eventId=existing_event['id'],
            body=event
        ).execute()
        return updated_event
    except Exception as e:
        print(f"Error updating event: {e}")
        return None


def delete_orphaned_events(service, calendar_id, active_names):
    today = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    deleted_count = 0
    page_token = None

    while True:
        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=today,
            singleEvents=True,
            pageToken=page_token
        ).execute()

        for event in events_result.get('items', []):
            summary = event.get('summary', '')
            if summary and summary not in active_names:
                try:
                    service.events().delete(
                        calendarId=calendar_id,
                        eventId=event['id']
                    ).execute()
                    print(f"  [Deleted] {summary}")
                    deleted_count += 1
                except Exception as e:
                    print(f"  [Failed to delete] {summary}: {e}")

        page_token = events_result.get('nextPageToken')
        if not page_token:
            break

    return deleted_count


def main():
    calendar_id = os.environ.get('CALENDAR_ID')
    if not calendar_id:
        print("Error: CALENDAR_ID environment variable is required")
        sys.exit(1)

    year = int(os.environ.get('EVENT_YEAR', datetime.now().year))

    print("Authenticating with service account for Sheets...")
    sheet_creds = get_sheet_credentials()

    print("Authenticating with OAuth for Calendar...")
    cal_creds = get_calendar_credentials()

    print("Fetching event data from Google Sheets...")
    raw_rows = fetch_sheet_data(sheet_creds)
    if not raw_rows:
        print("No data to process. Exiting.")
        return

    print("Cleaning event data...")
    events = clean_event_data(raw_rows, year)
    print(f"Found {len(events)} events")

    incomplete_events = [e for e in events if not e['complete']]
    print(f"Found {len(incomplete_events)} incomplete events to sync")

    cal_service = build('calendar', 'v3', credentials=cal_creds)

    active_names = {e['name'] for e in incomplete_events}

    print("\nSyncing events to calendar...")
    created_count = 0
    updated_count = 0
    failed_count = 0

    for event_data in incomplete_events:
        event_name = event_data['name']
        start_date = event_data['start_date']
        end_date = event_data['end_date']

        existing_event = find_existing_event(cal_service, calendar_id, event_name, start_date)

        if existing_event:
            updated_event = update_calendar_event(cal_service, calendar_id, existing_event, event_data)
            if updated_event:
                print(f"  [Updated] {event_name} ({start_date.strftime('%Y-%m-%d')}) - ({end_date.strftime('%Y-%m-%d')})")
                updated_count += 1
            else:
                print(f"  [Failed to update] {event_name}")
                failed_count += 1
        else:
            created_event = create_calendar_event(cal_service, calendar_id, event_data)
            if created_event:
                print(f"  [Created] {event_name} ({start_date.strftime('%Y-%m-%d')}) - ({end_date.strftime('%Y-%m-%d')})")
                created_count += 1
            else:
                print(f"  [Failed to create] {event_name}")
                failed_count += 1

    print("\nCleaning up orphaned events...")
    deleted_count = delete_orphaned_events(cal_service, calendar_id, active_names)

    print(f"\nSummary:")
    print(f"   Created: {created_count}")
    print(f"   Updated: {updated_count}")
    print(f"   Deleted: {deleted_count}")
    print(f"   Failed:  {failed_count}")
    print(f"   Total:   {len(incomplete_events)}")

    if failed_count > 0:
        sys.exit(1)


if __name__ == '__main__':
    main()
