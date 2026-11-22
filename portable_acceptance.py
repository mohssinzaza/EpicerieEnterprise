"""Windows-only acceptance test of the exact portable ZIP being delivered."""
from pathlib import Path
import subprocess
import tempfile
import zipfile
from make_portable import verify_portable


def test_portable_archive(archive, *, runner=subprocess.run):
    archive = Path(archive).resolve()
    verify_portable(archive)
    with tempfile.TemporaryDirectory(prefix='epicerie_accept_') as folder:
        extracted = Path(folder)
        with zipfile.ZipFile(archive) as z:
            for member in z.infolist():
                target = (extracted / member.filename).resolve()
                if not target.is_relative_to(extracted.resolve()):
                    raise ValueError('Unsafe archive path')
                z.extract(member, extracted)
        marker = extracted / 'portable_smoke_result.txt'
        executable = extracted / 'EpicerieEnterprise.exe'
        try:
            result = runner([str(executable), '--self-test', str(marker)],
                            cwd=extracted, timeout=120, check=False)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError('Portable executable self-test timed out') from exc
        except OSError as exc:
            raise RuntimeError('Portable executable could not start') from exc
        if result.returncode != 0 or not marker.is_file():
            raise RuntimeError('Portable executable self-test failed')
        if not marker.read_text(encoding='utf-8').startswith('PASS:'):
            raise RuntimeError('Portable executable did not pass self-test')
        recovery_marker = extracted / 'recovery_smoke_result.txt'
        recovery_exe = extracted / 'EpicerieRecovery.exe'

        try:
            recovery_result = runner(
                [str(recovery_exe), '--self-test', str(recovery_marker)],
                cwd=extracted,
                timeout=120,
                check=False
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError('Portable recovery self-test timed out') from exc
        except OSError as exc:
            raise RuntimeError('Portable recovery could not start') from exc

        if recovery_result.returncode != 0 or not recovery_marker.is_file():
            details = (
                recovery_marker.read_text(
                    encoding='utf-8', errors='replace'
                )
                if recovery_marker.is_file()
                else 'Recovery result file was not created'
            )
            raise RuntimeError(
                f'Portable recovery self-test failed. '
                f'Exit code: {recovery_result.returncode}. '
                f'Details: {details}'
            )

        if not recovery_marker.read_text(
            encoding='utf-8', errors='replace'
        ).startswith('PASS:'):
            raise RuntimeError(
                'Portable recovery executable did not pass self-test'
            )
    return True


if __name__ == '__main__':

    import sys
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python portable_acceptance.py <portable.zip>')
    test_portable_archive(sys.argv[1])
    print('PASS: portable archive executable tested successfully')
