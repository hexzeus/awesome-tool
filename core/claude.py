import os
import httpx
from typing import Optional

class ClaudeClient:
    """Wrapper for Anthropic Claude API"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("Claude API key not provided")
        
        self.base_url = "https://api.anthropic.com/v1/messages"
        self.model = "claude-sonnet-4-20250514"
        self.headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
    
    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4000,
        temperature: float = 0.7
    ) -> str:
        """Generate response from Claude"""
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.base_url,
                    headers=self.headers,
                    json={
                        "model": self.model,
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                        "system": system_prompt,
                        "messages": [
                            {"role": "user", "content": user_prompt}
                        ]
                    }
                )
                
                if response.status_code != 200:
                    error_data = response.json()
                    raise Exception(f"Claude API error: {error_data.get('error', {}).get('message', 'Unknown error')}")
                
                result = response.json()
                return result["content"][0]["text"]
                
        except httpx.TimeoutException:
            raise Exception("Claude API timeout - please try again")
        except Exception as e:
            raise Exception(f"Failed to generate: {str(e)}")