#!/bin/bash
#================================================================
# SPMVV Result Analysis - Deployment Script (Linux)
# Sri Padmavati Mahila Visvavidyalayam
# 
# This script:
# 1. Backs up the existing MariaDB database (if running)
# 2. Stops and removes existing containers and images
# 3. Rebuilds and deploys the application using plain docker
# 4. Restores the database backup
# 5. Application runs on port 2271
#================================================================

set -e

# Configuration
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKUP_DIR="${PROJECT_DIR}/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/db_backup_${TIMESTAMP}.sql"

DB_CONTAINER="soet-db"
BACKEND_CONTAINER="soet-backend"
FRONTEND_CONTAINER="soet-frontend"
NETWORK_NAME="soet-network"
DB_VOLUME="soet-mysql-data"

DB_IMAGE="mariadb:10.11"
BACKEND_IMAGE="soet-backend:latest"
FRONTEND_IMAGE="soet-frontend:latest"

DB_PASSWORD="spmvv_root_2024"
DB_NAME="result_analysis"
APP_PORT="2271"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}================================================================${NC}"
echo -e "${BLUE}  SPMVV Result Analysis - Deployment Script${NC}"
echo -e "${BLUE}  Sri Padmavati Mahila Visvavidyalayam${NC}"
echo -e "${BLUE}================================================================${NC}"
echo ""

mkdir -p "${BACKUP_DIR}"

#================================================================
# Step 1: Backup existing database
#================================================================
echo -e "${YELLOW}[Step 1/5] Checking for existing database to backup...${NC}"

if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "^${DB_CONTAINER}$"; then
    echo -e "${GREEN}  -> Found running database container. Creating backup...${NC}"
    docker exec ${DB_CONTAINER} mysqladmin ping -h localhost -u root -p${DB_PASSWORD} --silent 2>/dev/null || true

    if docker exec ${DB_CONTAINER} mysqldump -u root -p${DB_PASSWORD} ${DB_NAME} > "${BACKUP_FILE}" 2>/dev/null; then
        if [ -s "${BACKUP_FILE}" ]; then
            echo -e "${GREEN}  -> Database backup created: ${BACKUP_FILE}${NC}"
            echo -e "${GREEN}  -> Backup size: $(du -h "${BACKUP_FILE}" | cut -f1)${NC}"
        else
            echo -e "${YELLOW}  -> Backup is empty (new install or empty DB)${NC}"
            rm -f "${BACKUP_FILE}"
            BACKUP_FILE=""
        fi
    else
        echo -e "${YELLOW}  -> Could not backup database (might be a fresh install)${NC}"
        rm -f "${BACKUP_FILE}"
        BACKUP_FILE=""
    fi
else
    echo -e "${YELLOW}  -> No existing database container found. Skipping backup.${NC}"
    BACKUP_FILE=""
fi
echo ""

#================================================================
# Step 2: Stop and remove existing containers
#================================================================
echo -e "${YELLOW}[Step 2/5] Stopping and removing existing containers...${NC}"

for container in ${FRONTEND_CONTAINER} ${BACKEND_CONTAINER} ${DB_CONTAINER}; do
    if docker ps -a --format '{{.Names}}' 2>/dev/null | grep -q "^${container}$"; then
        echo -e "${GREEN}  -> Stopping & removing: ${container}${NC}"
        docker stop ${container} 2>/dev/null || true
        docker rm -f ${container} 2>/dev/null || true
    fi
done

echo -e "${GREEN}  -> All existing containers removed${NC}"
echo ""

#================================================================
# Step 3: Remove existing images (keep base images)
#================================================================
echo -e "${YELLOW}[Step 3/5] Removing existing application images...${NC}"

for image in ${BACKEND_IMAGE} ${FRONTEND_IMAGE}; do
    if docker images --format '{{.Repository}}:{{.Tag}}' 2>/dev/null | grep -q "^${image}$"; then
        echo -e "${GREEN}  -> Removing image: ${image}${NC}"
        docker rmi -f ${image} 2>/dev/null || true
    fi
done

docker image prune -f 2>/dev/null || true
echo -e "${GREEN}  -> Old images cleaned up${NC}"
echo ""

#================================================================
# Step 4: Build and start containers
#================================================================
echo -e "${YELLOW}[Step 4/5] Building and starting application...${NC}"

# Create network if not exists
docker network inspect ${NETWORK_NAME} >/dev/null 2>&1 || \
    docker network create ${NETWORK_NAME}
echo -e "${GREEN}  -> Network '${NETWORK_NAME}' ready${NC}"

# Create volume if not exists
docker volume inspect ${DB_VOLUME} >/dev/null 2>&1 || \
    docker volume create ${DB_VOLUME}
echo -e "${GREEN}  -> Volume '${DB_VOLUME}' ready${NC}"

