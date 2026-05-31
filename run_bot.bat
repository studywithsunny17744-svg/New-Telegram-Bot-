@echo off
title Mani 272 Bot Runner
cls
echo ==========================================
echo       MANI 272 BOT STARTER
echo ==========================================
echo.
echo [1] Checking dependencies...
pip install -r requirements.txt --quiet
echo [2] Starting bot.py...
echo.
python bot.py
echo.
echo ------------------------------------------
echo Bot has stopped or crashed.
echo Press any key to exit.
pause > nul
