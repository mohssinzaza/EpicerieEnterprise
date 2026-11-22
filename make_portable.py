"""Package already-built Windows binaries, with a verifiable SHA-256 manifest.
Must run on Windows after PyInstaller. Never claims to build EXEs on Linux.
"""
from pathlib import Path
import hashlib
import json
import zipfile
import struct

ROOT = Path(__file__).resolve().parent
FILES = {
    'dist/EpicerieEnterprise.exe': 'EpicerieEnterprise.exe',
    'dist/EpicerieRecovery.exe': 'EpicerieRecovery.exe',
    'WINDOWS_ACCEPTANCE_AR.md': 'WINDOWS_ACCEPTANCE_AR.md',
}
LAUNCHER = '@echo off\r\ncd /d "%~dp0"\r\nstart "" "%~dp0EpicerieEnterprise.exe"\r\n'
README = ('EPICERIE ENTERPRISE V97 - Windows 10 x64 portable\r\n'
          'Extract ZIP then double-click EpicerieEnterprise.exe (or START_EPICERIE.bat).\r\n'
          'No Python or installer required on shop PC.\r\n'
          'Data: LOCALAPPDATA\\EpicerieEnterpriseV11.\r\n'
          'Test before using real business data.\r\n')

def _sha(data):
    return hashlib.sha256(data).hexdigest()

def is_x64_pe(data):
    """Require a structurally plausible AMD64 Windows PE executable."""
    if len(data) < 1024 or data[:2] != b'MZ':
        return False
    offset = struct.unpack_from('<I', data, 0x3c)[0]
    if offset < 64 or offset + 24 > len(data) or data[offset:offset+4] != b'PE\0\0':
        return False
    machine, sections, _, _, _, optional_size, _ = struct.unpack_from('<HHIIIHH', data, offset + 4)
    return machine == 0x8664 and 0 < sections <= 96 and optional_size >= 96


def verify_portable(path):
    """Check archive structure, exact file inventory, and content digests."""
    expected = set(FILES.values()) | {'START_EPICERIE.bat', 'READ_ME_FIRST.txt', 'SHA256_MANIFEST.json'}
    with zipfile.ZipFile(path) as z:
        if z.testzip() is not None:
            raise ValueError('Damaged ZIP')
        names = z.namelist()
        # Reject links and oversized archive members before extracting or hashing.
        for info in z.infolist():
            mode = (info.external_attr >> 16) & 0o170000
            if mode == 0o120000:
                raise ValueError('Symbolic links are forbidden in portable ZIP')
            if info.file_size > 250 * 1024 * 1024:
                raise ValueError('Oversized portable ZIP member')
        if len(names) != len(set(names)) or set(names) != expected:
            raise ValueError('Unexpected or duplicate portable files')
        manifest = json.loads(z.read('SHA256_MANIFEST.json'))
        if manifest.get('version') != '97' or set(manifest.get('files', {})) != expected - {'SHA256_MANIFEST.json'}:
            raise ValueError('Invalid manifest')
        for name, digest in manifest['files'].items():
            if _sha(z.read(name)) != digest:
                raise ValueError('SHA-256 mismatch: ' + name)
        for name in ('EpicerieEnterprise.exe', 'EpicerieRecovery.exe'):
            data = z.read(name)
            if not is_x64_pe(data):
                raise ValueError('Invalid Windows x64 executable: ' + name)
    return True

def make_portable(root=ROOT):
    root = Path(root)
    content = {}
    for rel, arc in FILES.items():
        p = root / rel
        if not p.is_file() or (arc.endswith('.exe') and not is_x64_pe(p.read_bytes())):
            raise RuntimeError('Missing/incomplete Windows build: ' + rel)
        content[arc] = p.read_bytes()
    content['START_EPICERIE.bat'] = LAUNCHER.encode('utf-8')
    content['READ_ME_FIRST.txt'] = README.encode('utf-8')
    manifest = {'version': '97', 'files': {name: _sha(data) for name, data in sorted(content.items())}}
    output = root / 'installer_output' / 'EpicerieEnterprise_Portable_Win10_x64.zip'
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for name, data in content.items():
            z.writestr(name, data)
        z.writestr('SHA256_MANIFEST.json', json.dumps(manifest, indent=2, sort_keys=True))
    verify_portable(output)
    return output

if __name__ == '__main__':
    print(make_portable())
