import os
import httpx
from typing import Tuple, Optional

class GumroadValidator:
    """Validates Gumroad license keys across all tier products"""

    def __init__(self):
        # Get all product IDs for all tiers
        self.product_ids = []

        # Add all tier product IDs
        tier_ids = [
            ("Starter", os.getenv("GUMROAD_PRODUCT_ID_STARTER")),
            ("Pro", os.getenv("GUMROAD_PRODUCT_ID_PRO")),
            ("Unlimited", os.getenv("GUMROAD_PRODUCT_ID_UNLIMITED")),
            ("Agency", os.getenv("GUMROAD_PRODUCT_ID_AGENCY")),
            ("Legacy Pro", os.getenv("GUMROAD_PRODUCT_ID"))  # Old product ID for backwards compatibility
        ]

        for tier_name, product_id in tier_ids:
            if product_id:
                self.product_ids.append((tier_name, product_id))

        if not self.product_ids:
            raise ValueError("No GUMROAD_PRODUCT_ID configured. Set at least one tier product ID.")

        self.api_url = "https://api.gumroad.com/v2/licenses/verify"
        print(f"✓ Gumroad initialized with {len(self.product_ids)} product tiers")

    async def verify_license(self, license_key: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Verify license key with Gumroad API across ALL tier products

        Returns:
            (is_valid, error_message, product_id)
        """

        if not license_key or len(license_key) < 10:
            return False, "Invalid license key format", None

        print(f"→ Verifying license: {license_key[:20]}... across {len(self.product_ids)} tiers")

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                # Try each product ID until we find a match
                for tier_name, product_id in self.product_ids:
                    response = await client.post(
                        self.api_url,
                        data={
                            "product_id": product_id,
                            "license_key": license_key
                        }
                    )

                    data = response.json()

                    if response.status_code == 200 and data.get("success"):
                        # Valid license found!
                        purchase = data.get("purchase", {})

                        # Check if refunded or chargebacked
                        if purchase.get("refunded"):
                            return False, "License key has been refunded", None

                        if purchase.get("chargebacked"):
                            return False, "License key has been chargebacked", None

                        print(f"✓ License valid for tier: {tier_name} (product_id: {product_id})")
                        return True, None, product_id

                # No match found across any tier
                print(f"✗ License invalid: Not found in any tier product")
                return False, f"Invalid license key. Purchase at https://blazestudiox.gumroad.com/l/starter", None

        except httpx.TimeoutException:
            print("✗ Gumroad API timeout")
            return False, "License verification timeout. Please try again", None
        except Exception as e:
            print(f"✗ Gumroad API error: {str(e)}")
            return False, f"License verification failed: {str(e)}", None