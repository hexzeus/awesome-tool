import os
import sqlite3
from datetime import datetime
from typing import Tuple, Dict
from contextlib import contextmanager

class UsageTracker:
    """Tracks license key usage with SQLite"""
    
    def __init__(self):
        self.db_path = os.path.join(os.path.dirname(__file__), "..", "data", "usage.db")
        self.free_limit = int(os.getenv("FREE_USAGE_LIMIT", "3"))
        self._init_db()
    
    def _init_db(self):
        """Initialize database and create tables"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS usage (
                    license_key TEXT PRIMARY KEY,
                    total_uses INTEGER DEFAULT 0,
                    first_used TIMESTAMP,
                    last_used TIMESTAMP
                )
            """)
            conn.commit()
    
    @contextmanager
    def _get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def check_usage(self, license_key: str) -> Tuple[bool, int, bool]:
        """
        Check if license key can be used
        
        Returns:
            (can_use, current_uses, needs_own_key)
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT total_uses FROM usage WHERE license_key = ?",
                (license_key,)
            )
            row = cursor.fetchone()
            
            if row is None:
                # First time use
                return True, 0, False
            
            current_uses = row["total_uses"]
            
            if current_uses >= self.free_limit:
                # Exceeded free limit - needs own API key
                return False, current_uses, True
            
            return True, current_uses, False
    
    def increment_usage(self, license_key: str):
        """Increment usage count for license key"""
        now = datetime.utcnow().isoformat()
        
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT total_uses FROM usage WHERE license_key = ?",
                (license_key,)
            )
            row = cursor.fetchone()
            
            if row is None:
                # First use
                conn.execute(
                    """INSERT INTO usage (license_key, total_uses, first_used, last_used)
                       VALUES (?, 1, ?, ?)""",
                    (license_key, now, now)
                )
            else:
                # Increment
                conn.execute(
                    """UPDATE usage 
                       SET total_uses = total_uses + 1, last_used = ?
                       WHERE license_key = ?""",
                    (now, license_key)
                )
            
            conn.commit()
    
    def get_usage_stats(self, license_key: str) -> Dict:
        """Get usage statistics for a license key"""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT total_uses, first_used, last_used FROM usage WHERE license_key = ?",
                (license_key,)
            )
            row = cursor.fetchone()
            
            if row is None:
                return {
                    "uses": 0,
                    "limit": self.free_limit,
                    "remaining": self.free_limit,
                    "needs_own_key": False
                }
            
            total_uses = row["total_uses"]
            remaining = max(0, self.free_limit - total_uses)
            
            return {
                "uses": total_uses,
                "limit": self.free_limit,
                "remaining": remaining,
                "needs_own_key": total_uses >= self.free_limit,
                "first_used": row["first_used"],
                "last_used": row["last_used"]
            }