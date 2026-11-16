@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "NODEDECK_ISCC="
for /f "delims=" %%I in ('where iscc.exe 2^>nul') do if not defined NODEDECK_ISCC set "NODEDECK_ISCC=%%I"
if not defined NODEDECK_ISCC if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "NODEDECK_ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined NODEDECK_ISCC if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "NODEDECK_ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined NODEDECK_ISCC if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "NODEDECK_ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not defined NODEDECK_ISCC (
  echo Inno Setup 6 is required. https://jrsoftware.org/isdl.php
  exit /b 1
)
call build_windows.bat --app-only
if errorlevel 1 exit /b 1
"%NODEDECK_ISCC%" NodeDeckInstaller.iss
if errorlevel 1 exit /b 1
echo Installer: "%CD%\installer\NodeDeckSSH-Setup.exe"
