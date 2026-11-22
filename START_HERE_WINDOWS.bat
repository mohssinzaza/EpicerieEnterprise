@echo off
setlocal
cd /d "%~dp0"
echo ==========================================
echo   EPICERIE ENTERPRISE - WINDOWS BUILD
 echo ==========================================
echo This package is SOURCE CODE, not an installer.
echo On this BUILD computer install Python 3.10+ and Inno Setup 6.
echo Your shop computer will NOT need Python after Setup.exe is built.
echo.
choice /C YN /M "Build the Windows installer now"
if errorlevel 2 exit /b 0
call "%~dp0BUILD_ON_WINDOWS.bat"
if errorlevel 1 (
 echo.
 echo BUILD FAILED. Do NOT use an old installer.
 pause
 exit /b 1
)
echo.
echo Build finished. Run the installer from installer_output.
echo Before real sales, test printing, barcode, backup and restore.
pause
