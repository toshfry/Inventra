"""
Automatic SQLite backup utility.
- Called on app open and close.
- Keeps the last 10 backups in data/backups/.
- Backup filename: inventra_YYYYMMDD_HHMMSS.db
"""
import os
import shutil
import glob
from datetime import datetime
from config.settings import DB_PATH, BACKUP_DIR


def _checkpoint_wal() -> None:
    """
    Flush the write-ahead log into the main .db file so a file copy is complete.

    The database runs in WAL mode, which means recent committed changes can live
    in inventra.db-wal and NOT yet be in inventra.db. Without this checkpoint a
    plain file copy could miss the latest data.
    """
    try:
        from database.engine import engine
        with engine.connect() as conn:
            conn.exec_driver_sql("PRAGMA wal_checkpoint(TRUNCATE)")
    except Exception as e:
        print(f"[backup] Warning: WAL checkpoint skipped — {e}")


def create_backup() -> str | None:
    """
    Copy the current database to the backups folder.
    Returns the backup path on success, or None if the DB doesn't exist yet.
    Automatically prunes to keep only the 10 most recent backups.
    """
    if not os.path.exists(DB_PATH):
        return None  # Nothing to back up on first run before DB is created

    os.makedirs(BACKUP_DIR, exist_ok=True)

    # Make sure the .db file holds everything before we copy it.
    _checkpoint_wal()

    timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"inventra_{timestamp}.db")

    try:
        shutil.copy2(DB_PATH, backup_path)
        _prune_backups(keep=10)
        return backup_path
    except Exception as e:
        # Never crash the app over a backup failure
        print(f"[backup] Warning: could not create backup — {e}")
        return None


def _prune_backups(keep: int = 10):
    """Delete oldest backups so only `keep` files remain."""
    pattern = os.path.join(BACKUP_DIR, "inventra_*.db")
    backups = sorted(glob.glob(pattern))          # alphabetical = chronological
    while len(backups) > keep:
        try:
            os.remove(backups.pop(0))
        except OSError:
            pass


def list_backups() -> list[str]:
    """Return all backup file paths, newest first."""
    pattern = os.path.join(BACKUP_DIR, "inventra_*.db")
    return sorted(glob.glob(pattern), reverse=True)


def restore_backup(backup_path: str) -> bool:
    """
    Overwrite the live database with a backup file.

    WAL mode is in use, so we must:
      1. Dispose the SQLAlchemy engine to release open file handles/locks.
      2. Copy the backup over inventra.db.
      3. Delete the stale inventra.db-wal / inventra.db-shm sidecar files.
         If left behind, SQLite would replay the OLD log over the restored
         database on next open and silently undo the restore.

    The app must be restarted afterwards so a fresh engine reads the new file.
    Returns True on success.
    """
    if not os.path.exists(backup_path):
        return False

    # Release the live database connections/locks before overwriting the file.
    try:
        from database.engine import engine
        engine.dispose()
    except Exception as e:
        print(f"[backup] Warning: could not dispose engine before restore — {e}")

    try:
        shutil.copy2(backup_path, DB_PATH)

        # Remove stale WAL/SHM so the restored data is what actually loads.
        for suffix in ("-wal", "-shm"):
            sidecar = DB_PATH + suffix
            if os.path.exists(sidecar):
                try:
                    os.remove(sidecar)
                except OSError as e:
                    print(f"[backup] Warning: could not remove {sidecar} — {e}")
        return True
    except Exception as e:
        print(f"[backup] Restore failed — {e}")
        return False
