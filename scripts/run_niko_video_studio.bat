@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0.."
title Niko Video Studio

if not exist "envs.json" (
    echo [!] envs.json not found. Run scripts\install.bat first.
    pause
    exit /b 1
)

set "ENV_TYPE="
set "ENV_PATH="
for /f "tokens=1,2,3 delims=|" %%A in ('python setup.py get_env_info 2^>nul') do (
    if "%%A"=="ENV_INFO" (
        set "ENV_TYPE=%%B"
        set "ENV_PATH=%%C"
    )
)

if "!ENV_TYPE!"=="" (
    echo [!] No active WanGP environment found.
    pause
    exit /b 1
)

if "!ENV_TYPE!"=="venv" (
    call "!ENV_PATH!\Scripts\activate.bat"
) else if "!ENV_TYPE!"=="uv" (
    call "!ENV_PATH!\Scripts\activate.bat"
) else if "!ENV_TYPE!"=="conda" (
    set "CONDA_BAT="
    where conda >nul 2>nul
    if !errorlevel! equ 0 set "CONDA_BAT=conda"
    if "!CONDA_BAT!"=="" if exist "%USERPROFILE%\Miniconda3\condabin\conda.bat" set "CONDA_BAT=%USERPROFILE%\Miniconda3\condabin\conda.bat"
    if "!CONDA_BAT!"=="" if exist "%USERPROFILE%\Anaconda3\condabin\conda.bat" set "CONDA_BAT=%USERPROFILE%\Anaconda3\condabin\conda.bat"
    if "!CONDA_BAT!"=="" (
        echo [!] Could not find conda.bat.
        pause
        exit /b 1
    )
    call "!CONDA_BAT!" activate "!ENV_PATH!"
) else if not "!ENV_TYPE!"=="none" (
    echo [!] Unknown environment type: !ENV_TYPE!
    pause
    exit /b 1
)

if "%NIKO_VIDEO_HOST%"=="" set "NIKO_VIDEO_HOST=127.0.0.1"
if "%NIKO_VIDEO_PORT%"=="" set "NIKO_VIDEO_PORT=7870"

echo [*] Starting Niko Video Studio on http://%NIKO_VIDEO_HOST%:%NIKO_VIDEO_PORT%
python niko_video_studio.py --host "%NIKO_VIDEO_HOST%" --port "%NIKO_VIDEO_PORT%" %*

pause
