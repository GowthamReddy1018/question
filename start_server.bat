@echo off
echo Starting Telugu Q&A Generator Server...
echo.
py -m uvicorn app:app --reload --host 0.0.0.0 --port 8000
pause
