@echo off
title New Neo Duel
cd /d "%~dp0"
echo ==============================================
echo    New Neo Duel - bootstrap
echo ==============================================
echo.

rem -- 1) find python 3.10+  (everything else lives in the repo: scripts\BOOT)
set PYEXE=
set PYCHK=import sys; sys.exit(0 if sys.version_info>=(3,10) else 9)
python -c "%PYCHK%" >nul 2>&1
if not errorlevel 1 set PYEXE=python
if defined PYEXE goto GETREPO
py -3 -c "%PYCHK%" >nul 2>&1
if not errorlevel 1 set PYEXE=py -3
if defined PYEXE goto GETREPO
py -3.12 -c "%PYCHK%" >nul 2>&1
if not errorlevel 1 set PYEXE=py -3.12
if defined PYEXE goto GETREPO
echo  [!] Python 3.10+ not found. Opening python.org - install with
echo      "Add python.exe to PATH" checked, then run this file again.
start https://www.python.org/downloads/
pause
exit /b 1

:GETREPO
rem -- 2) fetch the game once (updates are done by the repo itself: scripts\BOOT)
if exist "NewNeoDuel" goto RUN
git --version >nul 2>&1
if errorlevel 1 goto ZIP
git clone -q --depth 1 -b DuelModel https://github.com/somlon/card_simulation_model.git NewNeoDuel
if not errorlevel 1 goto RUN
:ZIP
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $u='https://codeload.github.com/somlon/card_simulation_model/zip/refs/heads/DuelModel'; $z=Join-Path $env:TEMP 'nnduel.zip'; Invoke-WebRequest -UseBasicParsing $u -OutFile $z; $d=Join-Path $env:TEMP ('nnduel_'+(Get-Random)); Expand-Archive -Path $z -DestinationPath $d -Force; $i=(Get-ChildItem $d -Directory | Select-Object -First 1).FullName; New-Item -ItemType Directory -Force -Path 'NewNeoDuel' | Out-Null; Copy-Item (Join-Path $i '*') -Destination 'NewNeoDuel' -Recurse -Force; Remove-Item $z,$d -Recurse -Force"
if errorlevel 1 (
  echo  [!] download failed - check internet connection and run again.
  pause
  exit /b 1
)

:RUN
rem -- update when possible (zip users get updated by re-downloading; git users here)
if exist "NewNeoDuel\.git" (
  pushd NewNeoDuel
  git pull -q --rebase
  popd
)
rem -- 3) hand over to the repo-side bootstrap (fixable on GitHub, no redistribution)
%PYEXE% "NewNeoDuel\scripts\ºÎÆ®.py" %*
echo.
echo  game server closed.
pause
