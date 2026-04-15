#!/usr/bin/env python3
"""
Google Calendar Event Sync
Syncs AI Developer Events from spreadsheet to Google Calendar
"""

import csv
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import pickle

# If modifying these scopes, delete the token.pickle file
SCOPES = ['https://www.googleapis.com/auth/calendar']

EVENT_COLORS = {
    'Grassroots': '10',
    'Corporate': '9',
    'Meetups': '5',
    'Developer Days': '6',
    'Research': '11'
}


def parse_date(date_str, year=2026):
    """Parse various date formats from the spreadsheet"""
    if not date_str or date_str.strip() in ['', 'TBD']:
        return None

    date_str = date_str.strip()

    if date_str.lower() in ['january', 'february', 'march', 'april', 'may', 'june',
                             'july', 'august', 'september', 'october', 'november', 'december']:
        return None

    if 'TBD' in date_str or 'week' in date_str.lower():
        return None

    date_str = date_str.replace('Arpil', 'April')
    date_str = date_str.replace('Novemeber', 'November')
    date_str = date_str.replace('–', '-')
    date_str = re.sub(r'(\d+)-(\d+)(st|nd|rd|th)', r'\1-\2', date_str)
    date_str = re.sub(r'(\d+)\s*-\s*(\d+)', r'\1-\2', date_str)

    if '-' in date_str and not date_str.startswith('-'):
        parts = date_str.split()
        if len(parts) >= 2:
            month_name = parts[0]
            day_range = parts[1]
            if '-' in day_range:
                try:
                    days = day_range.split('-')
                    start_day = re.sub(r'(st|nd|rd|th)$', '', days[0].strip())
                    end_day = re.sub(r'(st|nd|rd|th)$', '', days[1].strip())

                    start_date = datetime.strptime(f"{month_name} {start_day} {year}", "%B %d %Y")
                    end_date = datetime.strptime(f"{month_name} {end_day} {year}", "%B %d %Y")
                    return (start_date, end_date)
                except:
                    pass

    try:
        clean_date = re.sub(r'(st|nd|rd|th)\s*$', '', date_str)
        date = datetime.strptime(f"{clean_date} {year}", "%B %d %Y")
        return (date, date)
    except:
        pass

    return None


def get_calendar_service():
    """Get authenticated Google Calendar service"""
    creds = None
    token_path = 'token.pickle'

    if os.path.exists(token_path):
        with open(token_path, 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json'):
                print("Error: credentials.json not found!")
                print("Please download OAuth credentials from Google Cloud Console")
                return None

            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)

        with open(token_path, 'wb') as token:
            pickle.dump(creds, token)

    return build('calendar', 'v3', credentials=creds)


def clean_event_data(csv_path):
    """Extract and clean event data from CSV"""
    events = []

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for row in reader:
            if not row.get('Event Name') or row['Event Name'].strip() in ['', 'Q1', 'Q2', 'Q3', 'Q4']:
                continue

            complete = row.get('Complete', '').upper() == 'TRUE'
            event_type = row.get('Type', '')
            event_name = row.get('Event Name', '').strip()
            date_str = row.get('Date', '')
            city = row.get('City', '').strip()
            country = row.get('Country', '').strip()
            attendees = row.get('AI BU On-Site Staff', '').strip()
            description = row.get('Description', '').strip()
            activities = row.get('Activities', '').strip()

            if not event_name:
                continue

            dates = parse_date(date_str)
            if not dates:
                print(f"Warning: Could not parse date '{date_str}' for event '{event_name}'")
                continue

            start_date, end_date = dates
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
    """Find an existing event with the same name and date (±7 days)"""
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
    """Build the event body for Google Calendar"""
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
    """Create a Google Calendar event"""
    event = build_event_body(event_data)

    try:
        created_event = service.events().insert(calendarId=calendar_id, body=event).execute()
        return created_event
    except Exception as e:
        print(f"Error creating event: {e}")
        return None


def update_calendar_event(service, calendar_id, existing_event, event_data):
    """Update an existing Google Calendar event"""
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


def list_calendars(service):
    """List all available calendars"""
    try:
        calendar_list = service.calendarList().list().execute()
        return calendar_list.get('items', [])
    except Exception as e:
        print(f"Error listing calendars: {e}")
        return []


def select_calendar(service):
    """Interactive calendar selection"""
    print("\nAvailable Calendars:")
    calendars = list_calendars(service)

    if not calendars:
        print("No calendars found!")
        return None

    for i, cal in enumerate(calendars, 1):
        summary = cal.get('summary', 'Unnamed')
        is_primary = ' (PRIMARY)' if cal.get('primary', False) else ''
        print(f"  {i}. {summary}{is_primary}")

    while True:
        try:
            choice = input(f"\nSelect calendar (1-{len(calendars)}): ").strip()
            choice_num = int(choice)

            if 1 <= choice_num <= len(calendars):
                selected = calendars[choice_num - 1]
                print(f"\nUsing calendar: {selected['summary']}")
                return selected['id']
            else:
                print("Invalid choice. Try again.")
        except (ValueError, KeyboardInterrupt):
            print("\nCancelled.")
            return None


def main():
    """Main function to sync events"""
    csv_path = Path.home() / 'Downloads' / 'AI BU Developer Marketing_Advocacy 2026 Events - Events.csv'

    if not csv_path.exists():
        print(f"Error: CSV file not found at {csv_path}")
        return

    print("Reading and cleaning event data...")
    events = clean_event_data(csv_path)
    print(f"Found {len(events)} events")

    incomplete_events = [e for e in events if not e['complete']]
    print(f"Found {len(incomplete_events)} incomplete events to sync")

    print("\nAuthenticating with Google Calendar...")
    service = get_calendar_service()
    if not service:
        return

    calendar_id = select_calendar(service)
    if not calendar_id:
        print("No calendar selected. Exiting.")
        return

    print("\nSyncing events to calendar...")
    created_count = 0
    updated_count = 0
    failed_count = 0

    for event_data in incomplete_events:
        event_name = event_data['name']
        start_date = event_data['start_date']

        existing_event = find_existing_event(service, calendar_id, event_name, start_date)

        if existing_event:
            updated_event = update_calendar_event(service, calendar_id, existing_event, event_data)
            if updated_event:
                print(f"  [Updated] {event_name} ({start_date.strftime('%Y-%m-%d')})")
                updated_count += 1
            else:
                print(f"  [Failed to update] {event_name}")
                failed_count += 1
        else:
            created_event = create_calendar_event(service, calendar_id, event_data)
            if created_event:
                print(f"  [Created] {event_name} ({start_date.strftime('%Y-%m-%d')})")
                created_count += 1
            else:
                print(f"  [Failed to create] {event_name}")
                failed_count += 1

    print(f"\nSummary:")
    print(f"   Created: {created_count}")
    print(f"   Updated: {updated_count}")
    print(f"   Failed:  {failed_count}")
    print(f"   Total:   {len(incomplete_events)}")


if __name__ == '__main__':
    main()
