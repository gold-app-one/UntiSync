from api import APIConnection
from calendarHandler import CalendarConnection
from constants import NAME_REPLACEMENTS
from dotenv import load_dotenv
import os
import time
from typing import List, Dict, Any, Optional

load_dotenv()

SURNAME = os.getenv('SURNAME')
FORENAME = os.getenv('FORENAME')
USERNAME = os.getenv('UNTIS_USERNAME')
PASSWORD = os.getenv('UNTIS_PASSWORD')
SCHOOL = os.getenv('UNTIS_SCHOOL')
CALENDAR_ID = os.getenv('CALENDAR_ID')
FREE_CALENDAR_ID = os.getenv('FREE_CALENDAR_ID')
SCHOOL_LOCATION = os.getenv('SCHOOL_LOCATION')
PROCESSING_METHOD = os.getenv('PROCESSING_METHOD', 'auto')  # auto, threaded, batch, individual
VERBOSE = os.getenv('VERBOSE', 'true').lower() in ('true', '1', 'yes')  # Enable/disable verbose logging

GRAY = '8'
RED = '11'

def log(message: str, force: bool = False) -> None:
  """Print a log message if verbose mode is enabled.

  Args:
    message: The message to print
    force: If True, print even if verbose mode is disabled (for errors/critical info)
  """
  if VERBOSE or force:
    try:
      print(message)
    except UnicodeEncodeError:
      # Fallback for Windows console that doesn't support Unicode
      print(message.encode('ascii', 'replace').decode('ascii'))

def apply_name_replacement(subject_name: str) -> str:
  """Apply name replacements from constants.py to a subject name.

  Args:
    subject_name: The original subject name

  Returns:
    The replaced name if found in NAME_REPLACEMENTS, otherwise the original name
  """
  return NAME_REPLACEMENTS.get(subject_name, subject_name)

def process_events_optimized(calendar: CalendarConnection, events_data: List[Dict[str, Any]],
    busy_calendar_id: str, free_calendar_id: Optional[str] = None,
    method: str = 'auto', verbose: bool = True) -> None:
  """Process calendar events using optimized methods.

  Args:
    calendar: CalendarConnection instance
    events_data: List of event data dictionaries
    busy_calendar_id: Google Calendar ID for busy events
    free_calendar_id: Google Calendar ID for free events (if None, uses busy_calendar_id)
    method: Processing method - 'auto', 'threaded', 'batch', or 'individual'
    verbose: Enable verbose logging
  """
  # Set verbose mode in calendar handler
  calendar.verbose = verbose
  log(f"Processing {len(events_data)} events using {method} method...")
  start_time = time.time()

  # If no separate free calendar, use the same calendar for all events
  use_dual_calendar = free_calendar_id is not None and free_calendar_id != busy_calendar_id

  try:
    if method == 'auto':
      # Automatically choose based on number of events
      # Using threaded by default as it's more reliable than batch
      # Batch processing may not be available on all Google API configurations
      method = 'threaded'

    if method == 'threaded':
      log("Using threaded processing...")
      if use_dual_calendar and free_calendar_id:
        log(f"📅 Busy events → Main Calendar")
        log(f"📅 Free events → Free Calendar")
        event_ids = calendar.createEventsThreadedWithCleanup(events_data, busy_calendar_id, free_calendar_id, max_workers=5)
      else:
        event_ids = calendar.createEventsThreaded(events_data, busy_calendar_id, max_workers=5)
    elif method == 'batch':
      log("Using batch processing...")
      log("⚠️  Note: If batch fails, it will automatically fall back to individual processing")
      if use_dual_calendar and free_calendar_id:
        log("⚠️  Warning: Batch mode doesn't support dual-calendar cleanup. Using threaded mode instead.")
        event_ids = calendar.createEventsThreadedWithCleanup(events_data, busy_calendar_id, free_calendar_id, max_workers=5)
      else:
        event_ids = calendar.createEventsBatch(events_data, busy_calendar_id, batch_size=10)
    elif method == 'individual':
      log("Using individual processing...")
      event_ids: List[str] = []
      for event_data in events_data:
        try:
          if use_dual_calendar and free_calendar_id:
            # Determine target calendar and cleanup from the other
            target_calendar = busy_calendar_id if event_data['busy'] else free_calendar_id
            other_calendar = free_calendar_id if event_data['busy'] else busy_calendar_id
            event_id = calendar.createEventWithCleanup(
              name=event_data['name'],
              start=event_data['start_dt'],
              end=event_data['end_dt'],
              target_calendarId=target_calendar,
              other_calendarId=other_calendar,
              location=event_data['location'],
              description=event_data['description'],
              color=event_data['color'],
              busy=event_data['busy']
            )
          else:
            event_id = calendar.createEvent(
              name=event_data['name'],
              start=event_data['start_dt'],
              end=event_data['end_dt'],
              location=event_data['location'],
              description=event_data['description'],
              calendarId=busy_calendar_id,
              color=event_data['color'],
              busy=event_data['busy']
            )
          event_ids.append(event_id)
        except Exception as e:
          log(f"Failed to create event '{event_data['name']}': {e}", force=True)
          event_ids.append(str(e))
    else:
      raise ValueError(f"Unknown method: {method}")

    successful_events = [id for id in event_ids if not (id.startswith('Error') or 'Error' in id)]
    failed_events = [id for id in event_ids if id.startswith('Error') or 'Error' in id]

    elapsed_time = time.time() - start_time
    log(f"✅ Successfully processed {len(successful_events)} events in {elapsed_time:.2f} seconds.", force=True)
    if failed_events:
      log(f"❌ Failed to process {len(failed_events)} events.", force=True)

  except Exception as e:
    log(f"Optimized processing failed: {e}", force=True)
    if method != 'individual':
      log("Falling back to individual event processing...", force=True)
      process_events_optimized(calendar, events_data, busy_calendar_id, free_calendar_id, 'individual', verbose)
    else:
      log("Individual processing also failed. Please check your configuration.", force=True)

