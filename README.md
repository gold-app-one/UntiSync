# UntiSync - WebUntis to Google Calendar Sync

Automatically sync your WebUntis school schedule to Google Calendar with support for dual calendars (busy/free events), threaded processing, and customizable subject names.

## Features

✨ **Automatic Sync** - Fetches lessons from WebUntis and creates/updates Google Calendar events  
📅 **Dual-Calendar Mode** - Separate calendars for busy and free/cancelled events  
⚡ **Performance Optimized** - Threaded processing with SSL-safe API calls  
🎨 **Custom Colors** - Red for exams, grey for cancelled classes  
📝 **Name Replacements** - Replace cryptic subject codes with friendly names  
🔄 **Smart Updates** - Updates existing events, removes duplicates  

---

## Quick Start

### 1. Install Python Packages

```bash
pip install -r requirements.txt
```

This installs:

- `webuntis` - WebUntis API client
- `google-auth-oauthlib` - Google OAuth authentication
- `google-auth-httplib2` - Google API HTTP transport
- `google-api-python-client` - Google Calendar API
- `python-dotenv` - Environment variable management

**Verify installation:**

```bash
python -c "import webuntis; import google.oauth2.credentials; import google_auth_oauthlib; import googleapiclient; import dotenv; print('✅ All packages installed!')"
```

### 2. Set Up Google Calendar API

#### Step 2.1: Enable Google Calendar API

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. Enable the **Google Calendar API**:
   - Navigate to "APIs & Services" > "Library"
   - Search for "Google Calendar API"
   - Click "Enable"

#### Step 2.2: Create OAuth Credentials

1. Go to "APIs & Services" > "Credentials"
2. Click "+ CREATE CREDENTIALS" > "OAuth client ID"
3. **Application type**: Desktop app
4. **Name**: UntiSync (or any name)
5. Click "Create"
6. Download the credentials JSON file
7. **Save as `credentials.json`** in the project root folder

**Important**: Must be "Desktop app", NOT "Web application"!

### 3. Create `.env` Configuration File

Create a file named `.env` in the project root with your credentials:

```env
# WebUntis Credentials (Required)
SURNAME=YourLastName
FORENAME=YourFirstName
UNTIS_USERNAME=your_username
UNTIS_PASSWORD=your_password
UNTIS_SCHOOL=your_school_name

# Google Calendar IDs (Required)
CALENDAR_ID=your_main_calendar_id@group.calendar.google.com

# Optional: Separate calendar for free/cancelled events
FREE_CALENDAR_ID=your_free_calendar_id@group.calendar.google.com

# School Location (Optional)
SCHOOL_LOCATION=Your School Name, City

# Processing Method (Optional)
# Options: auto, threaded, batch, individual
# Default: auto (uses threaded)
PROCESSING_METHOD=auto

# Verbose Logging (Optional)
# Options: true, false
# Default: true
VERBOSE=true
```

#### How to Find Your Calendar ID

