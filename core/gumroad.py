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
        print(f"✓ Gumroad initialized with permalink: {self.product_permalink}")
    
    async def verify_license(self, license_key: str) -> Tuple[bool, Optional[str]]:
        """
        Verify license key with Gumroad API
        
        Returns:
            (is_valid, error_message)
        """
        
        if not license_key or len(license_key) < 10:
            return False, "Invalid license key format"
        
        print(f"→ Verifying license: {license_key[:20]}...")
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    self.api_url,
                    data={
                        "product_permalink": self.product_permalink,
                        "license_key": license_key
                    }
                )
                
                print(f"← Gumroad response status: {response.status_code}")
                
                data = response.json()
                print(f"← Gumroad response data: {data}")
                
                if response.status_code == 200 and data.get("success"):
                    # Valid license
                    purchase = data.get("purchase", {})
                    
                    # Check if refunded or chargebacked
                    if purchase.get("refunded"):
                        return False, "License key has been refunded"
                    
                    if purchase.get("chargebacked"):
                        return False, "License key has been chargebacked"
                    
                    print("✓ License valid")
                    return True, None
                
                else:
                    # Invalid license
                    print(f"✗ License invalid: {data.get('message', 'Unknown error')}")
                    return False, f"Invalid license key. {data.get('message', '')} Purchase at https://blazestudiox.gumroad.com/l/coldemailgeneratorpro"
                    
        except httpx.TimeoutException:
            print("✗ Gumroad API timeout")
            return False, "License verification timeout. Please try again"
        except Exception as e:
            print(f"✗ Gumroad API error: {str(e)}")
            return False, f"License verification failed: {str(e)}"