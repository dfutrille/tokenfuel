#!/usr/bin/env python3
"""Install quota collectors without replacing existing status-line settings."""


import argparse
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
HOME = os.path.expanduser("~")
BIN_DIR = os.path.join(HOME, ".local", "bin")
CACHE_DIR = os.path.join(HOME, ".cache", "tokenwatch")
STATUSLINE_NAME = "statusline-tokenwatch.py"


STATUSLINE_TOOLS = (
    {
        "name": "Claude Code",
        "dir": os.path.join(HOME, ".claude"),
        "script": "statusline/claude.py",
        "block": {"type": "command", "command": "~/.claude/" + STATUSLINE_NAME},
    },
    {
        "name": "Antigravity CLI (agy)",
        "dir": os.path.join(HOME, ".gemini", "antigravity-cli"),
        "script": "statusline/antigravity.py",
        "block": {
            "type": "command",
            "command": "~/.gemini/antigravity-cli/" + STATUSLINE_NAME,
            "enabled": True,
            "stack_with_default": True,
        },
    },
)


def short(path):

    return path.replace(HOME, "~", 1) if path.startswith(HOME) else path


def save_json(path, data):
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    if os.path.exists(path):
        shutil.copymode(path, tmp)
    os.replace(tmp, path)


def load_settings(path):

    if not os.path.exists(path):
        return {}, None
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        return None, str(exc)
    if not isinstance(data, dict):
        return None, "not a JSON object"
    return data, None


def backup(path):
    if os.path.exists(path):
        shutil.copy2(path, f"{path}.bak-{time.strftime('%Y%m%d-%H%M%S')}")


def is_ours(block):
    return isinstance(block, dict) and STATUSLINE_NAME in str(block.get("command", ""))


def install_statusline(tool):
    if not os.path.isdir(tool["dir"]):
        print(f"- {tool['name']}: not installed; skipped.")
        return
    target = os.path.join(tool["dir"], STATUSLINE_NAME)
    shutil.copy2(os.path.join(HERE, tool["script"]), target)
    os.chmod(target, 0o755)
    settings_path = os.path.join(tool["dir"], "settings.json")
    settings, error = load_settings(settings_path)
    if settings is None:
        print(f"! {tool['name']}: could not read {short(settings_path)} ({error}). Add this block manually:")
        print('    "statusLine": ' + json.dumps(tool["block"]))
        return
    current = settings.get("statusLine")
    if is_ours(current):
        print(f"- {tool['name']}: already configured; script updated.")
        return
    if current:
        print(f"! {tool['name']}: existing status line preserved.")
        print(f"  To collect quota, run this from your status line with the same stdin JSON:")
        print(f"    {short(target)} --save-only")
        return
    backup(settings_path)
    settings["statusLine"] = tool["block"]
    save_json(settings_path, settings)
    print(f"- {tool['name']}: status line configured in {short(settings_path)}.")


def install():
    os.makedirs(BIN_DIR, exist_ok=True)
    target = os.path.join(BIN_DIR, "tokenwatch")
    shutil.copy2(os.path.join(HERE, "tokenwatch"), target)
    os.chmod(target, 0o755)
    print(f"- tokenwatch installed in {short(target)}.")
    for tool in STATUSLINE_TOOLS:
        install_statusline(tool)
    if shutil.which("codex") or os.path.isdir(os.path.join(HOME, ".codex")):
        print("- Codex: detected; no setup required.")
    print("- OpenCode Go: no setup required; connected keys are detected.")

    if BIN_DIR not in os.environ.get("PATH", "").split(os.pathsep):
        print(f"\n! {short(BIN_DIR)} is not in PATH. Add this to ~/.bashrc or ~/.zshrc and open a new terminal:")
        print('    export PATH="$HOME/.local/bin:$PATH"')
    print("\nCurrent status:\n", flush=True)
    subprocess.run([sys.executable, target, "-v"], check=False)
    print("\nClaude and agy show no data until their status lines receive quota.")


def uninstall():
    for tool in STATUSLINE_TOOLS:
        settings_path = os.path.join(tool["dir"], "settings.json")
        settings, _ = load_settings(settings_path)
        if settings and is_ours(settings.get("statusLine")):
            backup(settings_path)
            del settings["statusLine"]
            save_json(settings_path, settings)
            print(f"- {tool['name']}: removed status line from {short(settings_path)}.")
        script = os.path.join(tool["dir"], STATUSLINE_NAME)
        if os.path.exists(script):
            os.remove(script)
    target = os.path.join(BIN_DIR, "tokenwatch")
    if os.path.exists(target):
        os.remove(target)
        print(f"- removed {short(target)}.")
    shutil.rmtree(CACHE_DIR, ignore_errors=True)
    print("- removed cached data in ~/.cache/tokenwatch.")


def main():
    parser = argparse.ArgumentParser(description="Install or remove tokenwatch.")
    parser.add_argument("--uninstall", action="store_true", help="remove tokenwatch and its settings")
    args = parser.parse_args()
    if os.name == "nt":
        sys.exit("tokenwatch supports Linux and macOS; use WSL on Windows.")
    if sys.version_info < (3, 8):
        sys.exit("tokenwatch requires Python 3.8 or newer.")
    uninstall() if args.uninstall else install()


if __name__ == "__main__":
    main()
