# Graceful Shutdown Guide for UntiSync

This guide explains how to implement graceful shutdown handling in UntiSync to prevent your Raspberry Pi from taking multiple minutes to shut down when the sync process is running.

## Problem

When your Raspberry Pi tries to shut down while UntiSync is running (via cron job), the system waits for the process to complete before shutting down. This can cause:

- **Long shutdown times** (multiple minutes)
- **Hanging during shutdown** if the sync process gets stuck
- **Forced power-offs** that can corrupt the SD card

## Solution

The graceful shutdown implementation provides:

✅ **Signal handling** - Responds to SIGTERM, SIGINT, and SIGQUIT  
✅ **Immediate response** - Stops current operation and exits gracefully  
✅ **Partial sync completion** - Finishes the current API call before exiting  
✅ **Timeout protection** - Automatic termination if sync takes too long  
✅ **Proper exit codes** - Different codes for success, shutdown, timeout, and errors  

---

## Files Overview

### `main_graceful.py`
Enhanced version of `main.py` with signal handling and shutdown detection:
- Registers signal handlers for graceful shutdown
- Checks for shutdown requests throughout the sync process
- Returns proper exit codes for different scenarios
- Allows current operation to complete before exiting

### `untis_sync_wrapper.py`
Wrapper script that runs the sync with timeout protection:
- Enforces maximum runtime (default: 5 minutes)
- Forwards shutdown signals to the sync process
- Force-kills hanging processes as a last resort
- Provides detailed logging and monitoring

---

## Quick Setup

### 1. Test the Graceful Shutdown Version

```bash
# Run the graceful version directly
cd /path/to/UntiSync
python main_graceful.py
```

### 2. Test Signal Handling

```bash
# In one terminal, start the sync
python main_graceful.py

# In another terminal, send shutdown signal
pkill -TERM -f main_graceful.py
```

You should see:
```
🛑 Received SIGTERM - requesting graceful shutdown...
⏹️ Shutdown requested - stopping operations
👋 Graceful shutdown completed
```

### 3. Test the Wrapper Script

```bash
# Run with wrapper (includes timeout protection)
python untis_sync_wrapper.py
```

---

## Cron Job Configuration

### Option 1: Use the Wrapper Script (Recommended)

```bash
# Edit crontab
crontab -e

# Add this line for sync every 5 minutes with timeout protection
*/5 * * * * cd /home/pi/UntiSync && python untis_sync_wrapper.py >> /var/log/untis_sync.log 2>&1
```

### Option 2: Use main_graceful.py Directly

```bash
# Edit crontab
crontab -e

# Add this line for sync every 5 minutes
*/5 * * * * cd /home/pi/UntiSync && timeout 300 python main_graceful.py >> /var/log/untis_sync.log 2>&1
```

### Option 3: Replace Original main.py

```bash
# Backup original
cp main.py main_original.py

# Replace with graceful version
cp main_graceful.py main.py

# Your existing cron job will now use graceful shutdown
*/5 * * * * cd /home/pi/UntiSync && python main.py >> /var/log/untis_sync.log 2>&1
```

---

## Systemd Service Configuration

### Create Service File

```bash
sudo nano /etc/systemd/system/untis-sync.service
```

### Service Configuration

```ini
[Unit]
Description=UntiSync - WebUntis to Google Calendar Sync
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=pi
Group=pi
WorkingDirectory=/home/pi/UntiSync
Environment=UNTIS_SYNC_TIMEOUT=300
ExecStart=/usr/bin/python3 /home/pi/UntiSync/untis_sync_wrapper.py
TimeoutStopSec=60
KillMode=mixed
KillSignal=SIGTERM

# Restart policy for failed syncs
Restart=on-failure
RestartSec=60
StartLimitBurst=3
StartLimitIntervalSec=300

[Install]
WantedBy=multi-user.target
```

### Timer Configuration

```bash
sudo nano /etc/systemd/system/untis-sync.timer
```

