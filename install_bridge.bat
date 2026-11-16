@echo off
cd /d "%~dp0"
title KeePass Bridge Kurulumu
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_keepass_bridge.ps1"
if errorlevel 1 (
 echo.
 echo Hata: Program Files'a kopyalama icin Yonetici olarak calistirmayi deneyin.
)
pause
