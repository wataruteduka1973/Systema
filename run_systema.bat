@echo off
setlocal
cd /d "%~dp0"

REM Remove the legacy environment now that this project uses .venv.

REM Prevent an old server process from sharing port 8000 with a new process.
netstat -ano | findstr ":8000" | findstr "LISTENING" >nul
if not errorlevel 1 goto :port_in_use

set "BASE_PYTHON=python"
where python >nul 2>&1
if errorlevel 1 (
    if exist "%LocalAppData%\Programs\Python\Python313\python.exe" (
        set "BASE_PYTHON=%LocalAppData%\Programs\Python\Python313\python.exe"
    ) else (
        echo Python was not found. Install Python 3 and try again.
        goto :error
    )
)

REM Recreate an environment whose launcher contains an obsolete project path.
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" --version >nul 2>&1
    if errorlevel 1 (
        echo Recreating the invalid .venv environment...
        rmdir /s /q ".venv"
    )
)

REM Create the project virtual environment when it does not exist.
if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment in .venv...
    "%BASE_PYTHON%" -m venv .venv
    if errorlevel 1 goto :error
)

set "PYTHON=.venv\Scripts\python.exe"

REM Install or update the required packages.
"%PYTHON%" -m pip install --upgrade pip
if errorlevel 1 goto :error
"%PYTHON%" -m pip install -r requirements.txt
if errorlevel 1 goto :error

REM Apply any pending database migrations.
"%PYTHON%" manage.py showmigrations --plan | findstr /C:"[ ]" >nul
if not errorlevel 1 (
    echo Applying migrations...
    "%PYTHON%" manage.py migrate
    if errorlevel 1 goto :error
) else (
    echo No migrations needed.
)

REM Start the development server.
"%PYTHON%" manage.py runserver 127.0.0.1:8000 --insecure
if errorlevel 1 goto :error
goto :end

:error
echo.
echo Systema failed to start.
pause
exit /b 1

:port_in_use
echo.
echo Port 8000 is already in use. Systema may already be running.
echo Stop the existing server with Ctrl+C, then run this file again.
echo If no server window is visible, restart Windows or stop the Python process using port 8000.
pause
exit /b 2

:end
endlocal
