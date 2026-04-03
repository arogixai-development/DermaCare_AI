#!/bin/bash

# ==============================================================================
# DermaCare AI - Backup Script
# ==============================================================================
# Automated backup to Oracle Cloud Object Storage
# Usage: ./backup.sh [full|incremental|restore]
# ==============================================================================

set -e

# Configuration
BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DB_NAME="${DB_NAME:-dermacare}"
DB_USER="${DB_USER:-dermacare}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }

# ==============================================================================
# Database Backup
# ==============================================================================

backup_database() {
    log "Starting database backup..."
    
    mkdir -p "$BACKUP_DIR"
    
    local backup_file="$BACKUP_DIR/${DB_NAME}_${TIMESTAMP}.sql"
    
    # Check if running in docker
    if docker ps --format '{{.Names}}' | grep -q "^dermacare-db$"; then
        log "Using Docker container for backup..."
        docker exec dermacare-db pg_dump -U "$DB_USER" "$DB_NAME" > "$backup_file"
    else
        log "Using local PostgreSQL for backup..."
        pg_dump -U "$DB_USER" -h localhost "$DB_NAME" > "$backup_file"
    fi
    
    # Compress backup
    gzip "$backup_file"
    backup_file="${backup_file}.gz"
    
    local size=$(du -h "$backup_file" | cut -f1)
    log "Database backup created: $backup_file ($size)"
    
    echo "$backup_file"
}

# ==============================================================================
# File Backup
# ==============================================================================

backup_files() {
    log "Starting file backup..."
    
    local backup_file="$BACKUP_DIR/files_${TIMESTAMP}.tar.gz"
    
    tar -czf "$backup_file" \
        -C "$(dirname "$PWD")" \
        "$(basename "$PWD")/backend" \
        "$(basename "$PWD")/data" \
        2>/dev/null || {
        log_warning "Could not backup all files"
    }
    
    local size=$(du -h "$backup_file" | cut -f1)
    log "File backup created: $backup_file ($size)"
    
    echo "$backup_file"
}

# ==============================================================================
# Cleanup Old Backups
# ==============================================================================

cleanup_old_backups() {
    log "Cleaning up backups older than $RETENTION_DAYS days..."
    
    # Database backups
    find "$BACKUP_DIR" -name "${DB_NAME}_*.sql.gz" -type f -mtime +$RETENTION_DAYS -delete 2>/dev/null || true
    
    # File backups
    find "$BACKUP_DIR" -name "files_*.tar.gz" -type f -mtime +$RETENTION_DAYS -delete 2>/dev/null || true
    
    log "Cleanup completed"
}

# ==============================================================================
# Upload to Oracle Cloud Object Storage
# ==============================================================================

upload_to_oracle_cloud() {
    local file="$1"
    
    # Check if OCI CLI is configured
    if ! command -v oci &> /dev/null; then
        log_warning "OCI CLI not installed. Skipping cloud upload."
        log_info "Install: curl -sL https://raw.githubusercontent.com/oracle/oci-cli/master/scripts/install/install.sh | bash"
        return 1
    fi
    
    local bucket="${OCI_BUCKET_NAME:-dermacare-backups}"
    local namespace="${OCI_NAMESPACE}"
    
    if [ -z "$namespace" ]; then
        log_warning "OCI namespace not configured. Skipping cloud upload."
        return 1
    fi
    
    log "Uploading to Oracle Cloud Object Storage..."
    
    oci os object put \
        --bucket-name "$bucket" \
        --file "$file" \
        --name "dermacare/$(basename "$file")" \
        --namespace "$namespace" || {
        log_error "Failed to upload to Oracle Cloud"
        return 1
    }
    
    log "Uploaded successfully to Oracle Cloud"
}

# ==============================================================================
# Restore from Backup
# ==============================================================================

restore_database() {
    local backup_file="$1"
    
    if [ ! -f "$backup_file" ]; then
        log_error "Backup file not found: $backup_file"
        exit 1
    fi
    
    log "WARNING: This will overwrite the current database!"
    read -p "Are you sure? (yes/no): " confirm
    
    if [ "$confirm" != "yes" ]; then
        log "Restore cancelled"
        exit 0
    fi
    
    log "Restoring database from $backup_file..."
    
    # Decompress if needed
    if [[ "$backup_file" == *.gz ]]; then
        gunzip -c "$backup_file" | docker exec -i dermacare-db psql -U "$DB_USER" "$DB_NAME"
    else
        cat "$backup_file" | docker exec -i dermacare-db psql -U "$DB_USER" "$DB_NAME"
    fi
    
    log "Database restored successfully"
}

# ==============================================================================
# List Backups
# ==============================================================================

list_backups() {
    log "Available backups:"
    echo ""
    
    echo "=== Database Backups ==="
    ls -lah "$BACKUP_DIR"/${DB_NAME}_*.sql.gz 2>/dev/null || echo "No database backups found"
    echo ""
    
    echo "=== File Backups ==="
    ls -lah "$BACKUP_DIR"/files_*.tar.gz 2>/dev/null || echo "No file backups found"
    echo ""
    
    echo "=== Oracle Cloud Backups ==="
    if command -v oci &> /dev/null && [ -n "${OCI_NAMESPACE:-}" ]; then
        oci os object list --bucket-name "${OCI_BUCKET_NAME:-dermacare-backups}" --namespace "$OCI_NAMESPACE" 2>/dev/null || echo "Could not list Oracle Cloud backups"
    else
        echo "OCI not configured"
    fi
}

# ==============================================================================
# Main Menu
# ==============================================================================

case "${1:-full}" in
    full)
        log "=== Full Backup ==="
        backup_database
        backup_files
        cleanup_old_backups
        
        # Upload to cloud if configured
        if [ -n "${OCI_NAMESPACE:-}" ]; then
            upload_to_oracle_cloud "$(ls -t "$BACKUP_DIR"/${DB_NAME}_*.sql.gz 2>/dev/null | head -1)"
        fi
        
        log "Full backup completed!"
        ;;
    
    incremental)
        log "=== Incremental Backup ==="
        backup_database
        cleanup_old_backups
        log "Incremental backup completed!"
        ;;
    
    files)
        log "=== File Backup ==="
        backup_files
        log "File backup completed!"
        ;;
    
    list)
        list_backups
        ;;
    
    restore)
        if [ -z "${2:-}" ]; then
            log_error "Please specify backup file"
            echo "Usage: $0 restore <backup_file>"
            echo ""
            echo "Available backups:"
            ls "$BACKUP_DIR"/*.sql.gz 2>/dev/null || echo "No backups found"
            exit 1
        fi
        restore_database "$2"
        ;;
    
    cleanup)
        cleanup_old_backups
        ;;
    
    *)
        echo "Usage: $0 {full|incremental|files|list|restore|cleanup}"
        echo ""
        echo "  full        - Full backup (database + files)"
        echo "  incremental - Database backup only"
        echo "  files       - File backup only"
        echo "  list        - List available backups"
        echo "  restore     - Restore from backup"
        echo "  cleanup     - Remove old backups"
        exit 1
        ;;
esac