def main() -> None:
  if CALENDAR_ID is None:
    log('❌ Missing CALENDAR_ID', force=True)
    return
  if SCHOOL_LOCATION is None:
    log('⚠️  Missing SCHOOL_LOCATION', force=True)

  # Determine if we're using dual calendars
  use_dual_calendar = FREE_CALENDAR_ID is not None and FREE_CALENDAR_ID != CALENDAR_ID
  if use_dual_calendar:
    log(f"🗓️  Using dual-calendar mode:")
    log(f"   • Busy events → Main Calendar")
    log(f"   • Free events → Free Calendar")
  else:
    log(f"🗓️  Using single-calendar mode")

  conn = APIConnection(SURNAME, FORENAME, USERNAME, PASSWORD, SCHOOL)
  try:
    calendar = CalendarConnection(credentialsPath='credentials.json', tokenPath='token.pickle')
  except FileNotFoundError as e:
    log(f"❌ Error: {e}", force=True)
    log("Please ensure the credentials.json file is in the correct location.", force=True)
    return
  except ValueError as e:
    log(f"❌ Credentials Error: {e}", force=True)
    log("Please download the correct OAuth 2.0 credentials from Google Cloud Console.", force=True)
    return
  except Exception as e:
    log(f"❌ Unexpected error: {e}", force=True)
    return

  lessons = conn.getLessons()

  # Prepare all event data for batch/threaded processing
  events_data: List[Dict[str, Any]] = []
  busy_count = 0
  free_count = 0

  for lesson in lessons:
    busy = not lesson.isCancelled()
    if busy:
      busy_count += 1
    else:
      free_count += 1

    color = (RED if lesson.isExam() else None) if busy else GRAY
    # Apply name replacements from constants.py
    raw_subject = lesson.getSubject()
    name = apply_name_replacement(raw_subject)
    start = lesson.getStart()
    end = lesson.getEnd()
    description = lesson.getRoom()
    location = SCHOOL_LOCATION if busy and SCHOOL_LOCATION is not None else ''

    events_data.append({
      'name': name,
      'start_dt': start,
      'end_dt': end,
      'location': location,
      'description': description,
      'color': color,
      'busy': busy
    })

  log(f"📊 Found {len(events_data)} total events: {busy_count} busy, {free_count} free")
  process_events_optimized(calendar, events_data, CALENDAR_ID, FREE_CALENDAR_ID, method=PROCESSING_METHOD, verbose=VERBOSE)
if __name__ == '__main__':
  main()