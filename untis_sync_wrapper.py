#!/usr/bin/env python3
"""
UntiSync Wrapper Script with Timeout Handling

This wrapper script runs the UntiSync main process with a configurable timeout.
If the sync takes too long (e.g., during system shutdown), it will gracefully
terminate the process to prevent Pi shutdown delays.

Usage:
  python untis_sync_wrapper.py
  
Environment Variables:
  UNTIS_SYNC_TIMEOUT - Maximum sync time in seconds (default: 300 = 5 minutes)
  UNTIS_SYNC_KILL_TIMEOUT - Time to wait after SIGTERM before SIGKILL (default: 30 seconds)
  UNTIS_SYNC_SCRIPT - Path to the sync script (default: main_graceful.py)
"""

import os
import sys
import subprocess
import signal
import time
from typing import Optional

# Configuration from environment variables
SYNC_TIMEOUT = int(os.getenv('UNTIS_SYNC_TIMEOUT', '300'))  # 5 minutes default
KILL_TIMEOUT = int(os.getenv('UNTIS_SYNC_KILL_TIMEOUT', '30'))  # 30 seconds default
SYNC_SCRIPT = os.getenv('UNTIS_SYNC_SCRIPT', 'main_graceful.py')
VERBOSE = os.getenv('VERBOSE', 'true').lower() in ('true', '1', 'yes')

# Get script directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SYNC_SCRIPT_PATH = os.path.join(SCRIPT_DIR, SYNC_SCRIPT)

# Global variables
child_process: Optional[subprocess.Popen] = None
shutdown_requested = False


def log(message: str, force: bool = False) -> None:
    """Print a log message if verbose mode is enabled."""
    if VERBOSE or force:
        try:
            print(f"[WRAPPER] {message}")
        except UnicodeEncodeError:
            print(f"[WRAPPER] {message.encode('ascii', 'replace').decode('ascii')}")


def signal_handler(signum: int, frame) -> None:
    """Handle signals and forward them to child process."""
    global shutdown_requested, child_process
    
    signal_names = {signal.SIGTERM: 'SIGTERM', signal.SIGINT: 'SIGINT'}
    if hasattr(signal, 'SIGQUIT'):
        signal_names[signal.SIGQUIT] = 'SIGQUIT'
    
    signal_name = signal_names.get(signum, f'Signal {signum}')
    log(f"Received {signal_name} - forwarding to sync process...", force=True)
    
    shutdown_requested = True
    
    if child_process and child_process.poll() is None:
        try:
            log(f"Sending {signal_name} to sync process (PID: {child_process.pid})", force=True)
            child_process.send_signal(signum)
        except ProcessLookupError:
            log("Sync process already terminated", force=True)
        except Exception as e:
            log(f"Error forwarding signal: {e}", force=True)


def setup_signal_handlers() -> None:
    """Set up signal handlers to forward signals to child process."""
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    if hasattr(signal, 'SIGQUIT'):
        signal.signal(signal.SIGQUIT, signal_handler)
    
    log("Signal handlers registered for wrapper")


def terminate_process_gracefully(process: subprocess.Popen) -> bool:
    """Attempt to terminate the process gracefully.
    
    Returns:
        True if process terminated gracefully, False if force-killed
    """
    if process.poll() is not None:
        return True  # Already terminated
    
    log(f"Attempting graceful termination of sync process (PID: {process.pid})...", force=True)
    
    try:
        # Send SIGTERM for graceful shutdown
        process.terminate()
        
        # Wait for graceful shutdown
        try:
            process.wait(timeout=KILL_TIMEOUT)
            log("Sync process terminated gracefully", force=True)
            return True
        except subprocess.TimeoutExpired:
            # Process didn't respond to SIGTERM, force kill
            log(f"Sync process didn't respond to SIGTERM within {KILL_TIMEOUT}s, force killing...", force=True)
            process.kill()
            process.wait(timeout=5)  # Give it a few seconds to die
            log("Sync process force-killed", force=True)
            return False
            
    except ProcessLookupError:
        log("Sync process already terminated", force=True)
        return True
    except Exception as e:
        log(f"Error terminating sync process: {e}", force=True)
        return False


