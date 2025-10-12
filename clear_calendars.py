"""
Clear Calendar Helper Script
=============================
This script deletes all events from both the busy and free calendars.

WARNING: This action cannot be undone! All events will be permanently deleted.

Usage:
    python clear_calendars.py

    Or with confirmation prompt:
    python clear_calendars.py --confirm
"""

from calendarHandler import CalendarConnection
from dotenv import load_dotenv
import os
import sys
import datetime

# Load environment variables
load_dotenv()

CALENDAR_ID = os.getenv('CALENDAR_ID')
FREE_CALENDAR_ID = os.getenv('FREE_CALENDAR_ID')


def log(message: str) -> None:
  """Print a log message."""
  try:
    print(message)
  except UnicodeEncodeError:
    # Fallback for Windows console that doesn't support Unicode
    print(message.encode('ascii', 'replace').decode('ascii'))


def get_all_events(calendar: CalendarConnection, calendar_id: str, calendar_name: str) -> list:  # type: ignore
  """Get all events from a calendar.

  Args:
      calendar: CalendarConnection instance
      calendar_id: Google Calendar ID
      calendar_name: Display name for the calendar

  Returns:
      List of event dictionaries
  """
  try:
    log(f"\n📅 Fetching events from {calendar_name}...")

    # Get events from far past to far future
    time_min = datetime.datetime(2020, 1, 1).isoformat() + 'Z'
    time_max = datetime.datetime(2030, 12, 31).isoformat() + 'Z'

    request = calendar.service.events().list(  # type: ignore
        calendarId=calendar_id,
        timeMin=time_min,
        timeMax=time_max,
        maxResults=2500,  # Maximum allowed by API
        singleEvents=True,
        orderBy='startTime'
    )

    events_result = calendar._execute_with_retry(request)  # type: ignore
    events = events_result.get('items', [])  # type: ignore

    log(f"   Found {len(events)} events")  # type: ignore
    return events  # type: ignore

  except Exception as e:
    log(f"   ❌ Error fetching events: {e}")
    return []  # type: ignore


def delete_events(calendar: CalendarConnection, calendar_id: str, events: list, calendar_name: str) -> int:  # type: ignore
  """Delete all events from a calendar.

  Args:
      calendar: CalendarConnection instance
      calendar_id: Google Calendar ID
      events: List of events to delete
      calendar_name: Display name for the calendar

  Returns:
      Number of events successfully deleted
  """
  if not events:
    log(f"   ℹ️  No events to delete from {calendar_name}")
    return 0

  log(f"\n🗑️  Deleting {len(events)} events from {calendar_name}...")  # type: ignore
  deleted_count = 0
  failed_count = 0

  for i, event in enumerate(events, 1):  # type: ignore
    event_id = event.get('id')  # type: ignore
    event_name = event.get('summary', 'Untitled')  # type: ignore

    if not event_id:
      continue

    try:
      success = calendar._deleteEventFromCalendar(event_id, calendar_id)  # type: ignore
      if success:
        deleted_count += 1
        if i % 10 == 0 or i == len(events):  # type: ignore
          log(f"   Progress: {i}/{len(events)} deleted")  # type: ignore
      else:
        failed_count += 1
        log(f"   ⚠️  Failed to delete: {event_name}")
    except Exception as e:
      failed_count += 1
      log(f"   ❌ Error deleting '{event_name}': {e}")

  log(f"\n✅ Deleted {deleted_count} events from {calendar_name}")
  if failed_count > 0:
    log(f"⚠️  Failed to delete {failed_count} events")

  return deleted_count


def main():
  """Main function to clear both calendars."""

  # Check for confirmation flag
  require_confirm = '--confirm' in sys.argv

  log("=" * 60)
  log("🗑️  CLEAR CALENDARS - UntiSync Helper Script")
  log("=" * 60)

  # Validate environment variables
  if not CALENDAR_ID:
    log("❌ Error: CALENDAR_ID not set in .env file")
    sys.exit(1)

  # Check if dual-calendar mode is enabled
  using_dual_calendar = FREE_CALENDAR_ID and FREE_CALENDAR_ID != CALENDAR_ID

  if using_dual_calendar:
    log(f"\n📋 Mode: Dual-Calendar")
    log(f"   Busy Calendar ID: {CALENDAR_ID}")
    log(f"   Free Calendar ID: {FREE_CALENDAR_ID}")
  else:
    log(f"\n📋 Mode: Single-Calendar")
    log(f"   Calendar ID: {CALENDAR_ID}")

  # Confirmation prompt
  if require_confirm:
    log("\n⚠️  WARNING: This will permanently delete ALL events from your calendar(s)!")
    log("This action CANNOT be undone.\n")

    response = input("Are you sure you want to continue? (yes/no): ").strip().lower()
    if response not in ['yes', 'y']:
      log("\n❌ Operation cancelled")
      sys.exit(0)
  else:
    log("\n💡 Tip: Use --confirm flag to add a confirmation prompt")

  # Initialize calendar connection
  log("\n🔐 Connecting to Google Calendar...")
  try:
    calendar = CalendarConnection()
    calendar.verbose = False  # Disable verbose logging for cleaner output
    log("   ✅ Connected successfully")
  except Exception as e:
    log(f"❌ Failed to connect: {e}")
    sys.exit(1)

  total_deleted = 0

  # Clear busy calendar
  log("\n" + "=" * 60)
  log("BUSY CALENDAR")
  log("=" * 60)

  busy_events = get_all_events(calendar, CALENDAR_ID, "Busy Calendar")  # type: ignore
  total_deleted += delete_events(calendar, CALENDAR_ID, busy_events, "Busy Calendar")

  # Clear free calendar if in dual-calendar mode
  if using_dual_calendar:
    log("\n" + "=" * 60)
    log("FREE CALENDAR")
    log("=" * 60)

    free_events = get_all_events(calendar, FREE_CALENDAR_ID, "Free Calendar")  # type: ignore
    total_deleted += delete_events(calendar, FREE_CALENDAR_ID, free_events, "Free Calendar")  # type: ignore

  # Final summary
  log("\n" + "=" * 60)
  log("SUMMARY")
  log("=" * 60)
  log(f"✅ Total events deleted: {total_deleted}")

  if using_dual_calendar:
    log(f"   - Busy Calendar: {len(busy_events)} events deleted")  # type: ignore
    log(f"   - Free Calendar: {len(free_events)} events deleted")  # type: ignore

  log("\n🎉 Calendar clearing complete!")
  log("=" * 60)


if __name__ == "__main__":
  try:
    main()
  except KeyboardInterrupt:
    log("\n\n❌ Operation cancelled by user")
    sys.exit(1)
  except Exception as e:
    log(f"\n\n❌ Unexpected error: {e}")
    sys.exit(1)
