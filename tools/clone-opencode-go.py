#!/usr/bin/env python3
"""Explicitly clone OpenCode Go model metadata for a separately connected key."""


import argparse
import json
import os
import shutil
import subprocess
import sys
import time

SOURCE = "opencode-go"
DEFAULT_CONFIG = os.path.expanduser("~/.config/opencode/opencode.json")


def source_models():
    out = subprocess.run(
        ["opencode", "models", SOURCE, "--verbose"], capture_output=True, text=True, timeout=120, check=True
    ).stdout

    decoder, pos, models = json.JSONDecoder(), 0, []
    while (start := out.find("{", pos)) >= 0:
        try:
            model, length = decoder.raw_decode(out[start:])
        except ValueError:
            pos = start + 1
            continue
        models.append(model)
        pos = start + length
    return models


def to_config(model):
    caps = model.get("capabilities") or {}
    cost = model.get("cost") or {}
    cache = cost.get("cache") or {}
    entry = {
        "name": model.get("name") or model["id"],
        "attachment": bool(caps.get("attachment")),
        "reasoning": bool(caps.get("reasoning")),
        "temperature": bool(caps.get("temperature")),
        "tool_call": bool(caps.get("toolcall")),
        "cost": {
            "input": cost.get("input", 0),
            "output": cost.get("output", 0),
            "cache_read": cache.get("read", 0),
            "cache_write": cache.get("write", 0),
        },
        "limit": {key: value for key, value in (model.get("limit") or {}).items() if value is not None},
        "modalities": {
            side: [kind for kind, on in (caps.get(side) or {}).items() if on] for side in ("input", "output")
        },

        "provider": {"npm": (model.get("api") or {}).get("npm")},
    }
    for key in ("family", "release_date"):
        if model.get(key):
            entry[key] = model[key]
    if caps.get("interleaved"):
        entry["interleaved"] = caps["interleaved"]
    if model.get("status") and model["status"] != "active":
        entry["status"] = model["status"]
    for key in ("options", "headers"):
        if model.get(key):
            entry[key] = model[key]
    return entry


def main():
    parser = argparse.ArgumentParser(description="Clone the OpenCode Go provider under a separate ID.")
    parser.add_argument("config", nargs="?", default=DEFAULT_CONFIG, help="OpenCode configuration file")

    parser.add_argument("--id", default="opencode-go-2", help="new provider ID (must start with opencode-go-)")
    args = parser.parse_args()
    if not args.id.startswith("opencode-go-") or args.id == SOURCE:
        parser.error("ID must start with opencode-go-")

    models = source_models()
    if not models:
        sys.exit("could not read OpenCode Go models")
    apis = {(model.get("api") or {}).get("url") for model in models}
    if len(apis) != 1:
        sys.exit(f"models use multiple base URLs; expected one: {sorted(map(str, apis))}")

    env_var = args.id.upper().replace("-", "_") + "_API_KEY"
    provider = {
        "name": "OpenCode Go " + args.id.rsplit("-", 1)[-1],
        "npm": "@ai-sdk/openai-compatible",
        "api": apis.pop(),
        "env": [env_var],
        "models": {model["id"]: to_config(model) for model in models},
    }

    config = {"$schema": "https://opencode.ai/config.json"}
    if os.path.exists(args.config):
        with open(args.config, encoding="utf-8") as fh:
            config = json.load(fh)
        shutil.copy2(args.config, f"{args.config}.bak-{time.strftime('%Y%m%d-%H%M%S')}")
    if args.id in config.get("provider", {}):
        parser.error("provider ID already exists; choose a new ID")
    config.setdefault("provider", {})[args.id] = provider
    os.makedirs(os.path.dirname(os.path.abspath(args.config)), exist_ok=True)
    tmp = f"{args.config}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(config, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    if os.path.exists(args.config):
        shutil.copymode(args.config, tmp)
    os.replace(tmp, args.config)
    print(f"{args.id}: {len(models)} models written to {args.config}")
    print(f"key: /connect -> Other -> {args.id}, or environment variable {env_var}")


if __name__ == "__main__":
    main()
