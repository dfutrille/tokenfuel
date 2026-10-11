#!/usr/bin/env python3
"""Collect Claude Code quota from stdin and optionally render a status line."""


import json
import os
import sys
import tempfile
import time

CACHE = os.path.expanduser("~/.cache/tokenwatch/claude.json")
WINDOWS = ("five_hour", "seven_day")

SAME_WINDOW_SECS = 120


def load_cache():
    try:
        with open(CACHE, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def save_cache(data):
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(CACHE), prefix=".claude-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        os.replace(tmp, CACHE)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def merge_window(old, new, now):


    if not isinstance(new, dict) or new.get("resets_at") is None:
        return old
    new = {
        "used_percentage": new.get("used_percentage") or 0,
        "resets_at": new["resets_at"],
        "seen_at": now,
    }
    if not isinstance(old, dict) or old.get("resets_at") is None:
        return new
    delta = new["resets_at"] - old["resets_at"]
    if delta > SAME_WINDOW_SECS:
        return new
    if delta < -SAME_WINDOW_SECS:
        return old
    if new["used_percentage"] >= (old.get("used_percentage") or 0):
        return new
    return old


def free(window, now):
    if not isinstance(window, dict):
        return None
    if window.get("resets_at", 0) <= now:
        return 100
    return max(0, round(100 - (window.get("used_percentage") or 0)))


def main():
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        payload = {}
    now = int(time.time())
    cache = load_cache()
    limits = payload.get("rate_limits") or {}
    merged = {key: merge_window(cache.get(key), limits.get(key), now) for key in WINDOWS}
    merged = {key: value for key, value in merged.items() if value}
    if merged != {key: cache.get(key) for key in merged}:
        try:
            save_cache(merged)
        except OSError:
            pass


    if "--save-only" in sys.argv[1:]:
        return

    parts = []
    model = (payload.get("model") or {}).get("display_name")
    if model:
        parts.append(f"[{model}]")
    five, week = free(merged.get("five_hour"), now), free(merged.get("seven_day"), now)
    if five is not None:
        parts.append(f"5h: {five}% free")
    if week is not None:
        parts.append(f"week: {week}% free")
    print(" · ".join(parts) if len(parts) > 1 else " ".join(parts))


if __name__ == "__main__":
    main()
