@echo off
chcp 65001 > nul
title NNY 디코봇 (4차원 주머니)
cd /d "%~dp0.."
git pull --ff-only >nul 2>&1
py -3.12 -X utf8 tools\discord_bot.py
pause
