@echo off
cd /d W:\SWE\projects\youtube-content-intelligence
set PYTHONIOENCODING=utf-8
".venv\Scripts\python.exe" main.py >> logs\run_log.txt 2>&1