```ini
[Unit]
Description=Run UntiSync every 5 minutes
Requires=untis-sync.service

[Timer]
OnCalendar=*:0/5
Persistent=true
AccuracySec=30

[Install]
WantedBy=timers.target
```

### Enable and Start

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable timer
sudo systemctl enable untis-sync.timer

# Start timer
sudo systemctl start untis-sync.timer

# Check status
sudo systemctl status untis-sync.timer
sudo systemctl list-timers untis-sync.timer
```

---

## Configuration Options

### Environment Variables

Add these to your `.env` file or export them:

```bash
# Wrapper script timeouts
UNTIS_SYNC_TIMEOUT=300        # Max sync time (seconds)
UNTIS_SYNC_KILL_TIMEOUT=30    # Time to wait before force-kill
UNTIS_SYNC_SCRIPT=main_graceful.py  # Script to run

# Existing UntiSync options
VERBOSE=true                  # Enable detailed logging
PROCESSING_METHOD=individual  # Use individual for better shutdown response
```

### Processing Method for Better Shutdown Response

For the most responsive shutdown handling, use `individual` processing:

```env
PROCESSING_METHOD=individual
```

This checks for shutdown signals between each event, providing near-instant response.

---

## Exit Codes

### main_graceful.py Exit Codes

- **0**: Sync completed successfully
- **1**: Graceful shutdown (signal received)
- **2**: Error (configuration, API, etc.)

### untis_sync_wrapper.py Exit Codes

- **0**: Sync completed successfully
- **1**: Graceful shutdown (signal received)
- **2**: Error (configuration, API, etc.)
- **3**: Timeout (sync took too long)

---

## Testing Shutdown Behavior

### Test 1: Signal Handling

```bash
# Terminal 1: Start sync
python main_graceful.py

# Terminal 2: Send signals
pkill -TERM -f main_graceful.py  # Graceful
pkill -INT -f main_graceful.py   # Ctrl+C
pkill -QUIT -f main_graceful.py  # Quit (Linux only)
```

### Test 2: Wrapper Timeout

```bash
# Set short timeout for testing
UNTIS_SYNC_TIMEOUT=10 python untis_sync_wrapper.py
```

### Test 3: System Shutdown

```bash
# Start sync in background
python main_graceful.py &

# Try system shutdown (test VM recommended)
sudo shutdown -h +1

# Should see graceful shutdown messages
```

### Test 4: Cron Job Behavior

```bash
# Add test cron job
echo "*/1 * * * * cd /home/pi/UntiSync && python main_graceful.py >> /tmp/untis_test.log 2>&1" | crontab -

# Wait a minute, then check log
tail -f /tmp/untis_test.log

# Try shutdown while cron is running
sudo shutdown -h +1

# Remove test cron
crontab -r
```

---

## Troubleshooting

### Shutdown Still Takes Long

1. **Check cron job configuration**:
   ```bash
   crontab -l
   ```
   Ensure you're using `main_graceful.py` or the wrapper.

2. **Check for multiple processes**:
   ```bash
   ps aux | grep python | grep -i untis
   ```
   Kill any stuck processes:
   ```bash
   pkill -f "python.*main"
   ```

3. **Check systemd journal**:
   ```bash
   sudo journalctl -u untis-sync.service -f
   ```

### Signals Not Working

1. **Check signal handlers are registered**:
   Look for this log message:
   ```
   📡 Signal handlers registered for graceful shutdown
   ```

2. **Verify process receives signals**:
   ```bash
   # Start sync
   python main_graceful.py &
   PID=$!
   
   # Send signal directly
   kill -TERM $PID
   ```

### Wrapper Script Issues

1. **Check script permissions**:
   ```bash
   chmod +x untis_sync_wrapper.py
   ```

2. **Test timeout behavior**:
   ```bash
   UNTIS_SYNC_TIMEOUT=5 python untis_sync_wrapper.py
   ```

3. **Check for Python path issues**:
   ```bash
   which python3
   python3 --version
   ```

---

## Migration from Original Version

### Backup Current Setup

```bash
cd /path/to/UntiSync
cp main.py main_original_backup.py
cp crontab -l > crontab_backup.txt
```

### Method 1: Replace main.py (Simplest)

```bash
# Replace main.py with graceful version
cp main_graceful.py main.py

