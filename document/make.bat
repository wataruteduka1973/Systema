@echo off
setlocal

if "%SPHINXBUILD%" == "" set "SPHINXBUILD=sphinx-build"
set "SOURCEDIR=%~dp0"
set "BUILDDIR=%~dp0build"

if "%1" == "" goto help
if /I "%1" == "clean" (
    "%SPHINXBUILD%" -M clean "%SOURCEDIR%" "%BUILDDIR%" -W --keep-going
    if errorlevel 1 exit /b %errorlevel%
    shift
    if "%1" == "" exit /b 0
)

"%SPHINXBUILD%" -M %1 "%SOURCEDIR%" "%BUILDDIR%" -W --keep-going
exit /b %errorlevel%

:help
echo Usage: document\make.bat clean html
exit /b 1
