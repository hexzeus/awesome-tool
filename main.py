from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional
import os
from dotenv import load_dotenv

from core.gumroad import GumroadValidator
from core.usage import UsageTracker
from core.generator import EmailGenerator

# Load environment variables
load_dotenv()

# Verify required env vars
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_KEY:
    raise ValueError("ANTHROPIC_API_KEY not found in environment")

app = FastAPI(
    title="Cold Email Generator API",
    description="Professional cold email generation with strategic intelligence",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
gumroad = GumroadValidator()
usage_tracker = UsageTracker()


# Request models
class GenerateRequest(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=200)
    industry: str = Field(..., min_length=1, max_length=100)
    offer: str = Field(..., min_length=10, max_length=500)
    style: str = Field(default="professional", pattern="^(professional|casual|bold)$")
    company_size: str = Field(default="unknown")
    user_api_key: Optional[str] = None


# Routes
@app.get("/")
async def root():
    """Health check and API info"""
    return {
        "status": "online",
        "service": "Cold Email Generator API",
        "version": "1.0.0"
    }


@app.get("/api/usage")
async def get_usage(authorization: str = Header(...)):
    """Get usage statistics for a license key"""
    
    # Extract license key from Authorization header
    license_key = authorization.replace("Bearer ", "").strip()
    
    if not license_key:
        raise HTTPException(status_code=401, detail="License key required")
    
    # Validate license with Gumroad
    is_valid, error = await gumroad.verify_license(license_key)
    
    if not is_valid:
        raise HTTPException(status_code=401, detail=error)
    
    # Get usage stats
    stats = usage_tracker.get_usage_stats(license_key)
    
    return {
        "success": True,
        "license_valid": True,
        "usage": stats
    }


@app.post("/api/generate")
async def generate_campaign(
    request: GenerateRequest,
    authorization: str = Header(...)
):
    """Generate complete cold email campaign"""
    
    # Extract license key
    license_key = authorization.replace("Bearer ", "").strip()
    
    if not license_key:
        raise HTTPException(
            status_code=401,
            detail="License key required. Purchase at https://blazestudiox.gumroad.com/l/coldemailgeneratorpro"
        )
    
    # Validate license with Gumroad
    is_valid, error = await gumroad.verify_license(license_key)
    
    if not is_valid:
        raise HTTPException(status_code=401, detail=error)
    
    # Check usage limits
    can_use, current_uses, needs_own_key = usage_tracker.check_usage(license_key)
    
    if not can_use and not request.user_api_key:
        raise HTTPException(
            status_code=403,
            detail=f"Free usage limit reached ({current_uses} uses). Please provide your Claude API key to continue."
        )
    
    # Determine which API key to use
    api_key_to_use = request.user_api_key if needs_own_key else None
    
    try:
        # Generate campaign
        generator = EmailGenerator(api_key=api_key_to_use)
        
        result = await generator.generate_campaign(
            company_name=request.company_name,
            industry=request.industry,
            offer=request.offer,
            style=request.style,
            company_size=request.company_size
        )
        
        # Increment usage (only if using our key)
        if not request.user_api_key:
            usage_tracker.increment_usage(license_key)
        
        # Get updated stats
        updated_stats = usage_tracker.get_usage_stats(license_key)
        
        return {
            "success": True,
            "result": result,
            "usage": updated_stats
        }
        
    except ValueError as e:
        # Invalid API key or config error
        raise HTTPException(status_code=400, detail=str(e))
    
    except Exception as e:
        # Generation error
        error_msg = str(e)
        
        # Don't expose internal errors
        if "API key" in error_msg or "authentication" in error_msg.lower():
            raise HTTPException(
                status_code=401,
                detail="Invalid Claude API key. Check your key and try again."
            )
        
        raise HTTPException(
            status_code=500,
            detail=f"Generation failed: {error_msg}"
        )


@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "anthropic_configured": bool(ANTHROPIC_KEY),
        "gumroad_configured": bool(os.getenv("GUMROAD_PRODUCT_ID")),
        "database": "connected"
    }


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Custom error response format"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Catch-all error handler"""
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error. Please try again."
        }
    )