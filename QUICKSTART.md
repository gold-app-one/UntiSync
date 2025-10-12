# UntiSync - Quick Setup Guide

## 🚀 Get Started in 5 Steps

### Step 1: Install Python Packages ⚙️

```bash
pip install -r requirements.txt
```

### Step 2: Get Google Calendar Credentials 🔐

1. **Enable Google Calendar API:**

   - Go to <https://console.cloud.google.com/>
   - Create/select a project
   - Enable "Google Calendar API"

2. **Create OAuth Credentials:**
   - Go to "APIs & Services" > "Credentials"
   - Click "+ CREATE CREDENTIALS" > "OAuth client ID"
   - Choose "Desktop app"
   - Download JSON file
   - Save as `credentials.json` in project folder

   ⚠️ **Must be "Desktop app", NOT "Web application"!**

### Step 3: Find Your Calendar ID 📅

1. Open <https://calendar.google.com>
2. Click ⚙️ Settings
3. Click on your calendar name (left sidebar)
4. Scroll to "Integrate calendar"
5. Copy the **Calendar ID** (looks like: `abc123@group.calendar.google.com`)

**For Dual-Calendar Mode (Optional):**

- Create a second calendar for free events
- Get its Calendar ID too

### Step 4: Configure .env File 📝

1. **Copy the example:**

   ```bash
   copy .env.example .env
   ```

   (Linux/Mac: `cp .env.example .env`)

2. **Edit `.env` and fill in:**

   ```env
   # WebUntis Credentials
   SURNAME=YourLastName
   FORENAME=YourFirstName
   UNTIS_USERNAME=your_username
   UNTIS_PASSWORD=your_password
   UNTIS_SCHOOL=your_school_name

   # Google Calendar
   CALENDAR_ID=your_calendar_id@group.calendar.google.com

   # Optional: Dual calendars
   FREE_CALENDAR_ID=your_free_calendar_id@group.calendar.google.com

   # Optional: Location
   SCHOOL_LOCATION=Your School Name
   ```

### Step 5: Run First Sync 🎉

```bash
python main.py
```

**First run:** Browser opens for Google authorization → Sign in → Grant permissions

**Done!** Check your Google Calendar!

---

## File Checklist

Before running, make sure you have:

- [x] `credentials.json` - Downloaded from Google Cloud Console
- [x] `.env` - Created from `.env.example` with your credentials
- [x] `requirements.txt` - Already included
- [x] All Python packages installed

---

## Quick Reference

### Required Files

| File | How to Get | Location |
|------|-----------|----------|
| `credentials.json` | Download from Google Cloud Console | Project root |
| `.env` | Copy `.env.example` and fill in | Project root |

### Required Environment Variables

```env
SURNAME=...              # Your last name
FORENAME=...             # Your first name
UNTIS_USERNAME=...       # WebUntis username
UNTIS_PASSWORD=...       # WebUntis password
UNTIS_SCHOOL=...         # School identifier
CALENDAR_ID=...          # Google Calendar ID
```

### Optional Environment Variables

```env
FREE_CALENDAR_ID=...     # Separate calendar for cancelled events
SCHOOL_LOCATION=...      # Location added to events
PROCESSING_METHOD=auto   # auto, threaded, batch, individual
VERBOSE=true             # Show detailed logs
```

---

## Common Issues

### ❌ "credentials.json not found"

→ Download OAuth credentials from Google Cloud Console  
→ Save as `credentials.json` in project root

### ❌ "CALENDAR_ID not set"

→ Create `.env` file from `.env.example`  
→ Add your Calendar ID

### ❌ "Invalid credentials file format"

→ Credentials must be "Desktop app", not "Web application"  
→ Re-download with correct type

### ❌ "ModuleNotFoundError"

→ Run: `pip install -r requirements.txt`

---

## Next Steps

After successful first sync:

1. **Customize subject names** → Edit `constants.py`
2. **Set up dual calendars** → Add `FREE_CALENDAR_ID` to `.env`
3. **Adjust sync range** → Edit `BACKWARD_TIME` and `FORWARD_TIME` in `constants.py`
4. **Schedule automatic syncs** → Set up cron job or Task Scheduler

---

## Full Documentation

📘 **README.md** - Complete setup and configuration guide  
📗 **DUAL_CALENDAR_GUIDE.md** - Dual-calendar setup  
📙 **NAME_REPLACEMENT_GUIDE.md** - Customize subject names  
📕 **CLEAR_CALENDARS_GUIDE.md** - Clear calendar utility  

---

**Need help?** Check README.md for detailed troubleshooting!
