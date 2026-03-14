#!/usr/bin/env python3

import json
import os
import sys
import time
import signal
import subprocess
import argparse
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Set

# Try to import watchdog, fall back to polling if not available
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler

    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    print("Warning: watchdog not installed. Using polling mode (slower).")
    print("Install with: pip install watchdog")

# Configuration
CONFIG_PATH = Path.home() / ".config" / "opencode" / "opencode.json"
LOG_FILE = Path.home() / ".config" / "opencode" / "mcp-watch.log"
PID_FILE = Path.home() / ".config" / "opencode" / "mcp-watch.pid"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


class MCPManager:
    """Manages MCP server processes."""

    def __init__(self):
        self.config_path = CONFIG_PATH
        self.mcp_configs: Dict[str, dict] = {}
        self.mcp_processes: Dict[str, subprocess.Popen] = {}
        self.load_config()

    def load_config(self) -> bool:
        """Load MCP configuration from opencode.json."""
        try:
            with open(self.config_path, "r") as f:
                config = json.load(f)
                self.mcp_configs = config.get("mcp", {})
                logger.info(f"Loaded {len(self.mcp_configs)} MCP server configs")
                return True
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return False

    def get_mcp_command(self, name: str) -> Optional[List[str]]:
        """Get the command to launch an MCP server."""
        mcp_config = self.mcp_configs.get(name)
        if not mcp_config:
            return None

        cmd = mcp_config.get("command", [])
        if not cmd:
            return None

        # Handle different command formats
        if isinstance(cmd, list):
            return cmd
        elif isinstance(cmd, str):
            return cmd.split()
        return None

    def get_mcp_env(self, name: str) -> Dict[str, str]:
        """Get environment variables for an MCP server."""
        mcp_config = self.mcp_configs.get(name, {})
        env = os.environ.copy()
        env.update(mcp_config.get("environment", {}))
        return env

    def find_mcp_process(self, name: str) -> Optional[int]:
        """Find PID of running MCP server by name."""
        try:
            # Search for processes matching the MCP command
            cmd = self.get_mcp_command(name)
            if not cmd:
                return None

            # Look for processes containing the command signature
            cmd_str = " ".join(cmd[:3])  # First 3 parts of command
            result = subprocess.run(
                ["pgrep", "-f", cmd_str], capture_output=True, text=True
            )

            if result.returncode == 0:
                pids = result.stdout.strip().split("\n")
                # Filter out the grep process itself and this script
                for pid_str in pids:
                    try:
                        pid = int(pid_str)
                        # Check if it's not our own process
                        if pid != os.getpid():
                            return pid
                    except ValueError:
                        continue
            return None
        except Exception as e:
            logger.debug(f"Error finding process for {name}: {e}")
            return None

    def start_mcp(self, name: str) -> bool:
        """Start an MCP server."""
        cmd = self.get_mcp_command(name)
        if not cmd:
            logger.error(f"No command found for MCP: {name}")
            return False

        env = self.get_mcp_env(name)

        try:
            # Start the process
            process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,  # Create new process group
            )

            self.mcp_processes[name] = process
            logger.info(f"Started MCP: {name} (PID: {process.pid})")
            return True

        except Exception as e:
            logger.error(f"Failed to start MCP {name}: {e}")
            return False

    def stop_mcp(self, name: str) -> bool:
        """Stop an MCP server."""
        # Try to find and kill the process
        pid = self.find_mcp_process(name)

        if pid:
            try:
                os.kill(pid, signal.SIGTERM)
                logger.info(f"Sent SIGTERM to MCP: {name} (PID: {pid})")

                # Wait a bit for graceful shutdown
                time.sleep(1)

                # Check if still running, force kill if needed
                try:
                    os.kill(pid, 0)  # Check if process exists
                    os.kill(pid, signal.SIGKILL)
                    logger.info(f"Force killed MCP: {name} (PID: {pid})")
                except ProcessLookupError:
                    pass  # Process already terminated

                return True
            except Exception as e:
                logger.error(f"Error stopping MCP {name}: {e}")
                return False
        else:
            logger.warning(f"No running process found for MCP: {name}")
            return False

    def restart_mcp(self, name: str) -> bool:
        """Restart a single MCP server."""
        logger.info(f"Restarting MCP: {name}")
        self.stop_mcp(name)
        time.sleep(0.5)  # Brief pause between stop and start
        return self.start_mcp(name)

    def get_running_mcps(self) -> List[str]:
        """Get list of currently running MCP servers."""
        running = []
        for name in self.mcp_configs.keys():
            if self.find_mcp_process(name):
                running.append(name)
        return running

    def restart_all(self):
        """Restart all MCP servers."""
        logger.info("Restarting all MCP servers...")
        for name in self.mcp_configs.keys():
            self.restart_mcp(name)
            time.sleep(0.5)  # Stagger restarts

    def stop_all(self):
        """Stop all MCP servers."""
        logger.info("Stopping all MCP servers...")
        for name in self.mcp_configs.keys():
            self.stop_mcp(name)


