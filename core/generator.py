import json
import asyncio
from typing import Dict, Optional, List
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
    """Orchestrates multi-stage cold email generation with parallel execution"""
    
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
        Generate complete cold email campaign with optimized parallel execution
        
        Performance: ~60-90 seconds (was 180-195s)
        - Stage 1: Analysis (15s)
        - Stage 2: 5 emails + variants in parallel (30s)
        - Stage 3: Followups + Metadata in parallel (20s)
        """
        
        # Stage 1: Strategic Analysis (must run first)
        print("Stage 1: Analyzing company...")
        analysis = await self._analyze_company(
            company_name, industry, offer, company_size
        )
        
        # Stage 2: Generate 5 emails with variants IN PARALLEL
        print("Stage 2: Generating 5 emails in parallel...")
        approaches = ["problem_aware", "authority", "curiosity", "social_proof", "direct_value"]
        
        # Run all email generations in parallel
        email_tasks = [
            self._generate_email_with_variants(
                analysis, approach, style, company_name, offer
            )
            for approach in approaches
        ]
        
        email_results = await asyncio.gather(*email_tasks)
        emails = {approach: email_data for approach, email_data in zip(approaches, email_results)}
        
        # Stage 3: Follow-ups and Metadata IN PARALLEL
        print("Stage 3: Generating followups and metadata in parallel...")
        followups_task = self._generate_followups(
            emails["problem_aware"]["email"],
            analysis,
            style
        )
        
        all_emails_text = self._compile_emails_text(emails)
        metadata_task = self._generate_metadata(all_emails_text)
        
        # Run in parallel
        followups, metadata = await asyncio.gather(followups_task, metadata_task)
        
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
        """Stage 1: Deep strategic analysis with strict JSON output"""
        
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
        
        # Aggressive JSON cleaning
        cleaned_response = response.strip()
        
        # Remove markdown fences
        if cleaned_response.startswith("```"):
            lines = cleaned_response.split("\n")
            if len(lines) > 2:
                cleaned_response = "\n".join(lines[1:-1]).strip()
        
        # Try parsing
        try:
            analysis = json.loads(cleaned_response)
            
            # Ensure strategic_brief exists with proper structure
            if "strategic_brief" not in analysis:
                print("Warning: No strategic_brief in response, creating default structure")
                analysis = {
                    "strategic_brief": {
                        "top_3_pain_points": [],
                        "key_objections": [],
                        "resonant_value_propositions": [],
                        "approach_strategy": {},
                        "hooks_and_pattern_interrupts": []
                    },
                    "raw_analysis": cleaned_response
                }
            
            return analysis
            
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            print(f"Response preview: {cleaned_response[:200]}")
            
            # Fallback: Create structured response from text
            return {
                "strategic_brief": {
                    "top_3_pain_points": [
                        {
                            "pain_point": "Unable to parse strategic analysis",
                            "description": "The AI response could not be parsed. Using fallback structure.",
                            "urgency": "medium"
                        }
                    ],
                    "key_objections": [],
                    "resonant_value_propositions": [],
                    "approach_strategy": {},
                    "hooks_and_pattern_interrupts": []
                },
                "raw_analysis": cleaned_response,
                "analysis_text": cleaned_response
            }
    
    async def _generate_email_with_variants(
        self,
        analysis: Dict,
        approach: str,
        style: str,
        company_name: str,
        offer: str
    ) -> Dict:
        """
        Stage 2: Generate email AND variants in SINGLE optimized call
        
        Instead of 2 API calls (email + variants), we do 1 call
        by prompting for variants in the initial request
        """
        
        style_desc = get_style_description(style)
        email_system = EMAIL_SYSTEM.format(style=style_desc)
        
        # Enhanced prompt that requests variants in same response
        email_prompt = f"""{EMAIL_USER_APPROACH.format(
            analysis=json.dumps(analysis.get('strategic_brief', analysis), indent=2),
            approach=approach,
            style=style
        )}

