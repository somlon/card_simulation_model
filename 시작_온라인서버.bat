@echo off
chcp 65001 > nul
title NNY 온라인 서버
rem 코드 최신화(이 브랜치) 후 서버 실행. runtime/data 는 바탕화면 NNY_Simulator(zip 원본)를 쓴다.
cd /d "%~dp0"
git pull --ff-only
if errorlevel 1 echo (경고) git pull 실패 - 기존 코드로 실행합니다.
set BASE=%USERPROFILE%\Desktop\NNY_Simulator
if not exist "%BASE%untime\python.exe" echo 바탕화면 NNY_Simulator 폴더(zip 원본)가 필요합니다 && pause && exit /b 1
"%BASE%untime\python.exe" -I -X utf8 nny_simpp\main.py --sim nny_sim --viewer nny_simiewer --split "%BASE%\data\split" --cards "%BASE%\data\cards" --library "%BASE%\data\library" %*
pause