class ConfigWatcher(FileSystemEventHandler if WATCHDOG_AVAILABLE else object):
    """Watches opencode.json for changes and reloads affected MCPs."""

    def __init__(self, mcp_manager: MCPManager):
        self.mcp_manager = mcp_manager
        self.last_config: Dict = {}
        self.last_check_time = 0
        self.debounce_seconds = 2  # Debounce rapid changes
        self.load_current_config()

    def load_current_config(self):
        """Load current config state for comparison."""
        try:
            with open(CONFIG_PATH, "r") as f:
                self.last_config = json.load(f).get("mcp", {})
        except Exception as e:
            logger.error(f"Error loading initial config: {e}")
            self.last_config = {}

    def on_modified(self, event):
        """Handle file modification event."""
        if event.src_path == str(CONFIG_PATH):
            current_time = time.time()
            if current_time - self.last_check_time < self.debounce_seconds:
                return  # Debounce

            self.last_check_time = current_time
            logger.info(f"Detected change in {CONFIG_PATH}")

            # Reload config
            if not self.mcp_manager.load_config():
                return

            # Compare and restart changed MCPs
            self.handle_config_change()

    def handle_config_change(self):
        """Compare old and new config, restart changed MCPs."""
        try:
            with open(CONFIG_PATH, "r") as f:
                new_config = json.load(f).get("mcp", {})
        except Exception as e:
            logger.error(f"Error reading new config: {e}")
            return

        # Find changed or new MCPs
        changed_mcps = []

        for name, new_mcp_config in new_config.items():
            old_mcp_config = self.last_config.get(name)

            if old_mcp_config != new_mcp_config:
                changed_mcps.append(name)
                logger.info(f"MCP config changed: {name}")

        # Find removed MCPs
        removed_mcps = set(self.last_config.keys()) - set(new_config.keys())
        for name in removed_mcps:
            logger.info(f"MCP removed: {name}")
            self.mcp_manager.stop_mcp(name)

        # Restart changed MCPs
        for name in changed_mcps:
            self.mcp_manager.restart_mcp(name)

        # Update last config
        self.last_config = new_config

    def poll_mode(self):
        """Fallback polling mode when watchdog is not available."""
        logger.info("Starting polling mode (checking every 2 seconds)...")
        last_mtime = 0

        try:
            while True:
                try:
                    current_mtime = os.path.getmtime(CONFIG_PATH)
                    if current_mtime != last_mtime:
                        if last_mtime != 0:  # Skip first check
                            logger.info(f"Detected change in {CONFIG_PATH}")
                            if self.mcp_manager.load_config():
                                self.handle_config_change()
                        last_mtime = current_mtime
                except Exception as e:
                    logger.error(f"Error in poll mode: {e}")

                time.sleep(2)
        except KeyboardInterrupt:
            logger.info("Stopping watcher...")


def write_pid_file():
    """Write PID file to prevent multiple instances."""
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))


def remove_pid_file():
    """Remove PID file on exit."""
    try:
        if PID_FILE.exists():
            PID_FILE.unlink()
    except:
        pass


def main():
    parser = argparse.ArgumentParser(
        description="Watch opencode.json and auto-reload MCP servers"
    )
    parser.add_argument(
        "--status", action="store_true", help="Check status of running MCP servers"
    )
    parser.add_argument(
        "--restart-all", action="store_true", help="Restart all MCP servers"
    )
    parser.add_argument(
        "--restart", metavar="MCP_NAME", help="Restart a specific MCP server"
    )
    parser.add_argument("--kill", action="store_true", help="Stop all MCP servers")
    parser.add_argument(
        "--daemon", action="store_true", help="Run as daemon in background"
    )

    args = parser.parse_args()

    # Initialize manager
    manager = MCPManager()

    # Handle one-off commands
    if args.status:
        running = manager.get_running_mcps()
        print(f"Running MCP servers ({len(running)}):")
        for name in running:
            pid = manager.find_mcp_process(name)
            print(f"  ✓ {name} (PID: {pid})")
        return

    if args.restart:
        manager.restart_mcp(args.restart)
        return

    if args.restart_all:
        manager.restart_all()
        return

    if args.kill:
        manager.stop_all()
        return

    # Start watcher
    logger.info("=" * 60)
    logger.info("OpenCode MCP Watcher Started")
    logger.info(f"Watching: {CONFIG_PATH}")
    logger.info(f"Log file: {LOG_FILE}")
    logger.info("=" * 60)

    write_pid_file()

    try:
        if WATCHDOG_AVAILABLE:
            # Use watchdog for efficient file watching
            event_handler = ConfigWatcher(manager)
            observer = Observer()
            observer.schedule(
                event_handler, path=str(CONFIG_PATH.parent), recursive=False
            )
            observer.start()

            logger.info("Using inotify/watchdog for efficient watching")

            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                observer.stop()
                logger.info("Watcher stopped by user")

            observer.join()
        else:
            # Fallback to polling mode
            watcher = ConfigWatcher(manager)
            watcher.poll_mode()

    finally:
        remove_pid_file()


if __name__ == "__main__":
    main()


def start_daemon():
    import os
    import subprocess
    
    if PID_FILE.exists():
        try:
            with open(PID_FILE, "r") as f:
                pid = int(f.read().strip())
            if os.path.exists(f"/proc/{pid}"):
                print(f"MCP Watcher is already running (PID: {pid})")
                sys.exit(1)
        except (ValueError, IOError):
            pass
        PID_FILE.unlink()
    
    subprocess.Popen(
        [sys.executable, "-m", "mcp_watch.watcher"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True
    )
    
    time.sleep(1)
    if PID_FILE.exists():
        with open(PID_FILE, "r") as f:
            pid = f.read().strip()
        print(f"MCP Watcher started (PID: {pid})")
        print(f"Log file: {LOG_FILE}")
    else:
        print("Failed to start MCP Watcher")
        sys.exit(1)


def stop_daemon():
    import os
    import signal
    
    if not PID_FILE.exists():
        print("MCP Watcher is not running")
        return
    
    try:
        with open(PID_FILE, "r") as f:
            pid = int(f.read().strip())
        
        try:
            os.kill(pid, signal.SIGTERM)
            print("MCP Watcher stopped")
        except ProcessLookupError:
            print("MCP Watcher was not running")
        
        PID_FILE.unlink()
    except (ValueError, IOError) as e:
        print(f"Error stopping MCP Watcher: {e}")
        sys.exit(1)
