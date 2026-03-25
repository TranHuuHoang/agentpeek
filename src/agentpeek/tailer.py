"""Async file tailer for /tmp/agentpeek.jsonl with truncation + rotation handling."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Callable

EVENTS_FILE = "/tmp/agentpeek.jsonl"


async def tail_jsonl(
    callback: Callable[[dict], None],
    file_path: str = EVENTS_FILE,
    poll_interval: float = 0.1,
) -> None:
    """Tail a JSONL file, calling callback for each parsed line.

    Handles:
    - File not existing yet (waits for creation)
    - Truncation (size < last position → seek to 0)
    - File replacement (inode change → reopen)
    """
    path = Path(file_path)
    path.touch(exist_ok=True)

    f = open(path, "r")
    f.seek(0, 2)  # Start at end
    inode = os.stat(path).st_ino
    print(f"  Tailing {file_path} ...")

    try:
        while True:
            # Check for file replacement (new inode) or truncation
            try:
                stat = os.stat(path)
                if stat.st_ino != inode:
                    # File was replaced — reopen
                    f.close()
                    f = open(path, "r")
                    inode = stat.st_ino
                    print(f"  File replaced, reopened {file_path}")
                elif stat.st_size < f.tell():
                    # File was truncated — seek to start
                    f.seek(0)
                    print(f"  File truncated, rewound {file_path}")
            except FileNotFoundError:
                await asyncio.sleep(poll_interval)
                continue

            line = f.readline()
            if line:
                line = line.strip()
                if line:
                    try:
                        callback(json.loads(line))
                    except json.JSONDecodeError as e:
                        print(f"  \033[31mBAD JSON:\033[0m {line[:80]} — {e}")
            else:
                await asyncio.sleep(poll_interval)
    finally:
        f.close()
