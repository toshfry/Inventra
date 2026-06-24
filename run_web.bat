@echo off
cd /d "%~dp0"
if exist venv\Scripts\activate.bat call venv\Scripts\activate.bat
pip install flask --quiet
echo.
echo Starting Inventra Web...
python web_server.py
pause
