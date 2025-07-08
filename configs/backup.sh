#!/bin/bash

# AnchorPoint Surveillance System - Backup Script
# This script creates automated backups of system configuration and data

set -e

# Configuration
BACKUP_DIR="/data/backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="anchorpoint_backup_${DATE}"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_NAME}"

# Create backup directory if it doesn't exist
mkdir -p "${BACKUP_PATH}"

echo "Starting AnchorPoint backup: ${BACKUP_NAME}"

# Backup SQLite database
echo "Backing up database..."
cp /data/anchorpoint.db "${BACKUP_PATH}/anchorpoint.db"

# Backup Frigate configuration
echo "Backing up Frigate configuration..."
cp -r /config "${BACKUP_PATH}/frigate_config"

# Backup system settings
echo "Backing up system settings..."
cp -r /data/system_settings.json "${BACKUP_PATH}/system_settings.json" 2>/dev/null || true

# Backup Caddy configuration
echo "Backing up Caddy configuration..."
cp -r /etc/caddy "${BACKUP_PATH}/caddy_config" 2>/dev/null || true

# Create backup manifest
cat > "${BACKUP_PATH}/backup_manifest.txt" << EOF
AnchorPoint Backup Manifest
===========================
Backup Date: $(date)
Backup Name: ${BACKUP_NAME}
System Version: $(cat /data/version.txt 2>/dev/null || echo "Unknown")

Included Files:
- anchorpoint.db (User database)
- frigate_config/ (Frigate configuration)
- system_settings.json (System settings)
- caddy_config/ (Caddy configuration)

Backup Size: $(du -sh "${BACKUP_PATH}" | cut -f1)
EOF

# Create compressed archive
echo "Creating compressed archive..."
cd "${BACKUP_DIR}"
tar -czf "${BACKUP_NAME}.tar.gz" "${BACKUP_NAME}"
rm -rf "${BACKUP_NAME}"

# Clean up old backups (keep last 7 days)
echo "Cleaning up old backups..."
find "${BACKUP_DIR}" -name "anchorpoint_backup_*.tar.gz" -mtime +7 -delete

echo "Backup completed: ${BACKUP_DIR}/${BACKUP_NAME}.tar.gz"

# Optional: Upload to cloud storage (uncomment and configure as needed)
# echo "Uploading to cloud storage..."
# rclone copy "${BACKUP_DIR}/${BACKUP_NAME}.tar.gz" "backup:anchorpoint/"

echo "Backup process completed successfully!" 