# --- MariaDB ---
echo -e "${YELLOW}  -> Starting MariaDB...${NC}"
docker run -d \
    --name ${DB_CONTAINER} \
    --network ${NETWORK_NAME} \
    --restart unless-stopped \
    -e MYSQL_ROOT_PASSWORD=${DB_PASSWORD} \
    -e MYSQL_DATABASE=${DB_NAME} \
    -v ${DB_VOLUME}:/var/lib/mysql \
    ${DB_IMAGE}
echo -e "${GREEN}  -> MariaDB container started${NC}"

# Wait for DB to be healthy
echo -e "${YELLOW}  -> Waiting for MariaDB to be ready...${NC}"
MAX_WAIT=120
WAIT_COUNT=0
while [ $WAIT_COUNT -lt $MAX_WAIT ]; do
    if docker exec ${DB_CONTAINER} mysqladmin ping -h localhost -u root -p${DB_PASSWORD} --silent 2>/dev/null; then
        echo -e "${GREEN}  -> MariaDB is ready!${NC}"
        break
    fi
    WAIT_COUNT=$((WAIT_COUNT + 2))
    sleep 2
    echo -ne "\r${YELLOW}  -> Waiting... (${WAIT_COUNT}s / ${MAX_WAIT}s)${NC}   "
done
echo ""

if [ $WAIT_COUNT -ge $MAX_WAIT ]; then
    echo -e "${RED}  -> ERROR: MariaDB did not become ready in time${NC}"
    exit 1
fi

# --- Backend ---
echo -e "${YELLOW}  -> Building backend image...${NC}"
docker build -t ${BACKEND_IMAGE} "${PROJECT_DIR}/backend"
echo -e "${GREEN}  -> Backend image built${NC}"

echo -e "${YELLOW}  -> Starting backend...${NC}"
docker run -d \
    --name ${BACKEND_CONTAINER} \
    --network ${NETWORK_NAME} \
    --restart unless-stopped \
    -e DB_HOST=${DB_CONTAINER} \
    -e DB_PORT=3306 \
    -e DB_USER=root \
    -e DB_PASSWORD=${DB_PASSWORD} \
    -e DB_NAME=${DB_NAME} \
    -e JWT_SECRET_KEY=spmvv-result-analysis-secret-key-2024 \
    ${BACKEND_IMAGE} \
    sh -c "python init_db.py && gunicorn --bind 0.0.0.0:5000 --workers 4 --timeout 120 app:app"
echo -e "${GREEN}  -> Backend container started${NC}"

# --- Frontend ---
echo -e "${YELLOW}  -> Building frontend image...${NC}"
docker build -t ${FRONTEND_IMAGE} "${PROJECT_DIR}/frontend"
echo -e "${GREEN}  -> Frontend image built${NC}"

echo -e "${YELLOW}  -> Starting frontend...${NC}"
docker run -d \
    --name ${FRONTEND_CONTAINER} \
    --network ${NETWORK_NAME} \
    --restart unless-stopped \
    -p ${APP_PORT}:80 \
    ${FRONTEND_IMAGE}
echo -e "${GREEN}  -> Frontend container started${NC}"

# Wait for backend init_db.py to finish
echo -e "${YELLOW}  -> Waiting for backend initialization...${NC}"
sleep 10
echo ""

#================================================================
# Step 5: Restore database backup
#================================================================
echo -e "${YELLOW}[Step 5/5] Restoring database backup...${NC}"

if [ -n "${BACKUP_FILE}" ] && [ -f "${BACKUP_FILE}" ] && [ -s "${BACKUP_FILE}" ]; then
    echo -e "${GREEN}  -> Restoring from: ${BACKUP_FILE}${NC}"
    sleep 3
    if docker exec -i ${DB_CONTAINER} mysql -u root -p${DB_PASSWORD} ${DB_NAME} < "${BACKUP_FILE}" 2>/dev/null; then
        echo -e "${GREEN}  -> Database restored successfully!${NC}"
    else
        echo -e "${YELLOW}  -> Warning: Could not restore backup. Starting with fresh database.${NC}"
    fi
else
    echo -e "${YELLOW}  -> No backup to restore. Starting with fresh database.${NC}"
fi

echo ""

#================================================================
# Summary
#================================================================
echo -e "${BLUE}================================================================${NC}"
echo -e "${GREEN}  Deployment Complete!${NC}"
echo -e "${BLUE}================================================================${NC}"
echo ""
echo -e "${GREEN}  Application URL: http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo 'localhost'):${APP_PORT}${NC}"
echo -e "${GREEN}  Admin Login:     username: admin | password: admin123${NC}"
echo ""
echo -e "${BLUE}  Container Status:${NC}"
docker ps --format "  {{.Names}}\t{{.Status}}\t{{.Ports}}" --filter "name=soet" 2>/dev/null
echo ""
echo -e "${BLUE}================================================================${NC}"
