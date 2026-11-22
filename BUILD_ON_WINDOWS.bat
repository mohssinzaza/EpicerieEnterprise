@echo off
setlocal EnableExtensions
set "PYTHONUTF8=1"
cd /d "%~dp0"
echo EPICERIE ENTERPRISE V95 - WINDOWS 10 x64 INSTALLER
if /i not "%PROCESSOR_ARCHITECTURE%"=="AMD64" if /i not "%PROCESSOR_ARCHITEW6432%"=="AMD64" (
 echo ERROR: Windows x64 required.
 exit /b 1
)
set "PYTHON_CMD=python"
where py >nul 2>nul
if errorlevel 1 (
 where python >nul 2>nul
 if errorlevel 1 (
  echo ERROR: Python 3.10+ is required on the BUILD PC.
  exit /b 1
 )
 set "PYTHON_CMD=python"
)
%PYTHON_CMD% -c "import sys; assert sys.version_info >= (3,10), 'Python 3.10+ required'" || goto error
%PYTHON_CMD% -c "import struct; assert struct.calcsize('P') == 8, '64-bit Python required'" || goto error
%PYTHON_CMD% -m venv .buildvenv || goto error
call .buildvenv\Scripts\activate.bat || goto error
python -m pip install --upgrade pip || goto error
python -m pip install "pyinstaller==6.22.3" "tzdata>=2026.1" || goto error


python -c "import datetime,tzdata,zoneinfo; from zoneinfo import ZoneInfo; d=datetime.datetime(2026,11,22); print('TZDATA:',tzdata.__version__); print('ZONEINFO PATH:',zoneinfo.TZPATH); print('DEFAULT OFFSET:',d.replace(tzinfo=ZoneInfo('Africa/Casablanca')).utcoffset()); zoneinfo.reset_tzpath([]); ZoneInfo.clear_cache(); print('TZDATA ONLY OFFSET:',d.replace(tzinfo=ZoneInfo('Africa/Casablanca')).utcoffset())" || goto error


python release_check.py || goto error
python release_version.py || goto error
python -m unittest discover -s tests -q || goto error
if exist "dist" rmdir /s /q "dist"
if exist "installer_output" rmdir /s /q "installer_output"
if exist "dist" goto error
if exist "installer_output" goto error
python -m PyInstaller --noconfirm --clean --onefile --windowed --name EpicerieEnterprise --collect-all tzdata app.py || goto error
python -m PyInstaller --noconfirm --clean --onefile --windowed --name EpicerieRecovery recovery_gui.py || goto error
if not exist "dist\EpicerieEnterprise.exe" goto error
if not exist "dist\EpicerieRecovery.exe" goto error
if exist "packaged_smoke_result.txt" del /q "packaged_smoke_result.txt"
"dist\EpicerieEnterprise.exe" --self-test "%CD%\packaged_smoke_result.txt" || goto error
if not exist "packaged_smoke_result.txt" goto error
findstr /b /c:"PASS:" "packaged_smoke_result.txt" >nul || goto error

echo Executables ready in dist\
set "ISCC="
where ISCC.exe >nul 2>nul
if not errorlevel 1 set "ISCC=ISCC.exe"
if not defined ISCC if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC (
 echo ERROR: Inno Setup 6 required for a complete installer.
 goto error
)
"%ISCC%" "installer.iss" || goto error
if not exist "installer_output\EpicerieEnterprise_Setup.exe" goto error
python make_portable.py || goto error
python portable_acceptance.py "installer_output\EpicerieEnterprise_Portable_Win10_x64.zip" || goto error
if not exist "installer_output\EpicerieEnterprise_Portable_Win10_x64.zip" goto error
python verify_windows_build.py || goto error
python -c "from pathlib import Path; from verify_windows_build import verify_manifest; errors=verify_manifest(Path.cwd()); print('\n'.join(errors) if errors else 'Release manifest verified'); raise SystemExit(bool(errors))" || goto error
echo Installer ready: installer_output\EpicerieEnterprise_Setup.exe
echo IMPORTANT: test the EXEs, backup, printer and barcode reader on Windows before business use.
exit /b 0
:error
echo BUILD FAILED: do not distribute incomplete artifacts.
exit /b 1
