# tokenwatch

See how much subscription quota remains in Claude Code, Codex CLI, Antigravity CLI (`agy`), and OpenCode Go. One executable, Python standard library only. Quota checks do not invoke a model or consume model tokens.

```bash
tokenwatch                 # Remaining five-hour quota
tokenwatch -v              # Full table, reset times and data age
tokenwatch --json           # Structured output
tokenwatch --local          # Offline readings only
tokenwatch --live 30       # Live table; Ctrl+C to exit
tokenwatch --best hard      # Recommend a provider: easy, medium or hard
tokenwatch --agent-guide    # Instructions for AI agents
```

## Installation

Linux or macOS, Python 3.8+. Windows users can use WSL. macOS and older Python runtimes have not been tested; Python 3.8 syntax compatibility is checked automatically.

```bash
git clone https://github.com/dfutrille/tokenwatch.git
cd tokenwatch
python3 install.py
```

The installer copies the command to `~/.local/bin` and adds quota collectors for installed Claude Code and agy. It backs up settings before editing them and preserves existing status lines. Codex and OpenCode need no additional setup. Ensure `~/.local/bin` is in your PATH:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Claude and agy show `no data` until a session sends quota to the collector. If you already use a custom status line, run the installed collector with the same JSON on stdin:

```bash
~/.claude/statusline-tokenwatch.py --save-only
# For agy: ~/.gemini/antigravity-cli/statusline-tokenwatch.py
```

The agy collector never prints output. The Claude collector normally prints model and remaining quota. Installation does not modify global agent instructions or preferences.

```bash
python3 install.py --uninstall
```

Uninstallation removes tokenwatch, its collectors, its own status-line settings, and its cache. It preserves unrelated settings and preferences.

## Reading the output

Percentages show quota **remaining**. The full table includes five-hour, weekly, and optional monthly windows, local reset times, time until reset, and reading age. A passed reset is treated as 100% remaining. Readings older than 30 minutes are marked in the short output.

Rows sort by available five-hour quota, then weekly quota. Providers with weekly or monthly quota below 5% sort below usable providers, by reset time. Unknown readings come last. JSON uses a fixed provider order.

Five-hour colors: green at 60%+, yellow at 30%+, orange at 10%+, red below 10%. A red row with a crossed-out name indicates a weekly/monthly block. Provider name colors identify providers. Colors require a terminal unless `--color` is used; `--no-color` and `NO_COLOR` disable automatic colors. JSON never includes colors. `--live` uses an alternate terminal screen and restores it on Ctrl+C.

## Recommendations and preferences

`--best LEVEL` prints a ranked list and suggested launch commands. It only informs: it does not launch agents or change their configuration. Exit status 1 means no recommended provider has enough known quota. Blocked providers are excluded. Low or unknown five-hour readings move to the end; emergency providers appear when no regular provider has enough quota. Multiple OpenCode keys share family preferences and sort by availability.

```bash
mkdir -p ~/.config/tokenwatch
cp examples/preferences.json ~/.config/tokenwatch/preferences.json
```

The example is generic; choose model IDs supported by your installed tools and plan. Empty model lists exclude a provider for that level. Without preferences, recommendations use a generic order without specifying models.

| Key | Meaning |
| --- | --- |
| `min_five_hour` | Five-hour percentage below which recommendations move to the end |
| `levels` | Provider family order for `easy`, `medium`, `hard` |
| `providers.NAME.models` | Model IDs by level; first model appears in launch command |
| `providers.NAME.notes` | Conditions or notes by level |
| `providers.NAME.emergency_only` | Reserve for when regular providers lack quota |
| `providers.NAME.avoid` | Model IDs prohibited in the agent guide |
| `free` | Unmetered model IDs and permitted use |

Add this to your agents' global instructions if desired:

> Before opening a session in another AI tool or delegating work, run `tokenwatch --agent-guide` and follow its provider and model selection instructions. This command does not consume model tokens.

## OpenCode Go and multiple keys

Each connected provider ID starting with `opencode-go` produces a separate row, including five-hour, weekly and monthly quota. The optional helper clones model metadata under a new provider ID:

```bash
python3 tools/clone-opencode-go.py --id opencode-go-2
# Optional positional argument: alternate OpenCode JSON configuration path
```

This helper changes OpenCode configuration only when explicitly run. It backs up existing configuration and refuses an existing provider ID. Connect the new key inside OpenCode via `/connect` → Other → the new ID, or use the environment variable printed by the helper. Keys are never passed as command-line arguments. Re-run with a new ID when you need another provider. Plain JSON configuration is required.

Other providers connected in OpenCode with an API key (for example `anthropic`) are pay per use and have no quota windows. They appear as an informational `opencode-<id>` line in `-v`, `--best`, `--agent-guide` and as `pay_per_use` in `--json`, and are never recommended automatically.

## Sources, privacy and limitations

- Claude Code: limits received by its status line, saved in `~/.cache/tokenwatch/claude.json`.
- agy: quota received by its status line, saved in `~/.cache/tokenwatch/agy.json`.
- Codex: `codex app-server` reads account limits; falls back to the latest local session readings and cached results.
- OpenCode pay-per-use providers: only the provider IDs and key type are read from the same auth file; the keys are neither read into output nor sent anywhere.
- OpenCode Go: reads connected keys from the local OpenCode auth file and sends each key only to `https://opencode.ai/zen/go/v1/usage`. This endpoint is undocumented and may change.

No telemetry or third-party analytics are included. Credentials are not printed or copied into the repository. Codex uses its existing signed-in session. Cached quota responses stay on your machine. Live queries have a six-second timeout and are reused for 60 seconds. `--local` skips live queries. Claude/agy readings can be stale; API-key billing may not expose subscription windows. Provider protocol changes may require updates.

Collectors merge readings from multiple sessions conservatively: within the same window, the most consumed reading wins unless usage drops by 10 points or more (a reset or plan upgrade); across windows, the later reset wins. Collectors use atomic file replacement, but simultaneous read/merge/write operations are not locked. Wide tables may wrap in narrow terminals; orange requires 256-color support.

## Development

```bash
python3 -m unittest discover -s tests -v
```

Tests use synthetic quota and isolated home directories; they do not invoke models or contact usage endpoints. Licensed under MIT.
