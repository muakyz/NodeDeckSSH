@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title NodeDeck SSH - Windows EXE Builder

echo.
echo ================================================
echo   NODEDECK SSH - WINDOWS EXE BUILDER
echo ================================================
echo.
where py >nul 2>nul
if %ERRORLEVEL%==0 (
  set "PYTHON=py -3"
) else (
  where python >nul 2>nul
  if %ERRORLEVEL% neq 0 (
    echo HATA: Python 3 bulunamadi. https://www.python.org/downloads/windows/
    if /i not "%~1"=="--app-only" pause
    exit /b 1
  )
  set "PYTHON=python"
)
if not exist .venv\Scripts\python.exe (
  echo [1/4] Sanal Python ortami olusturuluyor...
  %PYTHON% -m venv .venv
  if errorlevel 1 goto :error
)
echo [2/4] Gerekli paketler kuruluyor...
.venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 goto :error
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto :error
echo [3/4] Windows EXE olusturuluyor...
for /f "delims=" %%D in ('.venv\Scripts\python.exe -c "import sys; print(sys.base_prefix)"') do set "NODEDECK_PYTHON_DLL=%%D\python3.dll"
if not exist "%NODEDECK_PYTHON_DLL%" (
  echo python3.dll is missing. Use full x64 Python from python.org.
  goto :error
)
.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm --onefile --windowed --name NodeDeckSSH --icon "assets\nodedeck.ico" --add-data "assets;assets" --add-binary "%NODEDECK_PYTHON_DLL%;." --collect-all winpty --copy-metadata pykeepass --hidden-import win32timezone launcher.py
if errorlevel 1 goto :error
echo [4/4] Hazir!
echo EXE: %CD%\dist\NodeDeckSSH.exe
if /i "%~1"=="--app-only" exit /b 0
where iscc >nul 2>nul
if %ERRORLEVEL%==0 (
  echo Inno Setup bulundu. Installer hazirlaniyor...
  iscc NodeDeckInstaller.iss
  if errorlevel 1 goto :error
)
echo.
pause
exit /b 0
:error
echo.
echo Build failed. Check the messages above.
if /i not "%~1"=="--app-only" pause
exit /b 1
