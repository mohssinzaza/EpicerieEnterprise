"""Guard against shipping inconsistent application and installer versions."""
from pathlib import Path
import re

VERSION = '97'

def check_versions(root: Path) -> list[str]:
    errors = []
    app = (root / 'app.py').read_text(encoding='utf-8')
    installer = (root / 'installer.iss').read_text(encoding='utf-8')
    for marker in ('Épicerie Enterprise V' + VERSION, 'ÉPICERIE ENTERPRISE V' + VERSION):
        if marker not in app:
            errors.append('Missing application version label: ' + marker)
    match = re.search(r'^#define AppVersion "([^"]+)"', installer, re.MULTILINE)
    if not match or match.group(1) != VERSION + '.0-buildkit':
        errors.append('Installer version mismatch')
    return errors

if __name__ == '__main__':
    errors = check_versions(Path(__file__).resolve().parent)
    if errors:
        raise SystemExit('\n'.join(errors))
    print('Application and installer version labels match V' + VERSION)
