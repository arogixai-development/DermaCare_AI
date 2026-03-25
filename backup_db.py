"""
Encrypted Database Backup - DermaCare AI
=====================================
Automated daily backup script for encrypted database.
"""
import os
import shutil
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

BACKUP_DIR = Path(__file__).parent.parent / "backups"
RETENTION_DAYS = 7


def backup_database():
    """Create encrypted backup of database."""
    BACKUP_DIR.mkdir(exist_ok=True)
    
    db_path = Path(__file__).parent.parent / "backend" / "database" / "dermacare.db"
    
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return False
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"dermacare_backup_{timestamp}.db"
    backup_path = BACKUP_DIR / backup_name
    
    try:
        shutil.copy2(db_path, backup_path)
        print(f"Backup created: {backup_path}")
        
        cleanup_old_backups()
        
        return True
    except Exception as e:
        print(f"Backup failed: {e}")
        return False


def cleanup_old_backups():
    """Remove backups older than retention period."""
    cutoff = datetime.now() - timedelta(days=RETENTION_DAYS)
    
    for backup in BACKUP_DIR.glob("dermacare_backup_*.db"):
        if backup.stat().st_mtime < cutoff.timestamp():
            backup.unlink()
            print(f"Removed old backup: {backup}")


def restore_backup(backup_name: str):
    """Restore database from backup."""
    backup_path = BACKUP_DIR / backup_name
    
    if not backup_path.exists():
        print(f"Backup not found: {backup_name}")
        return False
    
    db_path = Path(__file__).parent.parent / "backend" / "database" / "dermacare.db"
    
    try:
        shutil.copy2(backup_path, db_path)
        print(f"Restored from: {backup_name}")
        return True
    except Exception as e:
        print(f"Restore failed: {e}")
        return False


def list_backups():
    """List all available backups."""
    backups = list(BACKUP_DIR.glob("dermacare_backup_*.db"))
    backups.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    
    print("\nAvailable Backups:")
    print("-" * 50)
    for b in backups:
        size_kb = b.stat().st_size / 1024
        date = datetime.fromtimestamp(b.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        print(f"  {b.name} ({size_kb:.1f} KB) - {date}")
    print()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "backup":
            backup_database()
        elif cmd == "restore" and len(sys.argv) > 2:
            restore_backup(sys.argv[2])
        elif cmd == "list":
            list_backups()
        else:
            print("Usage: python backup_db.py [backup|restore|list]")
    else:
        backup_database()
