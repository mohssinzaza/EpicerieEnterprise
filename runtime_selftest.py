"""Run a non-destructive offline smoke test of the *packaged* executable.
Uses a temporary database; never touches the shop database.
"""
from pathlib import Path

def run_self_test(marker):
    try:
        from release_check import smoke
        smoke()
        Path(marker).write_text('PASS: packaged executable smoke test\n', encoding='utf-8')
        return 0
    except Exception as exc:
        Path(marker).write_text('FAIL: ' + repr(exc) + '\n', encoding='utf-8')
        return 1
