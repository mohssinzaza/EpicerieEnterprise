@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo EPICERIE ENTERPRISE V97 - PORTABLE WINDOWS 10 x64
if /i not "%PROCESSOR_ARCHITECTURE%"=="AMD64" if /i not "%PROCESSOR_ARCHITEW6432%"=="AMD64" (
 echo ERROR: This build must run on 64-bit Windows.
 exit /b 1
)
set "PYTHON_CMD=py -3"
where py >nul 2>nul
if errorlevel 1 (
 where python >nul 2>nul
 if errorlevel 1 (
  echo ERROR: Python 3.10+ required on the BUILD computer only.
  exit /b 1
 )
 set "PYTHON_CMD=python"
)
%PYTHON_CMD% -c "import sys; assert sys.version_info >= (3,10), 'Python 3.10+ required'" || goto error
%PYTHON_CMD% -c "import struct; assert struct.calcsize('P') == 8, '64-bit Python is required for x64 Windows builds'" || goto error
%PYTHON_CMD% -m venv .buildvenv || goto error
call .buildvenv\Scripts\activate.bat || goto error
python -m pip install --upgrade pip || goto error
python -m pip install "pyinstaller==6.16.0" "tzdata>=2026.1" || goto error
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

python make_portable.py || goto error
python portable_acceptance.py "installer_output\EpicerieEnterprise_Portable_Win10_x64.zip" || goto error
if not exist "installer_output\EpicerieEnterprise_Portable_Win10_x64.zip" goto error
echo.
echo SUCCESS: installer_output\EpicerieEnterprise_Portable_Win10_x64.zip
echo Copy ZIP to shop computer, extract, and run START_EPICERIE.bat.
echo No Python or Inno Setup is needed on the shop computer.
exit /b 0
:error
echo FAILED. Do not distribute incomplete build.
exit /b 1