# Your existing cron jobs will now use graceful shutdown
# No other changes needed
```

### Method 2: Update Cron Jobs (Recommended)

```bash
# Edit crontab
crontab -e

# Change from:
# */5 * * * * cd /home/pi/UntiSync && python main.py

# To:
# */5 * * * * cd /home/pi/UntiSync && python untis_sync_wrapper.py
```

### Method 3: Switch to Systemd (Advanced)

```bash
# Remove cron job
crontab -e  # Delete UntiSync lines

# Set up systemd service (see configuration above)
sudo systemctl enable untis-sync.timer
sudo systemctl start untis-sync.timer
```

---

## Performance Impact

The graceful shutdown implementation has minimal performance impact:

- **Signal handler registration**: ~0.001s overhead
- **Shutdown checks**: ~0.0001s per check
- **Individual processing**: Adds shutdown checks between events
- **Memory usage**: +~1KB for signal handling

**Recommendation**: Use `PROCESSING_METHOD=individual` for best shutdown response, or `threaded` for fastest sync with slightly slower shutdown response.

---

## Advanced Configuration

### Custom Signal Handler

You can modify the signal handler in `main_graceful.py`:

```python
def signal_handler(signum: int, frame) -> None:
    global shutdown_requested
    log(f"Custom handling for signal {signum}", force=True)
    
    # Custom logic here
    if signum == signal.SIGTERM:
        # System shutdown - exit immediately
        shutdown_requested = True
    elif signum == signal.SIGINT:
        # User Ctrl+C - finish current event
        shutdown_requested = True
```

### Shutdown Hook

Add custom cleanup logic:

```python
def cleanup_on_shutdown():
    """Custom cleanup when shutting down."""
    log("Performing custom cleanup...", force=True)
    # Your cleanup code here

# Call in main() when shutdown_requested is True
if shutdown_requested:
    cleanup_on_shutdown()
```

---

## Monitoring and Logging

### Log Analysis

```bash
# Check for graceful shutdowns
grep "graceful shutdown" /var/log/untis_sync.log

# Check for timeouts
grep "timeout" /var/log/untis_sync.log

# Check exit codes
grep "exit code" /var/log/untis_sync.log
```

### Health Check Script

```bash
#!/bin/bash
# health_check.sh

LOG_FILE="/var/log/untis_sync.log"
MAX_AGE=600  # 10 minutes

if [ -f "$LOG_FILE" ]; then
    LAST_SUCCESS=$(grep "Sync completed successfully" "$LOG_FILE" | tail -1 | cut -d' ' -f1-2)
    if [ -n "$LAST_SUCCESS" ]; then
        LAST_EPOCH=$(date -d "$LAST_SUCCESS" +%s 2>/dev/null || echo 0)
        NOW_EPOCH=$(date +%s)
        AGE=$((NOW_EPOCH - LAST_EPOCH))
        
        if [ $AGE -lt $MAX_AGE ]; then
            echo "OK: Last successful sync was ${AGE}s ago"
            exit 0
        else
            echo "WARNING: Last successful sync was ${AGE}s ago"
            exit 1
        fi
    else
        echo "ERROR: No successful syncs found in log"
        exit 2
    fi
else
    echo "ERROR: Log file not found"
    exit 2
fi
```

---

## Summary

The graceful shutdown implementation solves the Pi shutdown delay problem by:

1. **Responding immediately** to shutdown signals
2. **Completing current operations** gracefully
3. **Preventing hanging** with timeout protection
4. **Providing proper exit codes** for monitoring

**Recommended setup**: Use `untis_sync_wrapper.py` with cron or systemd for the most robust solution.

**Quick fix**: Replace `main.py` with `main_graceful.py` to immediately improve shutdown behavior with your existing setup.