import json
import asyncio
from typing import Dict, Optional, List, Literal
from .claude import ClaudeClient
from .openai_client import OpenAIClient
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

    def __init__(self, api_key: Optional[str] = None, model_provider: Literal["claude", "openai"] = "claude"):
        """
        Initialize email generator

        Args:
            api_key: API key for the chosen provider (optional, will use env var)
            model_provider: Which AI provider to use ("claude" or "openai")
        """
        self.model_provider = model_provider

        if model_provider == "claude":
            self.client = ClaudeClient(api_key)
        elif model_provider == "openai":
            self.client = OpenAIClient(api_key)
        else:
            raise ValueError(f"Invalid model provider: {model_provider}. Must be 'claude' or 'openai'")
    
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

    async def generate_campaign_stream(
        self,
        company_name: str,
        industry: str,
        offer: str,
        style: str = "professional",
        company_size: str = "unknown"
    ):
        """
        Generate campaign with progressive streaming - yields results as each stage completes

        Yields JSON chunks:
        - {"stage": "analysis", "data": {...}}
        - {"stage": "email", "approach": "problem_aware", "data": {...}}
        - {"stage": "followups", "data": [...]}
        - {"stage": "recommendations", "data": {...}}
        - {"stage": "complete", "data": {full_campaign}}
        """

        # Stage 1: Strategic Analysis
        print("Stage 1: Analyzing company...")
        yield {"stage": "started", "message": "Analyzing company and industry..."}

        analysis = await self._analyze_company(
            company_name, industry, offer, company_size
        )

        yield {"stage": "analysis", "data": analysis}

        # Stage 2: Generate 5 emails with variants - STREAM EACH AS IT COMPLETES
        print("Stage 2: Generating 5 emails in parallel...")
        yield {"stage": "started", "message": "Generating email variations..."}

        approaches = ["problem_aware", "authority", "curiosity", "social_proof", "direct_value"]

        # Create all tasks but use as_completed to yield results progressively
        email_tasks = {
            approach: asyncio.create_task(
                self._generate_email_with_variants(
                    analysis, approach, style, company_name, offer
                )
            )
            for approach in approaches
        }

        emails = {}
        for approach in approaches:
            email_data = await email_tasks[approach]
            emails[approach] = email_data
            # Stream this email immediately
            yield {
                "stage": "email",
                "approach": approach,
                "data": email_data
            }

        # Stage 3: Follow-ups and Metadata
        print("Stage 3: Generating followups and metadata...")
        yield {"stage": "started", "message": "Creating follow-up sequence..."}

        followups_task = self._generate_followups(
            emails["problem_aware"]["email"],
            analysis,
            style
        )

        all_emails_text = self._compile_emails_text(emails)
        metadata_task = self._generate_metadata(all_emails_text)

        # Stream followups as soon as ready
        followups, metadata = await asyncio.gather(followups_task, metadata_task)

        yield {"stage": "followups", "data": followups}

        # Stream recommendations
        yield {"stage": "recommendations", "data": metadata}

        # Final complete package
        complete_campaign = {
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

        yield {"stage": "complete", "data": complete_campaign}
    
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
        
        response = await self.client.generate(
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
            data = json.loads(cleaned_response)
            
            # Map keys to match frontend expectations
            # Handle both old format (pain_points) and new format (top_3_pain_points)
            analysis = {
                "strategic_brief": {
                    "top_3_pain_points": data.get("top_3_pain_points", data.get("pain_points", [])),
                    "key_objections": data.get("key_objections", data.get("objections", [])),
                    "resonant_value_propositions": data.get("resonant_value_propositions", data.get("value_props", [])),
                    "approach_strategy": data.get("approach_strategy", {}),
                    "hooks_and_pattern_interrupts": data.get("hooks_and_pattern_interrupts", data.get("hooks", []))
                },
                "raw_analysis": cleaned_response
            }
            
            return analysis
            
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            print(f"Response preview: {cleaned_response[:200]}")
            
            # Fallback: Return raw text for display
            return {
                "strategic_brief": {
                    "top_3_pain_points": [],
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
        
        response = await self.client.generate(
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
        
        response = await self.client.generate(
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
        """Stage 4: Strategic recommendations with full output"""
        
        metadata_prompt = METADATA_USER.format(emails=all_emails)
        
        response = await self.client.generate(
            system_prompt=METADATA_SYSTEM,
            user_prompt=metadata_prompt,
            max_tokens=4000,  # INCREASED from 2500 to prevent cut-off
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
        """Parse follow-up sequence into list of emails with robust pattern matching"""
        followups = []
        current_email = {"day": 0, "subject": "", "body": ""}
        body_started = False

        lines = followup_text.split("\n")
        for i, line in enumerate(lines):
            line_lower = line.lower().strip()
            line_stripped = line.strip()

            # Detect new email - more flexible patterns
            day_detected = None
            if any(pattern in line_lower for pattern in ["email 1", "day 3", "followup 1", "follow-up 1"]):
                day_detected = 3
            elif any(pattern in line_lower for pattern in ["email 2", "day 5", "followup 2", "follow-up 2"]):
                day_detected = 5
            elif any(pattern in line_lower for pattern in ["email 3", "day 7", "followup 3", "follow-up 3"]):
                day_detected = 7

            if day_detected:
                # Save previous email if it has content
                if current_email["subject"] and current_email["body"]:
                    followups.append(current_email.copy())
                current_email = {"day": day_detected, "subject": "", "body": ""}
                body_started = False
                continue

            # Parse subject line - flexible matching
            if line_stripped.upper().startswith("SUBJECT:") or line_stripped.startswith("Subject:"):
                current_email["subject"] = line_stripped.split(":", 1)[1].strip()
                body_started = True
                continue

            # Parse body content
            if body_started and line_stripped:
                # Skip separator lines and labels
                if any(x in line_stripped for x in ["BODY:", "Body:", "---", "===", "****"]):
                    continue
                # Skip lines that look like email headers/sections (but keep short sentences)
                if len(line_stripped) < 3 or (line_stripped[0] == "#" and len(line_stripped) < 20):
                    continue

                # Append to body
                if current_email["body"]:
                    current_email["body"] += "\n" + line_stripped
                else:
                    current_email["body"] = line_stripped

        # Add last email if valid
        if current_email["subject"] and current_email["body"]:
            followups.append(current_email.copy())

        # If we still don't have 3 followups, try alternative parsing
        if len(followups) < 3:
            print(f"Warning: Only parsed {len(followups)} followups, attempting backup parsing...")
            followups = self._parse_followup_fallback(followup_text)

        return followups

    def _parse_followup_fallback(self, followup_text: str) -> List[Dict]:
        """Fallback parser that tries to extract any SUBJECT: lines with content after them"""
        followups = []
        lines = followup_text.split("\n")

        i = 0
        while i < len(lines):
            line = lines[i].strip()
            # Look for subject lines
            if line.upper().startswith("SUBJECT:") or line.startswith("Subject:"):
                subject = line.split(":", 1)[1].strip()

                # Collect body lines until next subject or end
                body_lines = []
                i += 1
                while i < len(lines):
                    next_line = lines[i].strip()
                    if next_line.upper().startswith("SUBJECT:") or next_line.startswith("Subject:"):
                        break
                    if next_line and not any(x in next_line for x in ["Email", "Day", "BODY:", "---", "==="]):
                        body_lines.append(next_line)
                    i += 1

                if subject and body_lines:
                    # Assign days based on order: 1st=Day 3, 2nd=Day 5, 3rd=Day 7
                    day = [3, 5, 7][len(followups)] if len(followups) < 3 else 7
                    followups.append({
                        "day": day,
                        "subject": subject,
                        "body": "\n".join(body_lines)
                    })
                continue
            i += 1

        return followups
    
    def _compile_emails_text(self, emails: Dict) -> str:
        """Compile all emails for metadata analysis"""
        text = ""
        for approach, email_data in emails.items():
            text += f"\n\n=== {approach.upper()} APPROACH ===\n"
            text += f"Subject: {email_data['subject']}\n\n"
            text += email_data['email']
        return text