def run_sync_with_timeout() -> int:
    """Run the sync script with timeout protection.
    
    Returns:
        Exit code: 0 = success, 1 = graceful shutdown, 2 = error, 3 = timeout
    """
    global child_process
    
    if not os.path.exists(SYNC_SCRIPT_PATH):
        log(f"Sync script not found: {SYNC_SCRIPT_PATH}", force=True)
        return 2
    
    log(f"Starting sync process with {SYNC_TIMEOUT}s timeout...", force=True)
    log(f"Command: python {SYNC_SCRIPT_PATH}", force=False)
    
    start_time = time.time()
    
    try:
        # Start the sync process
        child_process = subprocess.Popen(
            [sys.executable, SYNC_SCRIPT_PATH],
            cwd=SCRIPT_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1  # Line buffered
        )
        
        log(f"Sync process started (PID: {child_process.pid})", force=True)
        
        # Monitor the process with timeout
        while True:
            # Check if process completed
            exit_code = child_process.poll()
            if exit_code is not None:
                elapsed = time.time() - start_time
                log(f"Sync process completed in {elapsed:.1f}s with exit code {exit_code}", force=True)
                
                # Read any remaining output
                if child_process.stdout:
                    remaining_output = child_process.stdout.read()
                    if remaining_output and VERBOSE:
                        print(remaining_output, end='')
                
                return exit_code
            
            # Check for timeout
            elapsed = time.time() - start_time
            if elapsed > SYNC_TIMEOUT:
                log(f"Sync process timed out after {elapsed:.1f}s (limit: {SYNC_TIMEOUT}s)", force=True)
                graceful = terminate_process_gracefully(child_process)
                if graceful:
                    log("Sync process terminated gracefully due to timeout", force=True)
                    return 3  # Timeout exit code
                else:
                    log("Sync process force-killed due to timeout", force=True)
                    return 3  # Timeout exit code
            
            # Check for shutdown signal
            if shutdown_requested:
                log("Shutdown requested - waiting for sync process to finish...", force=True)
                # Give the process some time to shutdown gracefully
                remaining_time = max(0, min(30, SYNC_TIMEOUT - elapsed))
                try:
                    exit_code = child_process.wait(timeout=remaining_time)
                    log(f"Sync process exited with code {exit_code} after shutdown signal", force=True)
                    return exit_code
                except subprocess.TimeoutExpired:
                    log("Sync process didn't respond to shutdown signal, terminating...", force=True)
                    terminate_process_gracefully(child_process)
                    return 1  # Graceful shutdown
            
            # Read and forward output
            if child_process.stdout:
                try:
                    line = child_process.stdout.readline()
                    if line and VERBOSE:
                        print(line, end='')
                except Exception:
                    pass  # Ignore output errors
            
            # Small sleep to prevent busy waiting
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        log("Received keyboard interrupt", force=True)
        if child_process:
            terminate_process_gracefully(child_process)
        return 1
    except Exception as e:
        log(f"Error running sync process: {e}", force=True)
        if child_process:
            terminate_process_gracefully(child_process)
        return 2
    finally:
        child_process = None


def main() -> int:
    """Main wrapper function."""
    setup_signal_handlers()
    
    log(f"UntiSync Wrapper starting (timeout: {SYNC_TIMEOUT}s, kill timeout: {KILL_TIMEOUT}s)", force=True)
    log(f"Sync script: {SYNC_SCRIPT_PATH}", force=False)
    
    exit_code = run_sync_with_timeout()
    
    # Map exit codes to descriptive messages
    exit_messages = {
        0: "Sync completed successfully",
        1: "Sync terminated gracefully", 
        2: "Sync failed with errors",
        3: "Sync timed out"
    }
    
    message = exit_messages.get(exit_code, f"Sync exited with code {exit_code}")
    log(message, force=True)
    
    return exit_code


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as e:
        print(f"[WRAPPER] Unexpected error: {e}", file=sys.stderr)
        sys.exit(2)