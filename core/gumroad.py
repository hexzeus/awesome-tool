import os
import httpx
from typing import Tuple, Optional

class GumroadValidator:
    """Validates Gumroad license keys"""
    
    def __init__(self):
        self.product_permalink = os.getenv("GUMROAD_PRODUCT_PERMALINK")
        if not self.product_permalink:
            raise ValueError("GUMROAD_PRODUCT_PERMALINK not configured")
        
        self.api_url = "https://api.gumroad.com/v2/licenses/verify"
    
    async def verify_license(self, license_key: str) -> Tuple[bool, Optional[str]]:
        """
        Verify license key with Gumroad API
        
        Returns:
            (is_valid, error_message)
        """
        
        if not license_key or len(license_key) < 10:
            return False, "Invalid license key format"
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    self.api_url,
                    data={
                        "product_permalink": self.product_permalink,
                        "license_key": license_key
                    }
                )
                
                data = response.json()
                
                if response.status_code == 200 and data.get("success"):
                    # Valid license
                    purchase = data.get("purchase", {})
                    
                    # Check if refunded or chargebacked
                    if purchase.get("refunded"):
                        return False, "License key has been refunded"
                    
                    if purchase.get("chargebacked"):
                        return False, "License key has been chargebacked"
                    
                    return True, None
                
                else:
                    # Invalid license
                    return False, "Invalid license key. Purchase at https://blazestudiox.gumroad.com/l/coldemailgeneratorpro"
                    
        except httpx.TimeoutException:
            return False, "License verification timeout. Please try again"
        except Exception as e:
            # On error, fail closed (don't allow access)
            return False, f"License verification failed: {str(e)}"