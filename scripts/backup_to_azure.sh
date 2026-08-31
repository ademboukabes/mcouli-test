#!/bin/bash
# MultAI Backup Script
# This script creates a pg_dump and minio snapshot, storing them in /backups
# Future Azure integration lines are included but commented out until a Storage Account is created.

set -e

BACKUP_DIR="/home/adembks/multai/backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
PG_BACKUP_FILE="multai_db_$TIMESTAMP.sql.gz"
MINIO_BACKUP_FILE="multai_media_$TIMESTAMP.tar.gz"

mkdir -p "$BACKUP_DIR"

echo "=== Starting Backup [$TIMESTAMP] ==="

# 1. PostgreSQL Backup
echo "Dumping PostgreSQL database..."
sudo docker exec multi_postgres pg_dump -U multai_prod -d multi_ai_prod | gzip > "$BACKUP_DIR/$PG_BACKUP_FILE"
echo "Database backed up to $BACKUP_DIR/$PG_BACKUP_FILE"

# 2. MinIO Backup (Archiving the volume)
echo "Archiving MinIO data..."
# We use sudo tar on the docker volume directory directly or copy from the container
sudo docker run --rm --volumes-from multi_minio -v "$BACKUP_DIR":/backup ubuntu tar czf /backup/"$MINIO_BACKUP_FILE" /data
echo "MinIO backed up to $BACKUP_DIR/$MINIO_BACKUP_FILE"

# 3. Cleanup local backups older than 7 days
echo "Cleaning up local backups older than 7 days..."
find "$BACKUP_DIR" -type f -name "*.gz" -mtime +7 -exec rm {} \;

# ==============================================================================
# AZURE BLOB STORAGE INTEGRATION (Pending Azure Storage Account Creation)
# ==============================================================================
# To enable this, you need an Azure Storage Account and an SAS token, or az CLI logged in.
#
# AZURE_STORAGE_URL="https://<YOUR_ACCOUNT_NAME>.blob.core.windows.net/<YOUR_CONTAINER_NAME>?<SAS_TOKEN>"
# 
# echo "Uploading to Azure Blob Storage..."
# azcopy copy "$BACKUP_DIR/$PG_BACKUP_FILE" "$AZURE_STORAGE_URL"
# azcopy copy "$BACKUP_DIR/$MINIO_BACKUP_FILE" "$AZURE_STORAGE_URL"
# echo "Azure Upload Complete."

echo "=== Backup Finished Successfully ==="
