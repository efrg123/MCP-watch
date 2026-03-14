# OpenCode MCP Auto-Reload Watcher

[![PyPI version](https://badge.fury.io/py/mcp-watch.svg)](https://badge.fury.io/py/mcp-watch)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![GitHub stars](https://img.shields.io/github/stars/efrg123/MCP-watch.svg?style=social)](https://github.com/efrg123/MCP-watch/stargazers)

> 🚀 **Never restart OpenCode again!** Auto-reload MCP servers when config changes.

Tired of exiting and restarting OpenCode every time you modify an MCP server? **MCP Watch** monitors your `opencode.json` and automatically restarts only the changed MCP servers - in seconds, not minutes.

![Demo](https://raw.githubusercontent.com/efrg123/MCP-watch/main/assets/demo.gif)

## ✨ Features

- ⚡ **Instant Reload** - Changes apply in ~1 second, not 30+ seconds
- 🎯 **Smart Detection** - Only restarts MCPs that actually changed
- 🔍 **File Watching** - Uses efficient inotify/watchdog (no polling)
- 📊 **Process Management** - Graceful shutdown with fallback to force kill
- 📝 **Detailed Logging** - See exactly what changed and when
- 🎛️ **CLI Commands** - Status, manual restart, stop all, etc.
- 🐧 **Cross-Platform** - Linux, macOS, Windows support
- 🔧 **Zero Config** - Works out of the box with your existing setup

## 🚀 Quick Start

### Installation

```bash
# Via pip (recommended)
pip install mcp-watch

# Or install from source
git clone https://github.com/efrg123/MCP-watch.git
cd MCP-watch
pip install -e .
```

### Start Watching

```bash
# Start the watcher (runs in background)
mcp-watch-start

# That's it! Now edit ~/.config/opencode/opencode.json
# and watch your changes apply automatically
```

### Stop Watching

```bash
mcp-watch-stop
```

## 📖 Usage

### Automatic Mode (Recommended)

1. Start the watcher:
   ```bash
   mcp-watch-start
   ```

2. Edit your OpenCode config:
   ```bash
   vim ~/.config/opencode/opencode.json
   ```

3. Save the file → MCP servers restart automatically!

### CLI Commands

```bash
# Check status of all MCP servers
mcp-watch --status

# Restart a specific MCP server
mcp-watch --restart pandas-mcp-server

# Restart all MCP servers
mcp-watch --restart-all

# Stop all MCP servers
mcp-watch --kill

# Show help
mcp-watch --help
```

### Systemd Service (Linux)

Enable automatic startup on boot:

```bash
# Enable the service
systemctl --user enable mcp-watch.service

# Start the service
systemctl --user start mcp-watch.service

# Check status
systemctl --user status mcp-watch.service

# View logs
journalctl --user -u mcp-watch.service -f
```

## 🎯 Why MCP Watch?

| Without MCP Watch | With MCP Watch |
|------------------|----------------|
| Edit config | Edit config |
| Exit OpenCode | Save file |
| Wait for shutdown | ✅ Done in 1 second |
| Restart OpenCode | |
| Wait 30+ seconds | |
| Reconnect to session | |

**Time saved: 30+ seconds per config change**

## 🔧 How It Works

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│  opencode.json  │────▶│  MCP Watch   │────▶│  Restart MCPs   │
│   (watched)     │     │  (detector)  │     │  (only changed) │
└─────────────────┘     └──────────────┘     └─────────────────┘
         │                                               │
         │                                               │
         ▼                                               ▼
   You edit config                             MCP servers restart
   and save file                               (others keep running)
```

### Technical Details

1. **File Watching**: Uses `watchdog` library with inotify on Linux for efficient file system monitoring
2. **Change Detection**: SHA256 hash comparison to detect actual changes, not just file timestamps
3. **Process Management**: 
   - Sends SIGTERM for graceful shutdown
   - Waits 1 second
   - Sends SIGKILL if still running
4. **Debouncing**: 2-second debounce to handle rapid successive saves

## 📊 Log Output

```
2026-03-14 20:07:20,988 - INFO - OpenCode MCP Watcher Started
2026-03-14 20:07:20,988 - INFO - Watching: /home/fahd/.config/opencode/opencode.json
2026-03-14 20:07:52,372 - INFO - Detected change in opencode.json
2026-03-14 20:07:52,372 - INFO - MCP config changed: memory
2026-03-14 20:07:52,373 - INFO - Restarting MCP: memory
2026-03-14 20:07:52,388 - INFO - Sent SIGTERM to MCP: memory (PID: 52771)
2026-03-14 20:07:53,889 - INFO - Started MCP: memory (PID: 88820)
```

View logs:
```bash
tail -f ~/.config/opencode/mcp-watch.log
```

## 🛠️ Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MCP_WATCH_CONFIG` | Path to opencode.json | `~/.config/opencode/opencode.json` |
| `MCP_WATCH_LOG` | Path to log file | `~/.config/opencode/mcp-watch.log` |
| `MCP_WATCH_PID` | Path to PID file | `~/.config/opencode/mcp-watch.pid` |
| `MCP_WATCH_DEBOUNCE` | Debounce time in seconds | `2` |

### Example

```bash
export MCP_WATCH_CONFIG=/custom/path/opencode.json
export MCP_WATCH_DEBOUNCE=5
mcp-watch-start
```

## 🐛 Troubleshooting

### MCP servers not restarting

1. Check if watcher is running:
   ```bash
   pgrep -f mcp-watch
   ```

2. Check logs for errors:
   ```bash
   cat ~/.config/opencode/mcp-watch.log
   ```

3. Verify MCP config is valid:
   ```bash
   python3 -c "import json; json.load(open('/home/user/.config/opencode/opencode.json'))"
   ```

### Permission denied

Make sure the script has access to:
- Read `~/.config/opencode/opencode.json`
- Execute MCP server commands
- Use `pgrep` and `kill`

### Windows support

On Windows, the watcher uses polling mode (less efficient but works). For best performance, use WSL2.

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Setup

```bash
git clone https://github.com/efrg123/MCP-watch.git
cd MCP-watch
python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
pytest
```

## 📋 Roadmap

- [ ] Web dashboard for MCP status
- [ ] Health check before marking restart successful
- [ ] Dry-run mode
- [ ] Windows service support
- [ ] Docker container support
- [ ] Integration with Claude Code (when API available)

## 📝 License

MIT License - see [LICENSE](LICENSE) file

## 🙏 Acknowledgments

- Inspired by the frustration of restarting OpenCode 50 times a day
- Thanks to the OpenCode community for feature requests ([#6719](https://github.com/anomalyco/opencode/issues/6719))
- Built with [watchdog](https://github.com/gorakhargosh/watchdog) for efficient file watching

## ⭐ Star History

[![Star History Chart](https://api.star-history.com/svg?repos=efrg123/MCP-watch&type=Date)](https://star-history.com/#efrg123/MCP-watch&Date)

---

**Enjoying MCP Watch?** Give us a ⭐ on GitHub!

<a href="https://github.com/efrg123/MCP-watch">
  <img src="https://img.shields.io/github/stars/efrg123/MCP-watch?style=for-the-badge&logo=github&color=yellow" alt="GitHub stars">
</a>
