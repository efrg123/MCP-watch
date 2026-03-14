#!/usr/bin/env python3
import sys
from mcp_watch.watcher import main, start_daemon, stop_daemon


def cli_main():
    main()


def cli_start():
    start_daemon()


def cli_stop():
    stop_daemon()


if __name__ == "__main__":
    main()
