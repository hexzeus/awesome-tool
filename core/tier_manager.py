"""Tiered pricing and feature management"""

import os
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional
from contextlib import contextmanager


class TierManager:
    """Manage tier-based limits and features"""

    # Tier definitions
    TIERS = {
        'starter': {
            'name': 'Starter',
            'price': 29,
            'limit': 10,
            'days_valid': 7,
            'campaign_save_limit': 3,
            'features': ['basic_export']
        },
        'professional': {
            'name': 'Professional',
            'price': 49,
            'limit': 50,
            'days_valid': 30,
            'campaign_save_limit': 10,
            'features': ['basic_export', 'campaign_history']
        },
        'unlimited': {
            'name': 'Unlimited',
            'price': 99,
            'limit': -1,  # -1 means unlimited
            'days_valid': 90,
            'campaign_save_limit': -1,  # Unlimited
            'features': ['basic_export', 'campaign_history', 'priority_support', 'early_access']
        },
        'agency': {
            'name': 'Agency',
            'price': 199,
            'limit': -1,  # Unlimited
            'days_valid': -1,  # Lifetime
            'campaign_save_limit': -1,  # Unlimited
            'features': ['basic_export', 'campaign_history', 'priority_support', 'early_access', 'white_label', 'api_access']
        }
    }

    # Gumroad product ID mapping (you'll need to update these with your actual product IDs)
    PRODUCT_ID_MAP = {
        os.getenv("GUMROAD_PRODUCT_ID_STARTER", "starter_product_id"): 'starter',
        os.getenv("GUMROAD_PRODUCT_ID_PRO", "TEkWoFBy5TwWJJTpwbjQVA=="): 'professional',  # Current product
        os.getenv("GUMROAD_PRODUCT_ID_UNLIMITED", "unlimited_product_id"): 'unlimited',
        os.getenv("GUMROAD_PRODUCT_ID_AGENCY", "agency_product_id"): 'agency',
    }

    def __init__(self):
        self.db_path = os.path.join(os.path.dirname(__file__), "..", "data", "tiers.db")
        self._init_db()

    def _init_db(self):
        """Initialize tiers database"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_tiers (
                    license_key TEXT PRIMARY KEY,
                    tier TEXT NOT NULL,
                    purchased_at TIMESTAMP NOT NULL,
                    expires_at TIMESTAMP,
                    product_id TEXT
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

    def get_tier_from_product_id(self, product_id: str) -> str:
        """
        Map Gumroad product ID to tier

        Args:
            product_id: Gumroad product identifier

        Returns:
            Tier name (defaults to 'professional' if not found)
        """
        return self.PRODUCT_ID_MAP.get(product_id, 'professional')

    def register_license(
        self,
        license_key: str,
        product_id: str
    ):
        """
        Register a new license with tier information

        Args:
            license_key: User's license key
            product_id: Gumroad product ID
        """
        tier = self.get_tier_from_product_id(product_id)
        tier_config = self.TIERS[tier]

        now = datetime.utcnow()
        purchased_at = now.isoformat()

        # Calculate expiration
        if tier_config['days_valid'] == -1:
            expires_at = None  # Lifetime
        else:
            expires_at = (now + timedelta(days=tier_config['days_valid'])).isoformat()

        with self._get_connection() as conn:
            # Check if already exists
            cursor = conn.execute(
                "SELECT tier FROM user_tiers WHERE license_key = ?",
                (license_key,)
            )
            existing = cursor.fetchone()

            if existing:
                # Update existing (in case of upgrade)
                conn.execute(
                    """UPDATE user_tiers
                       SET tier = ?, expires_at = ?, product_id = ?
                       WHERE license_key = ?""",
                    (tier, expires_at, product_id, license_key)
                )
            else:
                # Insert new
                conn.execute(
                    """INSERT INTO user_tiers
                       (license_key, tier, purchased_at, expires_at, product_id)
                       VALUES (?, ?, ?, ?, ?)""",
                    (license_key, tier, purchased_at, expires_at, product_id)
                )

            conn.commit()

    def get_tier(self, license_key: str) -> str:
        """
        Get tier for a license key

        Args:
            license_key: User's license key

        Returns:
            Tier name (defaults to 'professional' for legacy users)
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT tier, expires_at FROM user_tiers WHERE license_key = ?",
                (license_key,)
            )
            row = cursor.fetchone()

            if row is None:
                # Legacy user - default to professional
                return 'professional'

            # Check if expired
            if row['expires_at']:
                expires_at = datetime.fromisoformat(row['expires_at'])
                if datetime.utcnow() > expires_at:
                    return 'expired'

            return row['tier']

    def get_tier_config(self, tier: str) -> Dict:
        """Get configuration for a tier"""
        return self.TIERS.get(tier, self.TIERS['professional'])

    def check_tier_limits(
        self,
        license_key: str,
        current_usage: int
    ) -> Tuple[bool, int, str]:
        """
        Check if user has exceeded their tier limits

        Args:
            license_key: User's license key
            current_usage: Current usage count

        Returns:
            (can_use, limit, tier_name)
        """
        tier = self.get_tier(license_key)

        if tier == 'expired':
            return False, 0, 'expired'

        tier_config = self.get_tier_config(tier)
        limit = tier_config['limit']

        if limit == -1:
            # Unlimited
            return True, -1, tier

        # Check if under limit
        can_use = current_usage < limit

        return can_use, limit, tier

    def has_feature(self, license_key: str, feature: str) -> bool:
        """
        Check if user's tier has a specific feature

        Args:
            license_key: User's license key
            feature: Feature name to check

        Returns:
            True if user has access to feature
        """
        tier = self.get_tier(license_key)

        if tier == 'expired':
            return False

        tier_config = self.get_tier_config(tier)
        return feature in tier_config.get('features', [])

    def get_campaign_save_limit(self, license_key: str) -> int:
        """
        Get maximum saved campaigns allowed for user's tier

        Returns:
            Number of campaigns (-1 for unlimited)
        """
        tier = self.get_tier(license_key)
        tier_config = self.get_tier_config(tier)
        return tier_config.get('campaign_save_limit', 10)

    def get_tier_info(self, license_key: str) -> Dict:
        """
        Get complete tier information for a user

        Returns:
            Dictionary with tier name, limits, features, expiration
        """
        tier = self.get_tier(license_key)

        if tier == 'expired':
            return {
                'tier': 'expired',
                'name': 'Expired',
                'is_expired': True,
                'message': 'Your subscription has expired. Please renew or upgrade.'
            }

        tier_config = self.get_tier_config(tier)

        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT purchased_at, expires_at FROM user_tiers WHERE license_key = ?",
                (license_key,)
            )
            row = cursor.fetchone()

            if row:
                purchased_at = row['purchased_at']
                expires_at = row['expires_at']
            else:
                # Legacy user
                purchased_at = None
                expires_at = None

        return {
            'tier': tier,
            'name': tier_config['name'],
            'price': tier_config['price'],
            'generation_limit': tier_config['limit'],
            'days_valid': tier_config['days_valid'],
            'campaign_save_limit': tier_config['campaign_save_limit'],
            'features': tier_config['features'],
            'purchased_at': purchased_at,
            'expires_at': expires_at,
            'is_expired': False,
            'is_lifetime': tier_config['days_valid'] == -1,
            'is_unlimited': tier_config['limit'] == -1
        }

    def get_upgrade_path(self, current_tier: str) -> list:
        """
        Get available upgrades from current tier

        Args:
            current_tier: User's current tier

        Returns:
            List of available tier upgrades with pricing
        """
        tier_order = ['starter', 'professional', 'unlimited', 'agency']

        if current_tier not in tier_order:
            return []

        current_index = tier_order.index(current_tier)
        available_upgrades = tier_order[current_index + 1:]

        upgrades = []
        for tier_key in available_upgrades:
            tier_config = self.TIERS[tier_key]
            upgrades.append({
                'tier': tier_key,
                'name': tier_config['name'],
                'price': tier_config['price'],
                'features': tier_config['features'],
                'generation_limit': tier_config['limit'],
                'campaign_save_limit': tier_config['campaign_save_limit']
            })

        return upgrades
