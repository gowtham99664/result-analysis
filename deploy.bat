@echo off
REM ================================================================
REM SPMVV Result Analysis - Deployment Script (Windows)
REM Sri Padmavati Mahila Visvavidyalayam
REM
REM Uses plain docker commands with MariaDB 10.11
REM This script:
REM 1. Backs up the existing MariaDB database (if running)
REM 2. Stops and removes existing containers and images
REM 3. Rebuilds and deploys the application
REM 4. Restores the database backup
REM 5. Application runs on port 2271
REM ================================================================

setlocal enabledelayedexpansion

set DB_CONTAINER=spmvv-db
set BACKEND_CONTAINER=spmvv-backend
set FRONTEND_CONTAINER=spmvv-frontend
set NETWORK_NAME=spmvv-network
set DB_VOLUME=spmvv-mysql-data

set DB_IMAGE=mariadb:10.11
set BACKEND_IMAGE=spmvv-backend:latest
set FRONTEND_IMAGE=spmvv-frontend:latest

set DB_PASSWORD=spmvv_root_2024
set DB_NAME=result_analysis
set APP_PORT=2271

set PROJECT_DIR=%~dp0
set BACKUP_DIR=%PROJECT_DIR%backups

REM Get timestamp for backup filename
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set datetime=%%I
set TIMESTAMP=%datetime:~0,8%_%datetime:~8,6%
set BACKUP_FILE=%BACKUP_DIR%\db_backup_%TIMESTAMP%.sql

echo ================================================================
echo   SPMVV Result Analysis - Deployment Script (Windows)
echo   Sri Padmavati Mahila Visvavidyalayam
echo ================================================================
echo.

REM Create backup directory
if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

REM ================================================================
REM Step 1: Backup existing database
REM ================================================================
echo [Step 1/5] Checking for existing database to backup...

docker ps --format "{{.Names}}" 2>nul | findstr /C:"%DB_CONTAINER%" >nul 2>&1
if %errorlevel% equ 0 (
    echo   -^> Found running database container. Creating backup...

    docker exec %DB_CONTAINER% mysqldump -u root -p%DB_PASSWORD% %DB_NAME% > "%BACKUP_FILE%" 2>nul

    if exist "%BACKUP_FILE%" (
        for %%A in ("%BACKUP_FILE%") do set FILESIZE=%%~zA
        if !FILESIZE! gtr 0 (
            echo   -^> Database backup created: %BACKUP_FILE%
        ) else (
            echo   -^> Database backup is empty. Skipping restore later.
            del "%BACKUP_FILE%" 2>nul
            set BACKUP_FILE=
        )
    ) else (
        echo   -^> Could not create backup. Might be a fresh install.
        set BACKUP_FILE=
    )
) else (
    echo   -^> No existing database container found. Skipping backup.
    set BACKUP_FILE=
)

echo.

REM ================================================================
REM Step 2: Stop and remove existing containers
REM ================================================================
echo [Step 2/5] Stopping and removing existing containers...

for %%c in (%FRONTEND_CONTAINER% %BACKEND_CONTAINER% %DB_CONTAINER%) do (
    docker ps -a --format "{{.Names}}" 2>nul | findstr /C:"%%c" >nul 2>&1
    if !errorlevel! equ 0 (
        echo   -^> Stopping ^& removing: %%c
        docker stop %%c 2>nul
        docker rm -f %%c 2>nul
    )
)

echo   -^> All existing containers removed
echo.

REM ================================================================
REM Step 3: Remove existing application images
REM ================================================================
echo [Step 3/5] Removing existing application images...

for %%i in (%BACKEND_IMAGE% %FRONTEND_IMAGE%) do (
    docker images --format "{{.Repository}}:{{.Tag}}" 2>nul | findstr /C:"%%i" >nul 2>&1
    if !errorlevel! equ 0 (
        echo   -^> Removing image: %%i
        docker rmi -f %%i 2>nul
    )
)

docker image prune -f 2>nul

echo   -^> Old images cleaned up
echo.

REM ================================================================
REM Step 4: Build and start containers
REM ================================================================
echo [Step 4/5] Building and starting application...

REM Create network if not exists
docker network inspect %NETWORK_NAME% >nul 2>&1
if %errorlevel% neq 0 (
    docker network create %NETWORK_NAME%
)
echo   -^> Network '%NETWORK_NAME%' ready