1. Open [Google Calendar](https://calendar.google.com)
2. Click the **⚙️ Settings** icon (top right)
3. Select **Settings** from the menu
4. In the left sidebar, click on the calendar name
5. Scroll down to **"Integrate calendar"**
6. Copy the **Calendar ID** (looks like: `abc123@group.calendar.google.com`)

**For dual-calendar mode:**

- Create two separate calendars in Google Calendar
- Get the Calendar ID for each
- Set `CALENDAR_ID` for busy events
- Set `FREE_CALENDAR_ID` for cancelled/free events

### 4. Configure Subject Name Replacements (Optional)

Edit `constants.py` to replace WebUntis subject codes with friendly names:

```python
NAME_REPLACEMENTS: dict[str, str] = {
  'M': 'Mathematics',
  'PHY': 'Physics',
  'CH': 'Chemistry',
  'L12Ch-T': 'Chemistry LK',
  'G12Ge-G': 'History',
}
```

See `NAME_REPLACEMENT_GUIDE.md` for detailed examples.

### 5. Run the Sync

```bash
python main.py
```

**First run**: Browser will open for Google Calendar authorization. Sign in and grant permissions.

---

## Configuration Reference

### Required Files

| File | Purpose | Location |
|------|---------|----------|
| `credentials.json` | Google OAuth credentials | Project root |
| `.env` | WebUntis & Calendar configuration | Project root |

### Environment Variables

#### Required Variables

```env
# WebUntis login credentials
SURNAME=YourLastName           # Your last name in WebUntis
FORENAME=YourFirstName         # Your first name in WebUntis
UNTIS_USERNAME=username        # WebUntis username
UNTIS_PASSWORD=password        # WebUntis password
UNTIS_SCHOOL=schoolname        # School identifier in WebUntis

# Google Calendar ID (your target calendar)
CALENDAR_ID=abc@group.calendar.google.com
```

#### Optional Variables

```env
# Dual-Calendar Mode: Separate calendar for cancelled events
FREE_CALENDAR_ID=def@group.calendar.google.com

# Event Location: Added to busy events
SCHOOL_LOCATION=Example High School, Berlin

# Processing Method: How events are created
# - auto: Automatically choose best method (default: threaded)
# - threaded: Parallel processing with thread safety (recommended)
# - batch: Batch API requests (may not work on all configurations)
# - individual: Process one-by-one (slowest, most reliable)
PROCESSING_METHOD=auto

# Verbose Logging: Show detailed output
# - true: Show all logs (default)
# - false: Only show critical messages
VERBOSE=true
```

### Example `.env` File

**Single-Calendar Mode:**

```env
SURNAME=Smith
FORENAME=John
UNTIS_USERNAME=john.smith
UNTIS_PASSWORD=MySecurePassword123
UNTIS_SCHOOL=example-school
CALENDAR_ID=abc123def456@group.calendar.google.com
SCHOOL_LOCATION=Example High School
PROCESSING_METHOD=auto
VERBOSE=true
```

**Dual-Calendar Mode:**

```env
SURNAME=Schmidt
FORENAME=Anna
UNTIS_USERNAME=anna.schmidt
UNTIS_PASSWORD=SecurePass456
UNTIS_SCHOOL=meine-schule
CALENDAR_ID=main-calendar@group.calendar.google.com
FREE_CALENDAR_ID=free-calendar@group.calendar.google.com
SCHOOL_LOCATION=Gymnasium Beispiel
PROCESSING_METHOD=threaded
VERBOSE=true
```

---

## Usage

### Basic Sync

```bash
python main.py
```

### Clear All Events (Before Re-sync)

```bash
# With confirmation prompt
python clear_calendars.py --confirm

# Without confirmation (immediate deletion)
python clear_calendars.py
```

### Check for Errors

If sync fails, check:

1. ✅ `credentials.json` exists and is for "Desktop app"
2. ✅ `.env` file has all required variables
3. ✅ Calendar IDs are correct
4. ✅ WebUntis credentials are valid
5. ✅ Google Calendar API is enabled

---

## Features & Configuration

### Dual-Calendar Mode

Separate busy events from cancelled/free events:

**Setup:**

1. Create two calendars in Google Calendar
2. Set both `CALENDAR_ID` and `FREE_CALENDAR_ID` in `.env`

**Behavior:**

- **Busy events** → Main Calendar (`CALENDAR_ID`)
- **Cancelled/Free events** → Free Calendar (`FREE_CALENDAR_ID`)
- Automatically moves events if status changes
- Cleans up duplicates across calendars

See `DUAL_CALENDAR_GUIDE.md` for details.

### Processing Methods

Control how events are synced:

| Method | Speed | Reliability | Use Case |
|--------|-------|-------------|----------|
| `auto` | Fast | High | Default - automatically chooses `threaded` |
| `threaded` | Fast | High | **Recommended** - parallel processing with thread safety |
| `batch` | Fast | Medium | Batch API calls (may fail, auto-fallback) |
| `individual` | Slow | Highest | Process one event at a time |

Set in `.env`:

```env
PROCESSING_METHOD=threaded
```

See `OPTIMIZATION_GUIDE.md` for performance comparison.

### Subject Name Replacements

Replace WebUntis subject codes with custom names:

**Edit `constants.py`:**

```python
NAME_REPLACEMENTS: dict[str, str] = {
  'M': 'Mathematics',
  'PHY': '⚛️ Physics',
  'L12Ch-T': 'Chemistry LK',
}
```

**Then sync:**

```bash
python main.py
```

See `NAME_REPLACEMENT_GUIDE.md` for examples and troubleshooting.

### Verbose Logging

Control output verbosity:

**Verbose Mode (default):**

```env
VERBOSE=true
```

Shows: Detailed progress, event counts, timing, warnings

**Quiet Mode:**

```env
VERBOSE=false
```

Shows: Only errors and final summary

---

## Troubleshooting

### "CALENDAR_ID not set in .env file"

- Create `.env` file in project root
- Add `CALENDAR_ID=your_calendar_id@group.calendar.google.com`

### "credentials.json not found"

- Download OAuth credentials from Google Cloud Console
- Save as `credentials.json` in project root
- Must be "Desktop app" type, not "Web application"

### "Invalid credentials file format"

- Your `credentials.json` is for "Web application"
- Re-download as "Desktop application" type
- See Step 2 above for correct setup

### SSL Errors (WRONG_VERSION_NUMBER, etc.)

- Fixed with automatic retry logic
- Threading lock prevents concurrent API access
- See `THREADING_FIX.md` for technical details

### Events Not Appearing

1. Check Calendar ID is correct
2. Verify Google Calendar API is enabled
3. Check WebUntis credentials
4. Run with `VERBOSE=true` to see details

### Unicode Errors on Windows

- Fixed with automatic fallback to ASCII
- See `WINDOWS_UNICODE_FIX.md` for details

### Name Replacements Not Working

- Check exact spelling (case-sensitive)
- Verify `constants.py` syntax
- See `NAME_REPLACEMENT_GUIDE.md` for help

---

## Project Structure

```txt
UntiSync/
├── main.py                          # Main sync script
├── api.py                           # WebUntis API wrapper
├── calendarHandler.py               # Google Calendar API wrapper
├── constants.py                     # Configuration & name replacements
├── clear_calendars.py               # Helper: Clear all events
├── credentials.json                 # Google OAuth credentials (you create)
├── token.pickle                     # Google auth token (auto-generated)
├── .env                             # Your configuration (you create)
├── requirements.txt                 # Python dependencies
│
├── README.md                        # This file
├── DUAL_CALENDAR_GUIDE.md          # Dual-calendar setup guide
├── OPTIMIZATION_GUIDE.md           # Performance optimization guide
├── NAME_REPLACEMENT_GUIDE.md       # Subject name replacement guide
├── THREADING_FIX.md                # Threading SSL fix documentation
├── WINDOWS_UNICODE_FIX.md          # Windows console Unicode fix
├── CLEAR_CALENDARS_GUIDE.md        # Calendar clearing utility guide
└── PACKAGES.md                     # Package reference
```

---

## Documentation

- 📘 **README.md** (this file) - Setup and configuration guide
- 📗 **DUAL_CALENDAR_GUIDE.md** - Separate calendars for busy/free events
- 📙 **OPTIMIZATION_GUIDE.md** - Performance tuning and processing methods
- 📕 **NAME_REPLACEMENT_GUIDE.md** - Customize subject names with examples
- 📔 **CLEAR_CALENDARS_GUIDE.md** - Using the calendar clearing utility
- 🔧 **THREADING_FIX.md** - Technical details on SSL threading fix
- 🪟 **WINDOWS_UNICODE_FIX.md** - Windows console encoding fix
- 📦 **PACKAGES.md** - Python package reference

---

## Requirements

- **Python**: 3.9+ (tested with 3.13)
- **Operating System**: Windows, Linux, macOS
- **Internet**: Required for API access
- **Google Account**: For Google Calendar
- **WebUntis Account**: For school schedule access

---

## Installation Checklist

- [ ] Python 3.9+ installed
- [ ] Install packages: `pip install -r requirements.txt`
- [ ] Google Cloud project created
- [ ] Google Calendar API enabled
- [ ] OAuth credentials downloaded as `credentials.json` (Desktop app)
- [ ] `.env` file created with all required variables
- [ ] Calendar ID(s) obtained from Google Calendar
- [ ] Subject name replacements configured (optional)
- [ ] First sync completed: `python main.py`

---

## Advanced Usage

### Custom Processing Logic

Modify `apply_name_replacement()` in `main.py` for advanced name transformations:

```python
def apply_name_replacement(subject_name: str) -> str:
  # Check dictionary first
  if subject_name in NAME_REPLACEMENTS:
    return NAME_REPLACEMENTS[subject_name]
  
  # Add custom logic
  if subject_name.startswith('L12'):
    return f"LK: {subject_name[3:]}"
  
  return subject_name
```

### Increase Retry Attempts

Edit `calendarHandler.py` line 91 to increase SSL error retries:

```python
def _execute_with_retry(self, request, max_retries: int = 5, initial_delay: float = 1.0):
```

### Time Range Configuration

Edit `constants.py` to change sync time range:

```python
BACKWARD_TIME = 3*DAY   # Sync 3 days in the past
FORWARD_TIME = WEEK     # Sync 1 week in the future
```

---

## Contributing

Found a bug or want to contribute?

- Repository: [https://github.com/yoshi-qq/UntiSync](https://github.com/yoshi-qq/UntiSync)
- Issues: Report bugs or request features

---

## License

This project is provided as-is for personal and educational use.

---

## Support

For issues and questions:

1. Check the relevant documentation files
2. Verify your `.env` configuration
3. Run with `VERBOSE=true` for detailed output
4. Check `credentials.json` is "Desktop app" type
5. Ensure Google Calendar API is enabled

---

## Version History

- **Current**: Full-featured sync with dual-calendar, threading, name replacements
- **Features**: Threaded processing, SSL retry logic, Unicode support, dual calendars
- **Platform**: Cross-platform (Windows, Linux, macOS)

---

## Credits

- **WebUntis API**: Python webuntis package
- **Google Calendar API**: Google API Python Client
- **Author**: yoshi-qq

---

**Ready to sync?** → `python main.py` 🚀
