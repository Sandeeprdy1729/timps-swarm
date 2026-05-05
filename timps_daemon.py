#!/usr/bin/env python3
"""
timps_daemon.py — TIMPS Context Keeper daemon

Runs the context keeper in the background, refreshing working memory every 5 minutes.
Called by the `timps daemon` CLI shim.

Usage:
  python3 timps_daemon.py [--interval 300]
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TIMPS Context Keeper daemon")
    parser.add_argument("--interval", type=int, default=300, help="Refresh interval in seconds (default: 300)")
    args = parser.parse_args()

    from src.context_keeper import run_daemon
    print(f"[timps-daemon] Starting context keeper daemon (interval={args.interval}s)")
    print("[timps-daemon] Press Ctrl+C to stop")
    try:
        run_daemon(interval_seconds=args.interval)
    except KeyboardInterrupt:
        print("\n[timps-daemon] Stopped.")
        sys.exit(0)
