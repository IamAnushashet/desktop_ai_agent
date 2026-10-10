@echo off
setlocal

if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
) else if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
)

echo Starting Desktop AI Agent Remote Control Server...
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
