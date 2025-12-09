from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
from dotenv import load_dotenv

from tool_core import generate_output

# Load .env
load_dotenv()

# Load Gumroad-style license keys (replace with DB later if needed)
VALID_KEYS = {
    "GUM-2025-XYZ789": "pro@gmail.com",
    "GUM-TEST-111": "testuser@example.com",
    # Add more as needed
}

app = FastAPI(
    title="ViralPost AI Pro",
    description="Lifetime LinkedIn post generator — $69 one-time",
    version="2.0"
)

# CORS Settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],         # Frontend allowed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()


# -------------------------------
# AUTHENTICATION: License Key
# -------------------------------

def verify_license(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Validate Gumroad-style license keys."""
    key = credentials.credentials
    if key not in VALID_KEYS:
        raise HTTPException(status_code=401, detail="Invalid or expired license key")
    return key


# -------------------------------
# REQUEST MODEL
# -------------------------------

class ToolRequest(BaseModel):
    prompt: str
    style: str = "professional"
    ai_key: str | None = None        # Optional user-supplied key
    model: str = "claude-3-5-sonnet" # Default model


# -------------------------------
# ROUTES
# -------------------------------

@app.get("/")
async def root():
    return {
        "message": "ViralPost AI Pro is LIVE — $69 lifetime access",
        "version": "2.0"
    }


@app.post("/api/generate")
async def generate_post(request: ToolRequest, license_key=Depends(verify_license)):
    """
    Main viral post generator API endpoint.
    """
    try:
        result = generate_output(
            prompt=request.prompt,
            style=request.style,
            user_ai_key=request.ai_key,
            preferred_model=request.model
        )
        return {
            "success": True,
            "result": result,
            "license_valid": True,
            "model": request.model
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    return {"status": "healthy", "uptime": "ok"}
