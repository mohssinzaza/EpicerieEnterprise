"""Structural validation and SHA-256 manifest for Windows release artifacts.

This is not a substitute for executing and testing the binaries on Windows.
"""
from pathlib import Path
import hashlib
import json
import struct
import sys

REQUIRED = (
    Path('dist/EpicerieEnterprise.exe'),
    Path('dist/EpicerieRecovery.exe'),
    Path('installer_output/EpicerieEnterprise_Setup.exe'),
)


def is_pe(path: Path) -> bool:
    """Validate DOS stub, PE offset, signature and basic COFF header."""
    with path.open('rb') as stream:
        header = stream.read(64)
        if len(header) < 64 or header[:2] != b'MZ':
            return False
        offset = struct.unpack_from('<I', header, 0x3c)[0]
        size = path.stat().st_size
        if offset < 64 or offset + 24 > size:
            return False
        stream.seek(offset)
        coff = stream.read(24)
        if len(coff) != 24 or coff[:4] != b'PE\0\0':
            return False
        machine, sections, _, _, _, optional_size, _ = struct.unpack('<HHIIIHH', coff[4:])
        return machine in (0x8664, 0x14c) and 0 < sections <= 96 and optional_size >= 96


def verify(root: Path) -> list[str]:
    errors = []
    for relative in REQUIRED:
        path = root / relative
        if not path.is_file():
            errors.append(f'Missing: {relative}')
        elif path.stat().st_size < 1024:
            errors.append(f'Too small: {relative}')
        elif not is_pe(path):
            errors.append(f'Invalid Windows PE header: {relative}')
    return errors


def write_manifest(root: Path, filename='installer_output/build_manifest.json') -> Path:
    """Write hashes only after all release artifacts pass structural checks."""
    errors = verify(root)
    if errors:
        raise ValueError('; '.join(errors))
    files = {}
    for relative in REQUIRED:
        digest = hashlib.sha256()
        with (root / relative).open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(chunk)
        files[relative.as_posix()] = {
            'sha256': digest.hexdigest(),
            'size_bytes': (root / relative).stat().st_size,
        }
    target = root / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({'files': files}, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return target


if __name__ == '__main__':
    root = Path(__file__).resolve().parent
    problems = verify(root)
    if problems:
        print('\n'.join(problems), file=sys.stderr)
        raise SystemExit(1)
    manifest = write_manifest(root)
    print(f'PE structural checks passed; SHA-256 manifest: {manifest}')
    print('Windows runtime, installer, printer, barcode and backup tests remain required.')


def verify_manifest(root: Path, filename='installer_output/build_manifest.json') -> list[str]:
    """Recheck the release against its previously generated SHA-256 manifest."""
    manifest = root / filename
    if not manifest.is_file():
        return [f'Missing manifest: {filename}']
    try:
        data = json.loads(manifest.read_text(encoding='utf-8'))
        entries = data['files']
        expected = {p.as_posix() for p in REQUIRED}
        if not isinstance(entries, dict) or set(entries) != expected:
            return ['Manifest artifact list mismatch']
        errors = []
        for relative in REQUIRED:
            name = relative.as_posix()
            item = entries[name]
            if not isinstance(item, dict) or set(item) != {'sha256', 'size_bytes'}:
                errors.append(f'Invalid manifest entry: {name}')
                continue
            size = item['size_bytes']
            digest = item['sha256']
            if type(size) is not int or size < 1024 or not isinstance(digest, str) or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
                errors.append(f'Invalid manifest metadata: {name}')
                continue
            path = root / relative
            if not path.is_file() or path.is_symlink():
                errors.append(f'Missing or linked artifact: {name}')
                continue
            if path.stat().st_size != size:
                errors.append(f'Size mismatch: {name}')
                continue
            hasher = hashlib.sha256()
            with path.open('rb') as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                    hasher.update(chunk)
            if hasher.hexdigest() != digest:
                errors.append(f'SHA-256 mismatch: {name}')
        return errors
    except (OSError, UnicodeError, ValueError, TypeError, KeyError, AttributeError):
        return ['Invalid or unreadable release manifest']
