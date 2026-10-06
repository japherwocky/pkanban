@echo off
rem pkanban installer for the Windows Command Prompt.
rem
rem   curl -fsSL __PKANBAN_SERVER__/install.cmd -o install.cmd && install.cmd && del install.cmd
rem
rem CMD cannot run a script from a pipe, hence the download-run-delete. The
rem work is done by install.ps1, through the PowerShell every Windows ships
rem with; this only hands over to it.

setlocal
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm '__PKANBAN_SERVER__/install.ps1' | iex"
if errorlevel 1 exit /b 1
echo.
echo Open a new Command Prompt to use pkanban: this one started before it was installed.
endlocal