REM Create volume if not exists
docker volume inspect %DB_VOLUME% >nul 2>&1
if %errorlevel% neq 0 (
    docker volume create %DB_VOLUME%
)
echo   -^> Volume '%DB_VOLUME%' ready

REM --- MariaDB ---
echo   -^> Starting MariaDB...
docker run -d ^
    --name %DB_CONTAINER% ^
    --network %NETWORK_NAME% ^
    --restart unless-stopped ^
    -e MYSQL_ROOT_PASSWORD=%DB_PASSWORD% ^
    -e MYSQL_DATABASE=%DB_NAME% ^
    -v %DB_VOLUME%:/var/lib/mysql ^
    %DB_IMAGE%
echo   -^> MariaDB container started

REM Wait for DB to be healthy
echo   -^> Waiting for MariaDB to be ready...
set /a WAIT_COUNT=0
set /a MAX_WAIT=120

:WAIT_LOOP
if %WAIT_COUNT% geq %MAX_WAIT% goto WAIT_TIMEOUT

docker exec %DB_CONTAINER% mysqladmin ping -h localhost -u root -p%DB_PASSWORD% --silent 2>nul
if %errorlevel% equ 0 (
    echo   -^> MariaDB is ready!
    goto WAIT_DONE
)

set /a WAIT_COUNT+=2
timeout /t 2 /nobreak >nul
echo   -^> Waiting... (%WAIT_COUNT%s / %MAX_WAIT%s)
goto WAIT_LOOP

:WAIT_TIMEOUT
echo   -^> ERROR: MariaDB did not become ready in time
exit /b 1

:WAIT_DONE

REM --- Backend ---
echo   -^> Building backend image...
docker build -t %BACKEND_IMAGE% "%PROJECT_DIR%backend"
echo   -^> Backend image built

echo   -^> Starting backend...
docker run -d ^
    --name %BACKEND_CONTAINER% ^
    --network %NETWORK_NAME% ^
    --restart unless-stopped ^
    -e DB_HOST=%DB_CONTAINER% ^
    -e DB_PORT=3306 ^
    -e DB_USER=root ^
    -e DB_PASSWORD=%DB_PASSWORD% ^
    -e DB_NAME=%DB_NAME% ^
    -e JWT_SECRET_KEY=spmvv-result-analysis-secret-key-2024 ^
    %BACKEND_IMAGE% ^
    sh -c "python init_db.py && gunicorn --bind 0.0.0.0:5000 --workers 4 --timeout 120 app:app"
echo   -^> Backend container started

REM --- Frontend ---
echo   -^> Building frontend image...
docker build -t %FRONTEND_IMAGE% "%PROJECT_DIR%frontend"
echo   -^> Frontend image built

echo   -^> Starting frontend...
docker run -d ^
    --name %FRONTEND_CONTAINER% ^
    --network %NETWORK_NAME% ^
    --restart unless-stopped ^
    -p %APP_PORT%:80 ^
    %FRONTEND_IMAGE%
echo   -^> Frontend container started

REM Wait for backend init_db.py to finish
echo   -^> Waiting for backend initialization...
timeout /t 10 /nobreak >nul
echo.

REM ================================================================
REM Step 5: Restore database backup
REM ================================================================
echo [Step 5/5] Restoring database backup...

if defined BACKUP_FILE (
    if exist "%BACKUP_FILE%" (
        echo   -^> Restoring from: %BACKUP_FILE%

        timeout /t 5 /nobreak >nul

        docker exec -i %DB_CONTAINER% mysql -u root -p%DB_PASSWORD% %DB_NAME% < "%BACKUP_FILE%" 2>nul
        if !errorlevel! equ 0 (
            echo   -^> Database restored successfully!
        ) else (
            echo   -^> Warning: Could not restore backup. Starting with fresh database.
        )
    ) else (
        echo   -^> No backup file found. Starting with fresh database.
    )
) else (
    echo   -^> No backup to restore. Starting with fresh database.
)

echo.

REM ================================================================
REM Summary
REM ================================================================
echo ================================================================
echo   Deployment Complete!
echo ================================================================
echo.
echo   Application URL: http://localhost:%APP_PORT%
echo   Admin Login:     username: admin ^| password: admin123
echo.
echo   Container Status:
docker ps --format "  {{.Names}}	{{.Status}}	{{.Ports}}" --filter "name=spmvv" 2>nul
echo.
echo ================================================================

pause