After the email, also provide 2 alternative subject lines:
VARIANT_1: [alternative subject line]
VARIANT_2: [alternative subject line]"""
        
        response = await self.claude.generate(
            system_prompt=email_system,
            user_prompt=email_prompt,
            max_tokens=1200,
            temperature=0.8
        )
        
        # Parse email and variants from single response
        email_parts = self._parse_email_with_variants(response)
        
        return {
            "approach": approach,
            "subject": email_parts["subject"],
            "subject_variants": email_parts["variants"],
            "email": email_parts["body"],
            "full_text": response
        }
    
    async def _generate_followups(
        self,
        initial_email: str,
        analysis: Dict,
        style: str
    ) -> List[Dict]:
        """Stage 3: Generate 3-email follow-up sequence"""
        
        followup_prompt = FOLLOWUP_USER.format(
            initial_email=initial_email,
            analysis=json.dumps(analysis.get('strategic_brief', analysis), indent=2)
        )
        
        response = await self.claude.generate(
            system_prompt=FOLLOWUP_SYSTEM,
            user_prompt=followup_prompt,
            max_tokens=1500,
            temperature=0.8
        )
        
        followups = self._parse_followup_sequence(response)
        
        # Ensure we have 3 followups
        if len(followups) < 3:
            print(f"Warning: Only got {len(followups)} followups, expected 3")
            # Add placeholder if missing
            while len(followups) < 3:
                day = [3, 5, 7][len(followups)]
                followups.append({
                    "day": day,
                    "subject": "Following up",
                    "body": "Quick follow-up on my previous email..."
                })
        
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
    
    def _parse_email_with_variants(self, email_text: str) -> Dict:
        """Parse email with subject variants from single response"""
        lines = email_text.strip().split("\n")
        subject = ""
        body_lines = []
        variants = []
        in_body = False
        
        for line in lines:
            if line.startswith("SUBJECT:"):
                subject = line.replace("SUBJECT:", "").strip()
                in_body = True
            elif line.startswith("VARIANT_"):
                # Extract variant
                variant = line.split(":", 1)[1].strip() if ":" in line else ""
                if variant:
                    variants.append(variant)
                in_body = False
            elif in_body and line.strip() and not line.startswith("VARIANT"):
                body_lines.append(line)
        
        return {
            "subject": subject or "Your meeting request",
            "body": "\n".join(body_lines).strip() or email_text,
            "variants": variants
        }
    
    def _parse_email(self, email_text: str) -> Dict:
        """Parse email into subject and body (legacy method)"""
        lines = email_text.strip().split("\n")
        subject = ""
        body_lines = []
        
        for line in lines:
            if line.startswith("SUBJECT:"):
                subject = line.replace("SUBJECT:", "").strip()
            elif line.strip() and not line.startswith("SUBJECT"):
                body_lines.append(line)
        
        return {
            "subject": subject or "Quick question",
            "body": "\n".join(body_lines).strip() or email_text
        }
    
    def _parse_variants(self, variants_text: str) -> List[str]:
        """Parse subject line variants (legacy method)"""
        variants = []
        for line in variants_text.split("\n"):
            if line.startswith("VARIANT_"):
                variant = line.split(":", 1)[1].strip() if ":" in line else ""
                if variant:
                    variants.append(variant)
        return variants
    
    def _parse_followup_sequence(self, followup_text: str) -> List[Dict]:
        """Parse follow-up sequence into list of emails"""
        followups = []
        current_email = {"day": 0, "subject": "", "body": ""}
        body_started = False
        
        lines = followup_text.split("\n")
        for line in lines:
            line_lower = line.lower()
            
            # Detect new email
            if "email 1" in line_lower or "day 3" in line_lower:
                if current_email["subject"] and body_started:
                    followups.append(current_email)
                current_email = {"day": 3, "subject": "", "body": ""}
                body_started = False
            elif "email 2" in line_lower or "day 5" in line_lower:
                if current_email["subject"] and body_started:
                    followups.append(current_email)
                current_email = {"day": 5, "subject": "", "body": ""}
                body_started = False
            elif "email 3" in line_lower or "day 7" in line_lower:
                if current_email["subject"] and body_started:
                    followups.append(current_email)
                current_email = {"day": 7, "subject": "", "body": ""}
                body_started = False
            elif line.startswith("SUBJECT:") or line.startswith("Subject:"):
                current_email["subject"] = line.split(":", 1)[1].strip()
                body_started = True
            elif body_started and line.strip() and not any(x in line for x in ["Email", "BODY:", "Body:", "---", "==="]):
                if current_email["body"]:
                    current_email["body"] += "\n" + line
                else:
                    current_email["body"] = line
        
        # Add last email
        if current_email["subject"] and body_started:
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