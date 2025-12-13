"""Campaign storage and retrieval with SQLite"""

import sqlite3
import json
import os
from datetime import datetime
from typing import List, Dict, Optional
from contextlib import contextmanager


class CampaignStore:
    """Store and manage user campaigns in SQLite database"""

    def __init__(self):
        self.db_path = os.path.join(os.path.dirname(__file__), "..", "data", "campaigns.db")
        self._init_db()

    def _init_db(self):
        """Initialize campaigns database"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS campaigns (
                    id TEXT PRIMARY KEY,
                    license_key TEXT NOT NULL,
                    company_name TEXT NOT NULL,
                    industry TEXT NOT NULL,
                    campaign_data TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL
                )
            """)

            # Create index for faster lookups
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_license_key
                ON campaigns(license_key)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_created_at
                ON campaigns(license_key, created_at DESC)
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

    def _generate_id(self) -> str:
        """Generate unique campaign ID"""
        import uuid
        return str(uuid.uuid4())

    def save_campaign(
        self,
        license_key: str,
        campaign_data: Dict
    ) -> str:
        """
        Save a campaign to the database

        Args:
            license_key: User's license key
            campaign_data: Complete campaign data dictionary

        Returns:
            campaign_id: Unique ID of saved campaign
        """
        campaign_id = self._generate_id()
        now = datetime.utcnow().isoformat()

        # Extract company info for indexing
        company_name = campaign_data.get('company', {}).get('name', 'Unknown')
        industry = campaign_data.get('company', {}).get('industry', 'Unknown')

        # Store entire campaign as JSON
        campaign_json = json.dumps(campaign_data)

        with self._get_connection() as conn:
            conn.execute(
                """INSERT INTO campaigns
                   (id, license_key, company_name, industry, campaign_data, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (campaign_id, license_key, company_name, industry, campaign_json, now, now)
            )
            conn.commit()

        return campaign_id

    def get_campaign(self, license_key: str, campaign_id: str) -> Optional[Dict]:
        """
        Retrieve a specific campaign

        Args:
            license_key: User's license key (for security)
            campaign_id: Campaign ID to retrieve

        Returns:
            Campaign data dict or None if not found
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """SELECT campaign_data, created_at, updated_at, company_name, industry
                   FROM campaigns
                   WHERE id = ? AND license_key = ?""",
                (campaign_id, license_key)
            )
            row = cursor.fetchone()

            if row is None:
                return None

            campaign_data = json.loads(row['campaign_data'])

            # Add metadata
            campaign_data['_metadata'] = {
                'id': campaign_id,
                'created_at': row['created_at'],
                'updated_at': row['updated_at'],
                'company_name': row['company_name'],
                'industry': row['industry']
            }

            return campaign_data

    def list_campaigns(
        self,
        license_key: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict]:
        """
        List all campaigns for a license key

        Args:
            license_key: User's license key
            limit: Maximum campaigns to return
            offset: Number of campaigns to skip (for pagination)

        Returns:
            List of campaign summaries
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """SELECT id, company_name, industry, created_at, updated_at
                   FROM campaigns
                   WHERE license_key = ?
                   ORDER BY created_at DESC
                   LIMIT ? OFFSET ?""",
                (license_key, limit, offset)
            )

            campaigns = []
            for row in cursor.fetchall():
                campaigns.append({
                    'id': row['id'],
                    'company_name': row['company_name'],
                    'industry': row['industry'],
                    'created_at': row['created_at'],
                    'updated_at': row['updated_at']
                })

            return campaigns

    def delete_campaign(self, license_key: str, campaign_id: str) -> bool:
        """
        Delete a campaign

        Args:
            license_key: User's license key (for security)
            campaign_id: Campaign ID to delete

        Returns:
            True if deleted, False if not found
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM campaigns WHERE id = ? AND license_key = ?",
                (campaign_id, license_key)
            )
            conn.commit()

            return cursor.rowcount > 0

    def count_campaigns(self, license_key: str) -> int:
        """
        Count total campaigns for a license key

        Args:
            license_key: User's license key

        Returns:
            Total number of campaigns
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) as count FROM campaigns WHERE license_key = ?",
                (license_key,)
            )
            row = cursor.fetchone()
            return row['count'] if row else 0

    def update_campaign(
        self,
        license_key: str,
        campaign_id: str,
        campaign_data: Dict
    ) -> bool:
        """
        Update an existing campaign

        Args:
            license_key: User's license key (for security)
            campaign_id: Campaign ID to update
            campaign_data: New campaign data

        Returns:
            True if updated, False if not found
        """
        now = datetime.utcnow().isoformat()

        # Extract company info
        company_name = campaign_data.get('company', {}).get('name', 'Unknown')
        industry = campaign_data.get('company', {}).get('industry', 'Unknown')

        # Store entire campaign as JSON
        campaign_json = json.dumps(campaign_data)

        with self._get_connection() as conn:
            cursor = conn.execute(
                """UPDATE campaigns
                   SET campaign_data = ?, company_name = ?, industry = ?, updated_at = ?
                   WHERE id = ? AND license_key = ?""",
                (campaign_json, company_name, industry, now, campaign_id, license_key)
            )
            conn.commit()

            return cursor.rowcount > 0

    def cleanup_old_campaigns(self, days: int = 90):
        """
        Delete campaigns older than N days (maintenance function)

        Args:
            days: Delete campaigns older than this many days
        """
        from datetime import timedelta
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM campaigns WHERE created_at < ?",
                (cutoff,)
            )
            conn.commit()

            return cursor.rowcount
