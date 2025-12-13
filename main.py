from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional
import os
from dotenv import load_dotenv

from core.gumroad import GumroadValidator
from core.usage import UsageTracker
from core.generator import EmailGenerator
from core.exporter import CampaignExporter
from core.rate_limiter import DemoRateLimiter
from core.campaign_store import CampaignStore
from core.tier_manager import TierManager

# Load environment variables
load_dotenv()

# Verify required env vars
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_KEY:
    raise ValueError("ANTHROPIC_API_KEY not found in environment")

app = FastAPI(
    title="Cold Email Generator API",
    description="Professional cold email generation with strategic intelligence",
    version="2.0.0"
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
exporter = CampaignExporter()
demo_limiter = DemoRateLimiter(max_demos=3, window_hours=24)  # 3 demos per 24 hours
campaign_store = CampaignStore()
tier_manager = TierManager()


# Request models
class GenerateRequest(BaseModel):
    company_name: str = Field(default="", max_length=200)
    industry: str = Field(default="", max_length=100)
    offer: str = Field(default="", max_length=500)
    style: str = Field(default="professional", pattern="^(professional|casual|bold)$")
    company_size: str = Field(default="unknown")
    user_api_key: Optional[str] = None
    model_provider: str = Field(default="claude", pattern="^(claude|openai)$")


class DemoRequest(BaseModel):
    company_name: str = Field(default="", max_length=200)
    industry: str = Field(default="", max_length=100)
    offer: str = Field(default="", max_length=500)
    style: str = Field(default="professional", pattern="^(professional|casual|bold)$")


class ExportRequest(BaseModel):
    campaign_data: dict
    format: str = Field(..., pattern="^(docx|pdf)$")


# Routes
@app.get("/")
async def root():
    """Health check and API info"""
    return {
        "status": "online",
        "service": "Cold Email Generator API",
        "version": "2.0.0",
        "features": ["demo", "export_docx", "export_pdf"]
    }


@app.post("/api/demo")
async def generate_demo(demo_request: DemoRequest, request: Request):
    """
    Generate DEMO campaign (single email, no license required)
    Rate limited to 3 demos per IP per 24 hours
    """

    # Get client IP
    client_ip = request.client.host

    # Check rate limit
    is_allowed, current_count, remaining = demo_limiter.check_rate_limit(client_ip)

    if not is_allowed:
        seconds_until_reset = demo_limiter.get_time_until_reset(client_ip)
        hours_until_reset = seconds_until_reset / 3600

        raise HTTPException(
            status_code=429,
            detail=f"Demo limit reached ({current_count}/{demo_limiter.max_demos}). Try again in {hours_until_reset:.1f} hours or purchase full access at https://blazestudiox.gumroad.com/l/coldemailgeneratorpro"
        )

    try:
        # Use user input if provided, otherwise use defaults
        company_name = demo_request.company_name.strip() if demo_request.company_name and demo_request.company_name.strip() else "TechCorp Solutions"
        industry = demo_request.industry.strip() if demo_request.industry and demo_request.industry.strip() else "SaaS"
        offer = demo_request.offer.strip() if demo_request.offer and demo_request.offer.strip() else "We help SaaS companies automate their customer onboarding with AI-powered workflows that reduce time-to-value by 50%"
        
        # Generate limited demo using our API key
        generator = EmailGenerator(api_key=None)
        
        # Generate analysis only
        print("Demo: Generating analysis...")
        analysis = await generator._analyze_company(
            company_name=company_name,
            industry=industry,
            offer=offer,
            company_size="unknown"
        )
        
        # Generate ONE email (problem_aware approach)
        print("Demo: Generating single email...")
        demo_email = await generator._generate_email_with_variants(
            analysis=analysis,
            approach="problem_aware",
            style=demo_request.style,
            company_name=company_name,
            offer=offer
        )

        # Record successful demo request for rate limiting
        demo_limiter.record_request(client_ip)
        
        # Return demo result with watermark
        return {
            "success": True,
            "demo": True,
            "message": "🎉 This is a DEMO result. Purchase for 5 complete emails + follow-ups + strategic recommendations.",
            "result": {
                "company": {
                    "name": company_name,
                    "industry": industry,
                    "size": "unknown"
                },
                "analysis": {
                    "strategic_brief": {
                        "top_3_pain_points": analysis.get('strategic_brief', {}).get('top_3_pain_points', [])[:2],
                        "note": "⚡ Full analysis with objections, value props, and hooks available in paid version"
                    }
                },
                "demo_email": {
                    "approach": demo_email["approach"],
                    "subject": demo_email["subject"],
                    "email": demo_email["email"],
                    "note": "⚡ DEMO - Purchase to unlock 4 more email approaches + variants"
                },
                "locked_features": {
                    "additional_emails": "🔒 4 more email approaches (authority, curiosity, social_proof, direct_value)",
                    "followup_sequence": "🔒 3-email follow-up sequence",
                    "recommendations": "🔒 Strategic recommendations & optimization tactics",
                    "exports": "🔒 Export as .docx and .pdf"
                }
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Demo generation failed: {str(e)}"
        )


@app.get("/api/usage")
async def get_usage(authorization: str = Header(...)):
    """Get usage statistics and tier information for a license key"""

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

    # Get tier information
    tier_info = tier_manager.get_tier_info(license_key)

    # Check tier-based limits
    current_uses = stats.get('uses', 0)
    can_use, tier_limit, tier_name = tier_manager.check_tier_limits(license_key, current_uses)

    return {
        "success": True,
        "license_valid": True,
        "usage": stats,
        "tier": tier_info,
        "tier_limit_reached": not can_use,
        "available_upgrades": tier_manager.get_upgrade_path(tier_name) if not can_use else []
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
    
    # Validate form data thoroughly
    if not request.company_name or len(request.company_name.strip()) < 2:
        raise HTTPException(
            status_code=422,
            detail="Company name is required (minimum 2 characters)"
        )
    
    if not request.industry or len(request.industry.strip()) < 2:
        raise HTTPException(
            status_code=422,
            detail="Industry is required (minimum 2 characters)"
        )
    
    if not request.offer or len(request.offer.strip()) < 10:
        raise HTTPException(
            status_code=422,
            detail="Offer description is required (minimum 10 characters)"
        )
    
    # Check tier limits first
    current_uses = usage_tracker.get_usage_stats(license_key).get('uses', 0)
    can_use_tier, tier_limit, tier_name = tier_manager.check_tier_limits(license_key, current_uses)

    if not can_use_tier:
        tier_info = tier_manager.get_tier_info(license_key)

        if tier_info.get('is_expired'):
            raise HTTPException(
                status_code=403,
                detail=f"Your {tier_info['name']} tier has expired. Please renew or upgrade at https://blazestudiox.gumroad.com/l/coldemailgeneratorpro"
            )

        if tier_limit > 0:  # Not unlimited
            upgrades = tier_manager.get_upgrade_path(tier_name)
            upgrade_msg = ""
            if upgrades:
                next_tier = upgrades[0]
                upgrade_msg = f" Upgrade to {next_tier['name']} for ${next_tier['price']} to continue."

            raise HTTPException(
                status_code=403,
                detail=f"Tier limit reached ({current_uses}/{tier_limit} campaigns).{upgrade_msg}"
            )

    # Legacy check: also check old usage limits (backwards compatibility)
    can_use_legacy, legacy_uses, needs_own_key = usage_tracker.check_usage(license_key)

    if not can_use_legacy and not request.user_api_key:
        raise HTTPException(
            status_code=403,
            detail=f"Free usage limit reached ({legacy_uses} uses). Please provide your Claude API key to continue."
        )

    # Determine which API key to use (prioritize tier-based limits)
    api_key_to_use = request.user_api_key if needs_own_key else None
    
    try:
        # Generate campaign with selected model provider
        generator = EmailGenerator(
            api_key=api_key_to_use,
            model_provider=request.model_provider
        )
        
        result = await generator.generate_campaign(
            company_name=request.company_name.strip(),
            industry=request.industry.strip(),
            offer=request.offer.strip(),
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


@app.post("/api/export")
async def export_campaign(
    request: ExportRequest,
    authorization: str = Header(...)
):
    """
    Export campaign to .docx or .pdf
    """
    
    # Extract license key
    license_key = authorization.replace("Bearer ", "").strip()
    
    if not license_key:
        raise HTTPException(status_code=401, detail="License key required")
    
    # Validate license
    is_valid, error = await gumroad.verify_license(license_key)
    
    if not is_valid:
        raise HTTPException(status_code=401, detail=error)
    
    try:
        campaign_data = request.campaign_data
        export_format = request.format
        
        if export_format == "docx":
            buffer = exporter.export_to_docx(campaign_data)
            filename = f"campaign_{campaign_data.get('company', {}).get('name', 'export').replace(' ', '_')}.docx"
            media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        
        elif export_format == "pdf":
            buffer = exporter.export_to_pdf(campaign_data)
            filename = f"campaign_{campaign_data.get('company', {}).get('name', 'export').replace(' ', '_')}.pdf"
            media_type = "application/pdf"
        
        else:
            raise HTTPException(status_code=400, detail="Invalid format. Use 'docx' or 'pdf'")
        
        return StreamingResponse(
            buffer,
            media_type=media_type,
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Export failed: {str(e)}"
        )


@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "anthropic_configured": bool(ANTHROPIC_KEY),
        "gumroad_configured": bool(os.getenv("GUMROAD_PRODUCT_ID")),
        "database": "connected",
        "version": "2.0.0"
    }


# Campaign Management Endpoints

@app.post("/api/campaigns")
async def save_campaign(
    request: dict,
    authorization: str = Header(...)
):
    """
    Save a campaign to database

    Request body:
    {
        "campaign_data": {...}  // Complete campaign object
    }
    """

    # Extract license key
    license_key = authorization.replace("Bearer ", "").strip()

    if not license_key:
        raise HTTPException(status_code=401, detail="License key required")

    # Validate license
    is_valid, error = await gumroad.verify_license(license_key)

    if not is_valid:
        raise HTTPException(status_code=401, detail=error)

    try:
        campaign_data = request.get('campaign_data')

        if not campaign_data:
            raise HTTPException(status_code=400, detail="campaign_data is required")

        # Save to database
        campaign_id = campaign_store.save_campaign(license_key, campaign_data)

        return {
            "success": True,
            "campaign_id": campaign_id,
            "message": "Campaign saved successfully"
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save campaign: {str(e)}"
        )


@app.get("/api/campaigns")
async def list_campaigns(
    authorization: str = Header(...),
    limit: int = 50,
    offset: int = 0
):
    """
    List all campaigns for the authenticated user

    Query params:
    - limit: Max campaigns to return (default 50)
    - offset: Number to skip for pagination (default 0)
    """

    # Extract license key
    license_key = authorization.replace("Bearer ", "").strip()

    if not license_key:
        raise HTTPException(status_code=401, detail="License key required")

    # Validate license
    is_valid, error = await gumroad.verify_license(license_key)

    if not is_valid:
        raise HTTPException(status_code=401, detail=error)

    try:
        campaigns = campaign_store.list_campaigns(license_key, limit=limit, offset=offset)
        total_count = campaign_store.count_campaigns(license_key)

        return {
            "success": True,
            "campaigns": campaigns,
            "total": total_count,
            "limit": limit,
            "offset": offset
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list campaigns: {str(e)}"
        )


@app.get("/api/campaigns/{campaign_id}")
async def get_campaign(
    campaign_id: str,
    authorization: str = Header(...)
):
    """Get a specific campaign by ID"""

    # Extract license key
    license_key = authorization.replace("Bearer ", "").strip()

    if not license_key:
        raise HTTPException(status_code=401, detail="License key required")

    # Validate license
    is_valid, error = await gumroad.verify_license(license_key)

    if not is_valid:
        raise HTTPException(status_code=401, detail=error)

    try:
        campaign = campaign_store.get_campaign(license_key, campaign_id)

        if campaign is None:
            raise HTTPException(status_code=404, detail="Campaign not found")

        return {
            "success": True,
            "campaign": campaign
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve campaign: {str(e)}"
        )


@app.delete("/api/campaigns/{campaign_id}")
async def delete_campaign(
    campaign_id: str,
    authorization: str = Header(...)
):
    """Delete a campaign"""

    # Extract license key
    license_key = authorization.replace("Bearer ", "").strip()

    if not license_key:
        raise HTTPException(status_code=401, detail="License key required")

    # Validate license
    is_valid, error = await gumroad.verify_license(license_key)

    if not is_valid:
        raise HTTPException(status_code=401, detail=error)

    try:
        deleted = campaign_store.delete_campaign(license_key, campaign_id)

        if not deleted:
            raise HTTPException(status_code=404, detail="Campaign not found")

        return {
            "success": True,
            "message": "Campaign deleted successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete campaign: {str(e)}"
        )


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