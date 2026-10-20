import ast
import copy
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


app = load('tokenwatch', ROOT / 'tokenwatch')
claude = load('claude_status', ROOT / 'statusline/claude.py')
agy = load('agy_status', ROOT / 'statusline/antigravity.py')
clone = load('clone_go', ROOT / 'tools/clone-opencode-go.py')


class QuotaTests(unittest.TestCase):
    def provider(self, name, five=80, week=90, month=None):
        return {'name': name, 'five_hour': app.window(five, 2000, 1000, 1000),
                'week': app.window(week, 3000, 1000, 1000),
                'month': app.window(month, 4000, 1000, 1000)}

    def test_expired_window_and_clamping(self):
        self.assertEqual(app.window(0, 999, 900, 1000)['remaining'], 100)
        self.assertTrue(app.window(0, 999, 900, 1000)['reset'])
        self.assertEqual(app.window(150)['remaining'], 100)
        self.assertEqual(app.window(-1)['remaining'], 0)

    def test_availability_and_monthly_block(self):
        rows = [self.provider('blocked', 100, 90, 0), self.provider('low', 20),
                self.provider('unknown', None), self.provider('high', 80)]
        self.assertEqual([p['name'] for p in app.by_availability(rows)], ['high', 'low', 'blocked', 'unknown'])
        self.assertEqual(app.blocking_window(rows[0])[0], 'month')

    def test_recommendation_families_exclusions_and_emergency(self):
        prefs = copy.deepcopy(app.DEFAULT_PREFS)
        prefs['providers'] = {'claude': {'models': {'easy': []}}, 'agy-claude-gpt': {'emergency_only': True}}
        ranked, discarded = app.recommend([self.provider('opencode-go-2', 70), self.provider('opencode-go', 90),
                self.provider('claude'), self.provider('codex', 100, 0), self.provider('agy-claude-gpt')], 'easy', prefs, 1000)
        self.assertEqual([p['name'] for p in ranked], ['opencode-go', 'opencode-go-2'])
        self.assertEqual(len(discarded), 3)

    def test_unknown_quota_returns_exit_one(self):
        args = type('Args', (), {'local': True, 'best': 'easy', 'json': True})()
        with patch.object(app, 'read_claude', return_value=[self.provider('claude', None)]), \
             patch.object(app, 'read_codex', return_value=[]), patch.object(app, 'read_agy', return_value=[]), \
             patch.object(app, 'read_opencode', return_value=[]), \
             patch.object(app, 'load_prefs', return_value=copy.deepcopy(app.DEFAULT_PREFS)):
            text, code = app.best_report(args, 1000)
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(text)['recommended'][0]['notes'], ['no data'])

    def test_collectors_merge_conservatively(self):
        old = {'used_percentage': 80, 'resets_at': 2000, 'seen_at': 900}
        self.assertEqual(claude.merge_window(old, {'used_percentage': 75, 'resets_at': 2001}, 1000), old)
        self.assertEqual(claude.merge_window(old, {'used_percentage': 0, 'resets_at': 4000}, 1000)['used_percentage'], 0)
        old = {'remaining_fraction': .2, 'reset_time': '2030-01-01T00:00:00Z'}
        self.assertEqual(agy.merge_bucket(old, {'remaining_fraction': .25, 'reset_time': old['reset_time']}, 1000), old)

    def test_collectors_accept_reset_within_same_window(self):
        old = {'used_percentage': 97, 'resets_at': 2000, 'seen_at': 900}
        self.assertEqual(claude.merge_window(old, {'used_percentage': 0, 'resets_at': 2000}, 1000)['used_percentage'], 0)
        old = {'remaining_fraction': .03, 'reset_time': '2030-01-01T00:00:00Z'}
        self.assertEqual(agy.merge_bucket(old, {'remaining_fraction': 1, 'reset_time': old['reset_time']}, 1000)['remaining_fraction'], 1)

    def test_python38_syntax(self):
        for path in [ROOT / 'tokenwatch', ROOT / 'install.py', *ROOT.glob('statusline/*.py'), *ROOT.glob('tools/*.py')]:
            ast.parse(path.read_text(), feature_version=(3, 8))

    def test_opencode_offline_never_contacts_endpoint(self):
        with tempfile.TemporaryDirectory() as home:
            auth = Path(home) / 'auth.json'
            auth.write_text(json.dumps({'opencode-go': {'key': 'synthetic-test-key'}}))
            with patch.object(app, 'OPENCODE_AUTH', str(auth)), patch.object(app, 'CACHE_DIR', home), \
                 patch.object(app.urllib.request, 'urlopen', side_effect=AssertionError('unexpected network')):
                rows = app.read_opencode(1000, live=False)
            self.assertEqual(rows[0]['name'], 'opencode-go')
            self.assertIsNone(rows[0]['five_hour'])

    def test_opencode_paid_lists_api_keys_only(self):
        with tempfile.TemporaryDirectory() as home:
            auth = Path(home) / 'auth.json'
            auth.write_text(json.dumps({'opencode-go': {'type': 'api', 'key': 'synthetic-go'},
                                        'anthropic': {'type': 'api', 'key': 'synthetic-test-key'},
                                        'openai': {'type': 'oauth', 'access': 'synthetic-token'},
                                        'empty': {'type': 'api', 'key': ''}}))
            with patch.object(app, 'OPENCODE_AUTH', str(auth)):
                paid = app.read_opencode_paid()
        self.assertEqual(paid, [{'name': 'opencode-anthropic', 'command': 'opencode -m anthropic/<model>'}])
        self.assertNotIn('synthetic', json.dumps(paid))

    def test_clone_refuses_existing_provider(self):
        model = {'id': 'example-model', 'api': {'url': 'https://opencode.ai/zen/go/v1', 'npm': '@ai-sdk/openai-compatible'}}
        with tempfile.TemporaryDirectory() as home:
            config = Path(home) / 'nested/config.json'
            with patch.object(clone, 'source_models', return_value=[model]), patch.object(sys, 'argv', ['clone', str(config)]):
                clone.main()
                data = json.loads(config.read_text())
                self.assertEqual(data['provider']['opencode-go-2']['env'], ['OPENCODE_GO_2_API_KEY'])
                with self.assertRaises(SystemExit):
                    clone.main()
            self.assertEqual(json.loads(config.read_text()), data)

    def test_install_uninstall_preserves_custom_settings(self):
        with tempfile.TemporaryDirectory() as home:
            env = {**os.environ, 'HOME': home, 'PATH': '/usr/bin:/bin', 'XDG_CONFIG_HOME': home + '/.config', 'XDG_DATA_HOME': home + '/.local/share'}
            settings = Path(home) / '.claude/settings.json'
            settings.parent.mkdir()
            original = {'statusLine': {'type': 'command', 'command': 'custom-status'}, 'other': True}
            settings.write_text(json.dumps(original))
            agy_settings = Path(home) / '.gemini/antigravity-cli/settings.json'
            agy_settings.parent.mkdir(parents=True)
            agy_settings.write_text('{"other": true}')
            for flags in ([], [], ['--uninstall']):
                result = subprocess.run([sys.executable, str(ROOT / 'install.py'), *flags], env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(settings.read_text()), original)
            self.assertEqual(json.loads(agy_settings.read_text()), {'other': True})
            self.assertFalse((Path(home) / '.local/bin/tokenwatch').exists())


if __name__ == '__main__':
    unittest.main()
