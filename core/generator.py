import json
from typing import Dict, Optional
from .claude import ClaudeClient
from prompts.system_prompts import (
    ANALYSIS_SYSTEM, ANALYSIS_USER,
    EMAIL_SYSTEM, EMAIL_USER_APPROACH,
    SUBJECT_VARIANTS,
    FOLLOWUP_SYSTEM, FOLLOWUP_USER,
    METADATA_SYSTEM, METADATA_USER,
    get_style_description
)


class EmailGenerator:
    """Orchestrates multi-stage cold email generation"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.claude = ClaudeClient(api_key)
    
    async def generate_campaign(
        self,
        company_name: str,
        industry: str,
        offer: str,
        style: str = "professional",
        company_size: str = "unknown"
    ) -> Dict:
        """
        Generate complete cold email campaign
        
        Returns full package:
        - Strategic analysis
        - 5 cold emails (different approaches)
        - 3 subject line variants per email
        - 3-email follow-up sequence
        - Strategic metadata & recommendations
        """
        
        # Stage 1: Strategic Analysis
        analysis = await self._analyze_company(
            company_name, industry, offer, company_size
        )
        
        # Stage 2: Generate 5 cold emails with different approaches
        approaches = ["problem_aware", "authority", "curiosity", "social_proof", "direct_value"]
        emails = {}
        
        for approach in approaches:
            email_data = await self._generate_email(
                analysis, approach, style, company_name, offer
            )
            emails[approach] = email_data
        
        # Stage 3: Follow-up sequence (based on best email)
        followups = await self._generate_followups(
            emails["problem_aware"]["email"],
            analysis,
            style
        )
        
        # Stage 4: Strategic metadata
        all_emails_text = self._compile_emails_text(emails)
        metadata = await self._generate_metadata(all_emails_text)
        
        # Compile final package
        return {
            "company": {
                "name": company_name,
                "industry": industry,
                "size": company_size
            },
            "analysis": analysis,
            "cold_emails": emails,
            "followup_sequence": followups,
            "recommendations": metadata,
            "style": style
        }
    
    async def _analyze_company(
        self,
        company_name: str,
        industry: str,
        offer: str,
        company_size: str
    ) -> Dict:
        """Stage 1: Deep strategic analysis"""
        
        user_prompt = ANALYSIS_USER.format(
            company_name=company_name,
            industry=industry,
            company_size=company_size,
            offer=offer
        )
        
        response = await self.claude.generate(
            system_prompt=ANALYSIS_SYSTEM,
            user_prompt=user_prompt,
            max_tokens=2000,
            temperature=0.7
        )
        
        # Clean markdown fences if present
        cleaned_response = response.strip()
        if cleaned_response.startswith("```"):
            # Remove ```json or ``` at start and end
            lines = cleaned_response.split("\n")
            # Remove first line (```json or ```) and last line (```)
            if len(lines) > 2:
                cleaned_response = "\n".join(lines[1:-1])
        
        # Parse JSON response
        try:
            analysis = json.loads(cleaned_response)
        except json.JSONDecodeError:
            # If Claude doesn't return JSON, structure it
            analysis = {"analysis_text": response}
        
        return analysis
    
    async def _generate_email(
        self,
        analysis: Dict,
        approach: str,
        style: str,
        company_name: str,
        offer: str
    ) -> Dict:
        """Stage 2: Generate single email with variants"""
        
        # Generate main email
        style_desc = get_style_description(style)
        email_system = EMAIL_SYSTEM.format(style=style_desc)
        
        email_prompt = EMAIL_USER_APPROACH.format(
            analysis=json.dumps(analysis, indent=2),
            approach=approach,
            style=style
        )
        
        email_response = await self.claude.generate(
            system_prompt=email_system,
            user_prompt=email_prompt,
            max_tokens=1000,
            temperature=0.8
        )
        
        # Parse email (SUBJECT: ... \n\n [body])
        email_parts = self._parse_email(email_response)
        
        # Generate 2 alternative subject lines
        variants_prompt = SUBJECT_VARIANTS.format(
            email=email_response,
            original_approach=approach
        )
        
        variants_response = await self.claude.generate(
            system_prompt=EMAIL_SYSTEM.format(style=style_desc),
            user_prompt=variants_prompt,
            max_tokens=300,
            temperature=0.9
        )
        
        variant_subjects = self._parse_variants(variants_response)
        
        return {
            "approach": approach,
            "subject": email_parts["subject"],
            "subject_variants": variant_subjects,
            "email": email_parts["body"],
            "full_text": email_response
        }
    
    async def _generate_followups(
        self,
        initial_email: str,
        analysis: Dict,
        style: str
    ) -> list:
        """Stage 3: Generate 3-email follow-up sequence"""
        
        followup_prompt = FOLLOWUP_USER.format(
            initial_email=initial_email,
            analysis=json.dumps(analysis, indent=2)
        )
        
        response = await self.claude.generate(
            system_prompt=FOLLOWUP_SYSTEM,
            user_prompt=followup_prompt,
            max_tokens=1500,
            temperature=0.8
        )
        
        # Parse into 3 separate emails
        followups = self._parse_followup_sequence(response)
        
        return followups
    
    async def _generate_metadata(self, all_emails: str) -> Dict:
        """Stage 4: Strategic recommendations"""
        
        metadata_prompt = METADATA_USER.format(emails=all_emails)
        
        response = await self.claude.generate(
            system_prompt=METADATA_SYSTEM,
            user_prompt=metadata_prompt,
            max_tokens=1500,
            temperature=0.7
        )
        
        return {"strategic_recommendations": response}
    
    def _parse_email(self, email_text: str) -> Dict:
        """Parse email into subject and body"""
        lines = email_text.strip().split("\n")
        subject = ""
        body_lines = []
        
        for line in lines:
            if line.startswith("SUBJECT:"):
                subject = line.replace("SUBJECT:", "").strip()
            elif line.strip() and not line.startswith("SUBJECT"):
                body_lines.append(line)
        
        return {
            "subject": subject,
            "body": "\n".join(body_lines).strip()
        }
    
    def _parse_variants(self, variants_text: str) -> list:
        """Parse subject line variants"""
        variants = []
        for line in variants_text.split("\n"):
            if line.startswith("VARIANT_"):
                variant = line.split(":", 1)[1].strip() if ":" in line else ""
                if variant:
                    variants.append(variant)
        return variants
    
    def _parse_followup_sequence(self, followup_text: str) -> list:
        """Parse follow-up sequence into list of emails"""
        # Simple parsing - split by "Email 1", "Email 2", "Email 3"
        followups = []
        current_email = {"day": 0, "subject": "", "body": ""}
        
        lines = followup_text.split("\n")
        for line in lines:
            if "Email 1" in line or "Day 3" in line:
                if current_email["subject"]:
                    followups.append(current_email)
                current_email = {"day": 3, "subject": "", "body": ""}
            elif "Email 2" in line or "Day 5" in line:
                if current_email["subject"]:
                    followups.append(current_email)
                current_email = {"day": 5, "subject": "", "body": ""}
            elif "Email 3" in line or "Day 7" in line:
                if current_email["subject"]:
                    followups.append(current_email)
                current_email = {"day": 7, "subject": "", "body": ""}
            elif line.startswith("SUBJECT:") or line.startswith("Subject:"):
                current_email["subject"] = line.split(":", 1)[1].strip()
            elif line.strip() and not any(x in line for x in ["Email", "BODY:", "Body:"]):
                if current_email["body"]:
                    current_email["body"] += "\n" + line
                else:
                    current_email["body"] = line
        
        if current_email["subject"]:
            followups.append(current_email)
        
        return followups
    
    def _compile_emails_text(self, emails: Dict) -> str:
        """Compile all emails for metadata analysis"""
        text = ""
        for approach, email_data in emails.items():
            text += f"\n\n=== {approach.upper()} APPROACH ===\n"
            text += f"Subject: {email_data['subject']}\n\n"
            text += email_data['email']
        return text