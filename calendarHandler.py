import datetime
import os
import pickle
import time
import ssl
import threading
from typing import TypedDict, Literal, List, Optional, Dict, Any, NotRequired
from concurrent.futures import ThreadPoolExecutor, as_completed
from google.oauth2.credentials import Credentials  # type: ignore
from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore
from google.auth.transport.requests import Request  # type: ignore
from googleapiclient.discovery import build, Resource  # type: ignore
from googleapiclient.errors import HttpError


class EventDateTime(TypedDict):
  dateTime: str
  timeZone: str


class CalendarEvent(TypedDict):
  summary: str
  colorId: NotRequired[Optional[str]]
  transparency: Literal['transparent', 'opaque']
  location: str
  description: str
  start: EventDateTime
  end: EventDateTime


class CalendarConnection:
  def __init__(self, credentialsPath: Optional[str] = None, tokenPath: Optional[str] = None) -> None:
    """Initializes the CalendarConnection class, setting up the Google Calendar API client.

    Args:
        credentialsPath (str, optional): Path to the credentials file. Defaults to 'credentials.json' in script directory.
        tokenPath (str, optional): Path to store the authentication token. Defaults to 'token.pickle' in script directory.

    Raises:
        FileNotFoundError: If the credentials file is not found.
        ValueError: If the credentials file is not valid for an installed app.
    """
    # Get the directory of the calling script
    import inspect
    caller_frame = inspect.stack()[1]
    caller_dir = os.path.dirname(os.path.abspath(caller_frame.filename))

    # Use provided paths or default to script directory
    if credentialsPath is None:
      credentialsPath = os.path.join(caller_dir, 'credentials.json')
    if tokenPath is None:
      tokenPath = os.path.join(caller_dir, 'token.pickle')

    if not os.path.exists(credentialsPath):
      raise FileNotFoundError(f"Credentials file not found: {credentialsPath}")

    SCOPES: List[str] = ['https://www.googleapis.com/auth/calendar']
    creds: Optional[Credentials] = None

    # Load existing token if available
    if os.path.exists(tokenPath):
      with open(tokenPath, 'rb') as token:
        creds = pickle.load(token)

    # If there are no (valid) credentials available, let the user log in
    if not creds or not creds.valid:  # type: ignore
      if creds and creds.expired and creds.refresh_token:  # type: ignore
        creds.refresh(Request())  # type: ignore
      else:
        try:
          flow = InstalledAppFlow.from_client_secrets_file(credentialsPath, SCOPES)  # type: ignore
          creds = flow.run_local_server(port=0)  # type: ignore
        except ValueError as e:
          if "Client secrets must be for a web or installed app" in str(e):
            raise ValueError(
                f"Invalid credentials file format. Please ensure you downloaded the correct "
                f"OAuth 2.0 client credentials for a 'Desktop application' from Google Cloud Console, "
                f"not a 'Web application'. The file should contain 'installed' client type."
            ) from e
          raise

      # Save the credentials for the next run
      with open(tokenPath, 'wb') as token:
        pickle.dump(creds, token)

    self.creds: Credentials = creds
    self.service: Resource = build('calendar', 'v3', credentials=self.creds)  # type: ignore
    self.verbose: bool = True  # Enable verbose logging by default
    self._lock = threading.Lock()  # Thread safety for API calls
    # Statistics tracking
    self._stats = {
        'created': 0,
        'updated': 0,
        'skipped': 0,
        'deleted': 0
    }
    self._stats_lock = threading.Lock()  # Thread safety for statistics

  def _log(self, message: str, force: bool = False) -> None:
    """Print a log message if verbose mode is enabled.

    Args:
      message: The message to print
      force: If True, print even if verbose mode is disabled (for errors/critical info)
    """
    if self.verbose or force:
      try:
        print(message)
      except UnicodeEncodeError:
        # Fallback for Windows console that doesn't support Unicode
        print(message.encode('ascii', 'replace').decode('ascii'))

  def get_stats(self) -> Dict[str, int]:
    """Get current statistics for event operations.

    Returns:
        Dict[str, int]: Dictionary with counts of created, updated, skipped, and deleted events.
    """
    with self._stats_lock:
      return self._stats.copy()

  def reset_stats(self) -> None:
    """Reset statistics counters to zero."""
    with self._stats_lock:
      self._stats = {
          'created': 0,
          'updated': 0,
          'skipped': 0,
          'deleted': 0
      }

  def _increment_stat(self, stat_name: str) -> None:
    """Increment a statistics counter in a thread-safe way.

    Args:
        stat_name: Name of the stat to increment ('created', 'updated', 'skipped', 'deleted')
    """
    with self._stats_lock:
      if stat_name in self._stats:
        self._stats[stat_name] += 1

  def _execute_with_retry(self, request, max_retries: int = 3, initial_delay: float = 1.0):  # type: ignore
    """Execute a Google API request with exponential backoff retry logic.

    Args:
      request: The Google API request object to execute
      max_retries: Maximum number of retry attempts (default: 3)
      initial_delay: Initial delay in seconds before first retry (default: 1.0)

    Returns:
      The result of the API request execution

    Raises:
      Exception: If all retry attempts fail
    """
    last_exception = None
    delay = initial_delay
    had_errors = False

    for attempt in range(max_retries + 1):
      try:
        # Use lock to ensure thread-safe API calls
        with self._lock:
          result = request.execute()  # type: ignore
        # If we had errors but succeeded after retry, log success
        if had_errors and attempt > 0:
          self._log(f"   ✅ Success after {attempt} retry/retries", force=True)
        return result  # type: ignore
      except ssl.SSLError as e:
        had_errors = True
        last_exception = e
        error_msg = str(e)

        if attempt < max_retries:
          self._log(f"⚠️  SSL error (attempt {attempt + 1}/{max_retries + 1}): {error_msg}", force=True)
          self._log(f"   Retrying in {delay:.1f} seconds...", force=True)
          time.sleep(delay)
          delay *= 2  # Exponential backoff
        else:
          self._log(f"❌ SSL error after {max_retries + 1} attempts: {error_msg}", force=True)
          raise
      except HttpError as e:
        # Don't retry HttpError (like 404, 403, etc.) - these won't be fixed by retrying
        raise
      except Exception as e:
        # For other exceptions, retry with backoff
        had_errors = True
        last_exception = e
        error_msg = str(e)

        if attempt < max_retries:
          self._log(f"⚠️  Error (attempt {attempt + 1}/{max_retries + 1}): {error_msg}", force=True)
          self._log(f"   Retrying in {delay:.1f} seconds...", force=True)
          time.sleep(delay)
          delay *= 2  # Exponential backoff
        else:
          self._log(f"❌ Error after {max_retries + 1} attempts: {error_msg}", force=True)
          raise

    # This should never be reached, but just in case
    if last_exception:
      raise last_exception

  def _getExistingEventInCalendar(self, start: datetime.datetime, end: datetime.datetime,
                                  calendarId: str) -> Optional[Dict[str, Any]]:
    """Check if an event exists in a specific calendar at the given time slot.

    Args:
        start (datetime.datetime): The start time to check.
        end (datetime.datetime): The end time to check.
        calendarId (str): The calendar ID to check.

    Returns:
        Optional[Dict[str, Any]]: The existing event if found, None otherwise.
    """
    try:
      # Query events for the entire day to catch all events
      day_start = start.replace(hour=0, minute=0, second=0, microsecond=0)
      day_end = day_start + datetime.timedelta(days=1)

      request = self.service.events().list(  # type: ignore
          calendarId=calendarId,
          timeMin=day_start.isoformat() + 'Z',
          timeMax=day_end.isoformat() + 'Z',
          singleEvents=True,
          orderBy='startTime'
      )
      events_result: Dict[str, Any] = self._execute_with_retry(request)  # type: ignore

      events: List[Dict[str, Any]] = events_result.get('items', [])  # type: ignore

      for event in events:  # type: ignore
        if 'start' not in event or 'end' not in event:
          continue

        event_start_raw: Optional[str] = event['start'].get('dateTime')  # type: ignore
        event_end_raw: Optional[str] = event['end'].get('dateTime')  # type: ignore

        if not event_start_raw or not event_end_raw:
          continue

        # Parse datetime strings - handle different timezone formats
        try:
          if event_start_raw.endswith('Z'):  # type: ignore
            event_start_dt = datetime.datetime.fromisoformat(
                event_start_raw.replace('Z', '+00:00')).replace(tzinfo=None)  # type: ignore
            event_end_dt = datetime.datetime.fromisoformat(
                event_end_raw.replace('Z', '+00:00')).replace(tzinfo=None)  # type: ignore
          elif '+' in event_start_raw:
            event_start_dt = datetime.datetime.fromisoformat(event_start_raw.split('+')[0])  # type: ignore
            event_end_dt = datetime.datetime.fromisoformat(event_end_raw.split('+')[0])  # type: ignore
          else:
            event_start_dt = datetime.datetime.fromisoformat(event_start_raw)  # type: ignore
            event_end_dt = datetime.datetime.fromisoformat(event_end_raw)  # type: ignore

          # Check if times match exactly
          if event_start_dt == start and event_end_dt == end:
            return event  # type: ignore

        except (ValueError, KeyError):
          continue

      return None
    except HttpError:
      return None

  def _getExistingEvent(self, start: datetime.datetime, end: datetime.datetime,
                        calendarId: str = 'primary') -> Optional[Dict[str, Any]]:
    """Check if an event already exists at the given time slot.

    Args:
        start (datetime.datetime): The start time to check.
        end (datetime.datetime): The end time to check.
        calendarId (str, optional): The calendar ID to check. Defaults to 'primary'.

    Returns:
        Optional[Dict[str, Any]]: The existing event if found, None otherwise.
    """
    return self._getExistingEventInCalendar(start, end, calendarId)

  def _eventNeedsUpdate(self, existing_event: Dict[str, Any], new_event: CalendarEvent) -> bool:
    """Check if an existing event needs to be updated.

    Args:
        existing_event (Dict[str, Any]): The existing event from the calendar.
        new_event (CalendarEvent): The new event data to compare against.

    Returns:
        bool: True if the event needs updating, False if it's already in the correct state.
    """
    # Compare summary
    if existing_event.get('summary', '') != new_event.get('summary', ''):
      return True

    # Compare location
    if existing_event.get('location', '') != new_event.get('location', ''):
      return True

    # Compare description
    if existing_event.get('description', '') != new_event.get('description', ''):
      return True

    # Compare transparency (busy/free)
    if existing_event.get('transparency', 'opaque') != new_event.get('transparency', 'opaque'):
      return True

    # Compare color (colorId can be None or a string)
    existing_color = existing_event.get('colorId')
    new_color = new_event.get('colorId')
    if existing_color != new_color:
      return True

    # If all properties match, no update needed
    return False

  def _deleteEventFromCalendar(self, event_id: str, calendarId: str) -> bool:
    """Delete an event from a specific calendar.

    Args:
        event_id (str): The event ID to delete.
        calendarId (str): The calendar ID to delete from.

    Returns:
        bool: True if successful, False otherwise.
    """
    try:
      request = self.service.events().delete(calendarId=calendarId, eventId=event_id)  # type: ignore
      self._execute_with_retry(request)  # type: ignore
      self._increment_stat('deleted')
      return True
    except (HttpError, ssl.SSLError):
      return False

  def createEventWithCleanup(self, name: str, start: datetime.datetime, end: datetime.datetime,
                             target_calendarId: str, other_calendarId: Optional[str] = None,
                             description: str = '', location: str = 'Online',
                             color: Optional[str] = None, busy: bool = True) -> str:
    """Creates an event in the target calendar and removes it from other calendar if it exists there.

    Args:
        name (str): The name of the event.
        start (datetime.datetime): The start time of the event.
        end (datetime.datetime): The end time to check.
        target_calendarId (str): The calendar where the event should be.
        other_calendarId (Optional[str]): The other calendar to check and clean up from.
        description (str, optional): A description of the event. Defaults to ''.
        location (str, optional): The location of the event. Defaults to 'Online'.
        color (Optional[str], optional): Color ID for the event. Defaults to None.
        busy (bool, optional): Whether the event should show as busy. Defaults to True.

    Returns:
        str: The ID of the created or updated event.
    """
    # Check if event exists in the wrong calendar and delete it
    if other_calendarId:
      wrong_calendar_event = self._getExistingEventInCalendar(start, end, other_calendarId)
      if wrong_calendar_event:
        self._deleteEventFromCalendar(wrong_calendar_event['id'], other_calendarId)

    # Now create/update in the correct calendar
    return self.createEvent(name, start, end, target_calendarId, description, location, color, busy)

  def createEvent(
          self,
          name: str,
          start: datetime.datetime,
          end: datetime.datetime,
          calendarId: str = 'primary',
          description: str = '',
          location: str = 'Online',
          color: Optional[str] = None,
          busy: bool = True) -> str:
    """Creates an event in the Google Calendar or updates existing one if found.

    Args:
        name (str): The name of the event.
        start (datetime.datetime): The start time of the event.
        end (datetime.datetime): The end time of the event.
        calendarId (str, optional): The ID of the calendar to create the event in. Defaults to 'primary'.
        description (str, optional): A description of the event. Defaults to ''.
        location (str, optional): The location of the event. Defaults to 'Online'.
        color (Optional[str], optional): Color ID for the event. Defaults to None.
        busy (bool, optional): Whether the event should show as busy. Defaults to True.

    Returns:
        str: The ID of the created or updated event.

    Raises:
        HttpError: If an error occurs during the API call.
    """
    # Check if event already exists
    existing_event = self._getExistingEvent(start, end, calendarId)

    event: CalendarEvent = {
        'summary': name,
        'location': location,
        'transparency': 'opaque' if busy else 'transparent',
        'description': description,
        'start': {
            'dateTime': start.isoformat(),
            'timeZone': 'Europe/Berlin',
        },
        'end': {
            'dateTime': end.isoformat(),
            'timeZone': 'Europe/Berlin',
        },
    }

    if color is not None:
      event['colorId'] = color

    try:
      if existing_event:
        # Only update if the event has changed
        if self._eventNeedsUpdate(existing_event, event):
          request = self.service.events().update(  # type: ignore
              calendarId=calendarId,
              eventId=existing_event['id'],
              body=event
          )
          updated_event = self._execute_with_retry(request)  # type: ignore
          self._increment_stat('updated')
          return updated_event['id']  # type: ignore
        else:
          # Event already exists in correct form, no update needed
          self._increment_stat('skipped')
          return existing_event['id']  # type: ignore
      else:
        # Create new event
        request = self.service.events().insert(calendarId=calendarId, body=event)  # type: ignore
        created_event = self._execute_with_retry(request)  # type: ignore
        self._increment_stat('created')
        return created_event['id']  # type: ignore
    except ssl.SSLError as e:
      # SSL errors that weren't resolved by retries
      error_msg = str(e).split('\n')[0] if '\n' in str(e) else str(e)
      self._log(f"Error creating event '{name}': {error_msg}", force=True)
      return f"SSL Error"
    except HttpError as e:
      if e.resp.status == 404:
        self._log(f"❌ Calendar not found (HTTP 404)", force=True)
        self._log(f"   Event: '{name}'", force=True)
        self._log(f"   Calendar ID: {calendarId}", force=True)
        self._log(f"   💡 Check your CALENDAR_ID in .env file", force=True)
      elif e.resp.status == 403:
        self._log(f"❌ Access denied (HTTP 403)", force=True)
        self._log(f"   Event: '{name}'", force=True)
        self._log(f"   💡 Check calendar sharing permissions", force=True)
      else:
        # Show only the first line of error, not the full HTML
        error_msg = str(e).split('\n')[0] if '\n' in str(e) else str(e)
        self._log(f"❌ HTTP {e.resp.status} Error: {error_msg}", force=True)
      return f"Error {e.resp.status}"

  def createEventsBatch(self, events_data: List[Dict[str, Any]],
                        calendarId: str = 'primary', batch_size: int = 10) -> List[str]:
    """Creates multiple events using batch requests for better performance.

    Args:
        events_data (List[Dict[str, Any]]): List of event data dictionaries containing event details.
        calendarId (str, optional): The ID of the calendar to create events in. Defaults to 'primary'.
        batch_size (int, optional): Number of requests per batch. Defaults to 10.

    Returns:
        List[str]: List of created event IDs.
    """
    from googleapiclient.http import BatchHttpRequest  # type: ignore

    event_ids: List[str] = []

    # Process events in batches
    for i in range(0, len(events_data), batch_size):
      batch_events = events_data[i:i + batch_size]
      batch_request = BatchHttpRequest()
      batch_results: List[str] = []
      batch_errors: List[str] = []
      batch_stats = {'created': 0, 'updated': 0, 'skipped': 0}

      def callback(request_id: str, response: Dict[str, Any], exception: Optional[Exception]) -> None:
        if exception is not None:
          batch_errors.append(str(exception))
          batch_results.append(str(exception))
        else:
          batch_results.append(response['id'])
          # Determine if this was a create or update based on request_id metadata
          # We'll track this separately since batch doesn't preserve context well

      # Add requests to batch
      for j, event_data in enumerate(batch_events):
        # Check if event already exists
        existing_event = self._getExistingEvent(
            event_data['start_dt'],
            event_data['end_dt'],
            calendarId
        )

        event: CalendarEvent = {
            'summary': event_data['name'],
            'location': event_data['location'],
            'transparency': 'opaque' if event_data['busy'] else 'transparent',
            'description': event_data['description'],
            'start': {
                'dateTime': event_data['start_dt'].isoformat(),
                'timeZone': 'Europe/Berlin',
            },
            'end': {
                'dateTime': event_data['end_dt'].isoformat(),
                'timeZone': 'Europe/Berlin',
            },
        }

        if event_data.get('color') is not None:
          event['colorId'] = event_data['color']

        if existing_event:
          # Only update if the event has changed
          if self._eventNeedsUpdate(existing_event, event):
            batch_request.add(
                self.service.events().update(  # type: ignore
                    calendarId=calendarId,
                    eventId=existing_event['id'],
                    body=event
                ),
                callback=callback,
                request_id=str(i * batch_size + j)
            )
            batch_stats['updated'] += 1
          else:
            # Event already in correct form, skip it
            batch_results.append(existing_event['id'])
            batch_stats['skipped'] += 1
        else:
          batch_request.add(
              self.service.events().insert(calendarId=calendarId, body=event),  # type: ignore
              callback=callback,
              request_id=str(i * batch_size + j)
          )
          batch_stats['created'] += 1

      # Execute batch
      try:
        batch_request.execute(http=self.service._http)  # type: ignore
        # Update global stats with batch stats
        with self._stats_lock:
          self._stats['created'] += batch_stats['created']
          self._stats['updated'] += batch_stats['updated']
          self._stats['skipped'] += batch_stats['skipped']
        # Log any batch errors
        for error in batch_errors:
          self._log(f"Error creating event: {error}", force=True)
        event_ids.extend(batch_results)
      except HttpError as e:
        # Clean error message without verbose HTML
        error_code = e.resp.status if hasattr(e, 'resp') else 'Unknown'
        if error_code == 404:
          self._log(f"⚠️  Batch API endpoint not available (HTTP 404)")
          self._log(f"   Falling back to individual processing for this batch...")
        else:
          self._log(f"⚠️  Batch request failed (HTTP {error_code})")
          self._log(f"   Falling back to individual processing for this batch...")

        # Fallback to individual requests for this batch
        for event_data in batch_events:
          try:
            event_id = self.createEvent(
                event_data['name'],
                event_data['start_dt'],
                event_data['end_dt'],
                calendarId,
                event_data['description'],
                event_data['location'],
                event_data.get('color'),
                event_data['busy']
            )
            event_ids.append(event_id)
          except Exception as ex:
            # Show clean error without verbose details
            error_msg = str(ex).split('\n')[0] if '\n' in str(ex) else str(ex)
            self._log(f"   ❌ Failed: {event_data['name']}", force=True)
            event_ids.append(f"Error: {error_msg}")

    return event_ids

  def createEventsThreaded(self, events_data: List[Dict[str, Any]],
                           calendarId: str = 'primary', max_workers: int = 5) -> List[str]:
    """Creates multiple events using threading for concurrent execution.

    Args:
        events_data (List[Dict[str, Any]]): List of event data dictionaries containing event details.
        calendarId (str, optional): The ID of the calendar to create events in. Defaults to 'primary'.
        max_workers (int, optional): Maximum number of concurrent threads. Defaults to 5.

    Returns:
        List[str]: List of created event IDs.
    """
    event_ids: List[str] = []

    def create_single_event(event_data: Dict[str, Any]) -> str:
      try:
        return self.createEvent(
            event_data['name'],
            event_data['start_dt'],
            event_data['end_dt'],
            calendarId,
            event_data['description'],
            event_data['location'],
            event_data.get('color'),
            event_data['busy']
        )
      except Exception as e:
        self._log(f"Error creating event '{event_data['name']}': {e}", force=True)
        return str(e)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
      # Submit all tasks
      future_to_event = {
          executor.submit(create_single_event, event_data): event_data
          for event_data in events_data
      }

      # Collect results as they complete
      for future in as_completed(future_to_event):
        event_data = future_to_event[future]
        try:
          event_id = future.result()
          event_ids.append(event_id)
        except Exception as e:
          self._log(f"Thread execution error for event '{event_data['name']}': {e}", force=True)
          event_ids.append(str(e))

    return event_ids

  def createEventsThreadedWithCleanup(self, events_data: List[Dict[str, Any]],
                                      busy_calendarId: str, free_calendarId: str,
                                      max_workers: int = 5) -> List[str]:
    """Creates multiple events using threading, placing them in correct calendars and cleaning up from wrong ones.

    Args:
        events_data (List[Dict[str, Any]]): List of event data dictionaries containing event details.
        busy_calendarId (str): The calendar ID for busy events.
        free_calendarId (str): The calendar ID for free events.
        max_workers (int, optional): Maximum number of concurrent threads. Defaults to 5.

    Returns:
        List[str]: List of created event IDs.
    """
    event_ids: List[str] = []

    def create_single_event_with_cleanup(event_data: Dict[str, Any]) -> str:
      try:
        # Determine target and other calendar based on busy status
        if event_data['busy']:
          target_calendar = busy_calendarId
          other_calendar = free_calendarId
        else:
          target_calendar = free_calendarId
          other_calendar = busy_calendarId

        return self.createEventWithCleanup(
            event_data['name'],
            event_data['start_dt'],
            event_data['end_dt'],
            target_calendar,
            other_calendar,
            event_data['description'],
            event_data['location'],
            event_data.get('color'),
            event_data['busy']
        )
      except Exception as e:
        error_msg = str(e).split('\n')[0] if '\n' in str(e) else str(e)
        self._log(f"Error creating event '{event_data['name']}': {error_msg}", force=True)
        return str(e)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
      # Submit all tasks
      future_to_event = {
          executor.submit(create_single_event_with_cleanup, event_data): event_data
          for event_data in events_data
      }

      # Collect results as they complete
      for future in as_completed(future_to_event):
        event_data = future_to_event[future]
        try:
          event_id = future.result()
          event_ids.append(event_id)
        except Exception as e:
          error_msg = str(e).split('\n')[0] if '\n' in str(e) else str(e)
          self._log(f"Thread execution error for event '{event_data['name']}': {error_msg}", force=True)
          event_ids.append(str(e))

    return event_ids
