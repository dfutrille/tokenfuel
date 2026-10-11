#!/usr/bin/env python3
"""Collect Antigravity quota from stdin without rendering output."""


import json
import os
import sys
import tempfile
import time
from datetime import datetime

CACHE = os.path.expanduser("~/.cache/tokenwatch/agy.json")

SAME_WINDOW_SECS = 120


def reset_epoch(entry):
    try:
        return datetime.fromisoformat(entry["reset_time"].replace("Z", "+00:00")).timestamp()
    except (AttributeError, KeyError, TypeError, ValueError):
        return None


def merge_bucket(old, new, now):


    if not isinstance(new, dict) or new.get("remaining_fraction") is None or reset_epoch(new) is None:
        return old
    new = {"remaining_fraction": new["remaining_fraction"], "reset_time": new["reset_time"], "seen_at": now}
    if not isinstance(old, dict) or reset_epoch(old) is None:
        return new
    delta = reset_epoch(new) - reset_epoch(old)
    if delta > SAME_WINDOW_SECS:
        return new
    if delta < -SAME_WINDOW_SECS:
        return old
    if new["remaining_fraction"] <= old.get("remaining_fraction", 1):
        return new
    return old


def main():
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return
    if not isinstance(payload, dict) or not isinstance(payload.get("quota"), dict):
        return
    now = int(time.time())
    try:
        with open(CACHE, encoding="utf-8") as fh:
            cached = json.load(fh).get("quota") or {}
    except (OSError, ValueError, AttributeError):
        cached = {}
    quota = {}
    for key in set(cached) | set(payload["quota"]):
        bucket = merge_bucket(cached.get(key), payload["quota"].get(key), now)
        if bucket:
            quota[key] = bucket
    if quota == cached:
        return
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(CACHE), prefix=".agy-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump({"quota": quota, "plan_tier": payload.get("plan_tier")}, fh)
        os.replace(tmp, CACHE)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
