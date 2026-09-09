@echo off
setlocal
cd /d "%~dp0"

REM Remove the legacy environment now that this project uses .venv.

REM PostgreSQL is the default development database. Values already configured
REM in the launching shell are preserved; missing credentials are requested for
REM this process only and are discarded when the window closes.
if not defined DB_ENGINE set "DB_ENGINE=postgresql"
if /I "%DB_ENGINE%"=="postgresql" (
    if not defined DB_NAME set "DB_NAME=Yahuoku_analyze_DB"
    if not defined DB_HOST set "DB_HOST=localhost"
    if not defined DB_PORT set "DB_PORT=5432"
    if not defined DB_SSLMODE set "DB_SSLMODE=prefer"
    if not defined DB_USER set /p "DB_USER=PostgreSQL user: "
    if not defined DB_PASSWORD (
        for /f "usebackq delims=" %%P in (`powershell.exe -NoProfile -Command "$value = Read-Host 'PostgreSQL password' -AsSecureString; [System.Net.NetworkCredential]::new('', $value).Password"`) do set "DB_PASSWORD=%%P"
    )
    if not defined DB_USER (
        echo DB_USER is required for PostgreSQL.
        goto :error
    )
    if not defined DB_PASSWORD (
        echo DB_PASSWORD is required for PostgreSQL.
        goto :error
    )
)

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

REM DEBUG is false by default, so collect assets for WhiteNoise before startup.
echo Collecting static files...
"%PYTHON%" manage.py collectstatic --noinput
if errorlevel 1 goto :error

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
