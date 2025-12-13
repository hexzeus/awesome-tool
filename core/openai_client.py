"""OpenAI GPT client for campaign generation"""

import os
import httpx
from typing import Optional


class OpenAIClient:
    """Wrapper for OpenAI GPT API"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key not provided")

        self.base_url = "https://api.openai.com/v1/chat/completions"
        self.model = "gpt-4o"  # Or gpt-4-turbo, gpt-4, gpt-3.5-turbo
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4000,
        temperature: float = 0.7,
        timeout: int = 90
    ) -> str:
        """
        Generate response from OpenAI

        Args:
            system_prompt: System instructions
            user_prompt: User message
            max_tokens: Maximum tokens to generate
            temperature: Creativity level (0-1)
            timeout: Request timeout in seconds

        Returns:
            Generated text response

        Raises:
            Exception: On API errors or timeouts
        """

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    self.base_url,
                    headers=self.headers,
                    json={
                        "model": self.model,
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ]
                    }
                )

                if response.status_code != 200:
                    error_data = response.json()
                    error_message = error_data.get('error', {}).get('message', 'Unknown error')
                    raise Exception(f"OpenAI API error: {error_message}")

                result = response.json()
                return result["choices"][0]["message"]["content"]

        except httpx.TimeoutException:
            raise Exception(f"OpenAI API timeout after {timeout}s - request took too long")
        except httpx.RequestError as e:
            raise Exception(f"Network error connecting to OpenAI API: {str(e)}")
        except KeyError as e:
            raise Exception(f"Unexpected OpenAI API response format: missing {str(e)}")
        except Exception as e:
            if "OpenAI API" in str(e):
                raise
            raise Exception(f"Failed to generate: {str(e)}")
