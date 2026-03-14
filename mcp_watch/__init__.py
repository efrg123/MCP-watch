"""
MCP Watch - OpenCode MCP Auto-Reload Watcher

Automatically watches opencode.json for changes and reloads MCP servers.
"""

__version__ = "0.1.0"
__author__ = "efrg123"
__license__ = "MIT"

from .watcher import MCPManager, ConfigWatcher

__all__ = ["MCPManager", "ConfigWatcher"]
