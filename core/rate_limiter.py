"""Rate limiter for demo endpoint to prevent API abuse"""

import sqlite3
import os
from datetime import datetime, timedelta
from typing import Tuple
from contextlib import contextmanager


class DemoRateLimiter:
    """Rate limit demo requests by IP address"""

    def __init__(self, max_demos: int = 3, window_hours: int = 24):
        """
        Initialize rate limiter

        Args:
            max_demos: Maximum demos allowed per IP in time window
            window_hours: Time window in hours (default 24)
        """
        self.max_demos = max_demos
        self.window_hours = window_hours
        self.db_path = os.path.join(os.path.dirname(__file__), "..", "data", "rate_limits.db")
        self._init_db()

    def _init_db(self):
        """Initialize rate limit database"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS demo_limits (
                    ip_address TEXT PRIMARY KEY,
                    demo_count INTEGER DEFAULT 0,
                    window_start TIMESTAMP,
                    last_request TIMESTAMP
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

    def check_rate_limit(self, ip_address: str) -> Tuple[bool, int, int]:
        """
        Check if IP has exceeded rate limit

        Args:
            ip_address: Client IP address

        Returns:
            (is_allowed, current_count, remaining_demos)
        """
        now = datetime.utcnow()
        window_start = now - timedelta(hours=self.window_hours)

        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT demo_count, window_start FROM demo_limits WHERE ip_address = ?",
                (ip_address,)
            )
            row = cursor.fetchone()

            if row is None:
                # First request from this IP
                return True, 0, self.max_demos

            db_window_start = datetime.fromisoformat(row["window_start"])
            demo_count = row["demo_count"]

            # Check if window has expired
            if db_window_start < window_start:
                # Window expired, reset counter
                return True, 0, self.max_demos

            # Within current window
            if demo_count >= self.max_demos:
                return False, demo_count, 0

            remaining = self.max_demos - demo_count
            return True, demo_count, remaining

    def record_request(self, ip_address: str):
        """Record a demo request for rate limiting"""
        now = datetime.utcnow()
        window_start = now - timedelta(hours=self.window_hours)

        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT demo_count, window_start FROM demo_limits WHERE ip_address = ?",
                (ip_address,)
            )
            row = cursor.fetchone()

            if row is None:
                # First request
                conn.execute(
                    """INSERT INTO demo_limits (ip_address, demo_count, window_start, last_request)
                       VALUES (?, 1, ?, ?)""",
                    (ip_address, now.isoformat(), now.isoformat())
                )
            else:
                db_window_start = datetime.fromisoformat(row["window_start"])

                if db_window_start < window_start:
                    # Window expired, reset
                    conn.execute(
                        """UPDATE demo_limits
                           SET demo_count = 1, window_start = ?, last_request = ?
                           WHERE ip_address = ?""",
                        (now.isoformat(), now.isoformat(), ip_address)
                    )
                else:
                    # Increment counter
                    conn.execute(
                        """UPDATE demo_limits
                           SET demo_count = demo_count + 1, last_request = ?
                           WHERE ip_address = ?""",
                        (now.isoformat(), ip_address)
                    )

            conn.commit()

    def get_time_until_reset(self, ip_address: str) -> int:
        """
        Get seconds until rate limit resets for IP

        Returns:
            Seconds until reset, or 0 if already reset
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT window_start FROM demo_limits WHERE ip_address = ?",
                (ip_address,)
            )
            row = cursor.fetchone()

            if row is None:
                return 0

            window_start = datetime.fromisoformat(row["window_start"])
            window_end = window_start + timedelta(hours=self.window_hours)
            now = datetime.utcnow()

            if now >= window_end:
                return 0

            return int((window_end - now).total_seconds())

    def cleanup_old_records(self, days: int = 7):
        """Remove rate limit records older than N days"""
        cutoff = datetime.utcnow() - timedelta(days=days)

        with self._get_connection() as conn:
            conn.execute(
                "DELETE FROM demo_limits WHERE last_request < ?",
                (cutoff.isoformat(),)
            )
            conn.commit()
