@echo off
setlocal
cd /d "%~dp0"
where docker >nul 2>nul
if errorlevel 1 goto missingdocker
where py >nul 2>nul
if errorlevel 1 goto missingpython
where npm >nul 2>nul
if errorlevel 1 goto missingnode
py -3.12 scripts\configure.py
if errorlevel 1 goto failed
docker compose up -d --wait db
if errorlevel 1 goto failed
echo Setting up Python dependencies...
if not exist backend\.venv\Scripts\python.exe py -3.12 -m venv backend\.venv
if errorlevel 1 goto failed
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
if errorlevel 1 goto failed
pushd backend
.venv\Scripts\python.exe -m alembic upgrade head
if errorlevel 1 (popd & goto failed)
.venv\Scripts\python.exe -m app.seed
if errorlevel 1 (popd & goto failed)
popd
call npm ci --prefix frontend
if errorlevel 1 goto failed
start "GymOS API" /D "%CD%\backend" cmd /k ".venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log"
start "GymOS Notifications" /D "%CD%\backend" cmd /k ".venv\Scripts\python.exe -m app.jobs"
start "GymOS Frontend" /D "%CD%\frontend" cmd /k "npm run dev"
echo.
echo Open http://localhost:5173 after Vite reports ready.
echo Sign-in details are in .local-credentials.txt. Keep this file private.
echo Close the three application windows to stop. Run docker compose stop db to stop the database.
pause
exit /b 0
:missingdocker
echo Install Docker Desktop with WSL 2 and start Docker Desktop.
goto failed
:missingpython
echo Install Python 3.12 with the py launcher.
goto failed
:missingnode
echo Install Node.js 24 LTS, then reopen this window.
:failed
echo Setup failed. Read the error above and docs\TROUBLESHOOTING.md.
pause
exit /b 1
