@echo off
setlocal
cd /d "%~dp0"

REM Remove the legacy environment now that this project uses .venv.

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
"%PYTHON%" manage.py runserver --insecure
if errorlevel 1 goto :error
goto :end

:error
echo.
echo Systema failed to start.
pause
exit /b 1

:end
endlocal
