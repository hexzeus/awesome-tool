import json
from typing import Dict, Optional
from .claude import ClaudeClient


class EmailGenerator:
    """Single-call email campaign generator"""
    
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
        Generate complete campaign in ONE API call
        
        Time: 15-20 seconds (was 60-90s)
        """
        
        print("Generating complete campaign in single call...")
        
        # Single mega-prompt
        system_prompt = self._build_system_prompt(style)
        user_prompt = self._build_user_prompt(
            company_name, industry, offer, style, company_size
        )
        
        response = await self.claude.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=4096,  # Max output
            temperature=0.8
        )
        
        # Parse the massive response
        result = self._parse_mega_response(response)
        
        return {
            "company": {
                "name": company_name,
                "industry": industry,
                "size": company_size
            },
            **result,
            "style": style
        }
    
    def _build_system_prompt(self, style: str) -> str:
        """Unified system prompt"""
        style_desc = self._get_style_description(style)
        
        return f"""You are an elite B2B cold email specialist who generates complete campaign packages.

YOUR EXPERTISE:
- Strategic company analysis ($500/hr consultant level)
- Email copywriting (Stripe/Salesforce ghostwriter quality)
- Campaign optimization (15%+ meeting rates)

STYLE: {style_desc}

You deliver complete, production-ready campaigns in structured format."""

    def _build_user_prompt(
        self,
        company_name: str,
        industry: str,
        offer: str,
        style: str,
        company_size: str
    ) -> str:
        """Single mega-prompt that requests everything"""
        
        return f"""Generate COMPLETE cold email campaign for:

TARGET:
Company: {company_name}
Industry: {industry}
Size: {company_size}
Our Solution: {offer}
Style: {style}

DELIVER COMPLETE PACKAGE:

═══════════════════════════════════════════════════════════
SECTION 1: STRATEGIC ANALYSIS (JSON)
═══════════════════════════════════════════════════════════

```json
{{
  "top_3_pain_points": [
    {{
      "pain_point": "Specific non-obvious challenge",
      "description": "Economic/operational impact with numbers",
      "urgency": "High/Critical/Medium",
      "hidden_cost": "What they're losing they don't see"
    }}
  ],
  "key_objections": [
    {{
      "objection": "Exact phrase they'll use",
      "underlying_concern": "Real fear beneath",
      "reframe_strategy": "Tactical rebuttal",
      "proof_point": "Evidence"
    }}
  ],
  "resonant_value_propositions": [
    {{
      "value_prop": "Outcome benefit",
      "why_it_works": "Psychological reason",
      "emotional_trigger": "fear/greed/status/control",
      "competitive_angle": "Differentiation"
    }}
  ],
  "approach_strategy": {{
    "primary": "Best angle",
    "rationale": "Why",
    "secondary": "Backup"
  }},
  "hooks_and_pattern_interrupts": [
    {{
      "hook": "Opening line",
      "type": "Psychology type",
      "why_it_works": "Cognitive trigger"
    }}
  ]
}}
```

═══════════════════════════════════════════════════════════
SECTION 2: FIVE COLD EMAILS
═══════════════════════════════════════════════════════════

Generate 5 emails using different approaches. Each must be 120-140 words.

---PROBLEM_AWARE---
SUBJECT: [3-6 words, no hype]

[Email body - lead with non-obvious pain, position as guide]

VARIANT_1: [alternative subject]
VARIANT_2: [alternative subject]

---AUTHORITY---
SUBJECT: [3-6 words, demonstrate expertise]

[Email body - show insights, not credentials]

VARIANT_1: [alternative subject]
VARIANT_2: [alternative subject]

---CURIOSITY---
SUBJECT: [3-6 words, information gap]

[Email body - valuable insight, create gap]

VARIANT_1: [alternative subject]
VARIANT_2: [alternative subject]

---SOCIAL_PROOF---
SUBJECT: [3-6 words, peer wins]

[Email body - specific competitor/peer results]

VARIANT_1: [alternative subject]
VARIANT_2: [alternative subject]

---DIRECT_VALUE---
SUBJECT: [3-6 words, concrete outcome]

[Email body - lead with result, back with proof]

VARIANT_1: [alternative subject]
VARIANT_2: [alternative subject]

═══════════════════════════════════════════════════════════
SECTION 3: FOLLOW-UP SEQUENCE
═══════════════════════════════════════════════════════════

---FOLLOWUP_DAY_3---
SUBJECT: [fresh angle]

[60-80 words - add new value, don't repeat]

---FOLLOWUP_DAY_5---
SUBJECT: [different angle]

[50-70 words - shift perspective]

---FOLLOWUP_DAY_7---
SUBJECT: [permission to close]

[40-60 words - acknowledge silence, give out]

═══════════════════════════════════════════════════════════
SECTION 4: STRATEGIC RECOMMENDATIONS
═══════════════════════════════════════════════════════════

# CAMPAIGN OPTIMIZATION PLAN

## 1. Optimal Send Time
[Day/time with psychology reasoning]

## 2. A/B Test Roadmap
[Primary test + 3 secondary tests]

## 3. Personalization Strategy
[5-7 dynamic tokens with sources]

## 4. Preemptive Objection Handling
[Top 4 objections with rebuttals]

## 5. Conversion Optimization
[3 structural improvements + 2 CTA refinements]

═══════════════════════════════════════════════════════════

CRITICAL RULES:
- Strategic analysis must be JSON (nothing else)
- Each email exactly 120-140 words
- Subject lines 3-6 words maximum
- No generic phrases, be specific
- Follow exact section format with delimiters"""

    def _parse_mega_response(self, response: str) -> Dict:
        """Parse the massive single response into structured data"""
        
        # Split into sections
        sections = {
            'analysis': self._extract_section(response, 'SECTION 1', 'SECTION 2'),
            'emails': self._extract_section(response, 'SECTION 2', 'SECTION 3'),
            'followups': self._extract_section(response, 'SECTION 3', 'SECTION 4'),
            'recommendations': self._extract_section(response, 'SECTION 4', '═══')
        }
        
        # Parse analysis JSON
        analysis = self._parse_analysis(sections['analysis'])
        
        # Parse emails
        emails = self._parse_emails(sections['emails'])
        
        # Parse follow-ups
        followups = self._parse_followups(sections['followups'])
        
        # Format recommendations
        recommendations = {"strategic_recommendations": sections['recommendations'].strip()}
        
        return {
            "analysis": analysis,
            "cold_emails": emails,
            "followup_sequence": followups,
            "recommendations": recommendations
        }
    
    def _extract_section(self, text: str, start_marker: str, end_marker: str) -> str:
        """Extract text between markers"""
        try:
            start = text.index(start_marker)
            end = text.index(end_marker, start + len(start_marker))
            return text[start:end]
        except ValueError:
            return ""
    
    def _parse_analysis(self, section: str) -> Dict:
        """Parse JSON analysis"""
        try:
            # Extract JSON from code block
            json_start = section.index('```json') + 7
            json_end = section.index('```', json_start)
            json_str = section[json_start:json_end].strip()
            
            data = json.loads(json_str)
            
            return {
                "strategic_brief": data,
                "raw_analysis": json_str
            }
        except:
            return {
                "strategic_brief": {
                    "top_3_pain_points": [],
                    "key_objections": [],
                    "resonant_value_propositions": [],
                    "approach_strategy": {},
                    "hooks_and_pattern_interrupts": []
                },
                "raw_analysis": section
            }
    
    def _parse_emails(self, section: str) -> Dict:
        """Parse 5 emails"""
        approaches = {
            'problem_aware': '---PROBLEM_AWARE---',
            'authority': '---AUTHORITY---',
            'curiosity': '---CURIOSITY---',
            'social_proof': '---SOCIAL_PROOF---',
            'direct_value': '---DIRECT_VALUE---'
        }
        
        emails = {}
        
        for approach, marker in approaches.items():
            try:
                start = section.index(marker) + len(marker)
                
                # Find next marker or end
                next_markers = [m for m in approaches.values() if m != marker]
                end = len(section)
                for next_marker in next_markers:
                    try:
                        pos = section.index(next_marker, start)
                        if pos < end:
                            end = pos
                    except ValueError:
                        pass
                
                email_text = section[start:end].strip()
                
                # Parse subject, body, variants
                lines = email_text.split('\n')
                subject = ""
                body = []
                variants = []
                
                for line in lines:
                    if line.startswith('SUBJECT:'):
                        subject = line.replace('SUBJECT:', '').strip()
                    elif line.startswith('VARIANT_'):
                        variants.append(line.split(':', 1)[1].strip())
                    elif line.strip() and not line.startswith('---'):
                        body.append(line)
                
                emails[approach] = {
                    "approach": approach,
                    "subject": subject,
                    "subject_variants": variants,
                    "email": '\n'.join(body).strip(),
                    "full_text": email_text
                }
            except:
                # Fallback
                emails[approach] = {
                    "approach": approach,
                    "subject": "Quick question",
                    "subject_variants": [],
                    "email": "Email parsing failed",
                    "full_text": ""
                }
        
        return emails
    
    def _parse_followups(self, section: str) -> list:
        """Parse 3 follow-ups"""
        followups = []
        markers = ['---FOLLOWUP_DAY_3---', '---FOLLOWUP_DAY_5---', '---FOLLOWUP_DAY_7---']
        days = [3, 5, 7]
        
        for i, marker in enumerate(markers):
            try:
                start = section.index(marker) + len(marker)
                
                # Find next marker
                end = len(section)
                if i < len(markers) - 1:
                    try:
                        end = section.index(markers[i + 1], start)
                    except ValueError:
                        pass
                
                text = section[start:end].strip()
                lines = text.split('\n')
                
                subject = ""
                body = []
                
                for line in lines:
                    if line.startswith('SUBJECT:'):
                        subject = line.replace('SUBJECT:', '').strip()
                    elif line.strip() and not line.startswith('---'):
                        body.append(line)
                
                followups.append({
                    "day": days[i],
                    "subject": subject,
                    "body": '\n'.join(body).strip()
                })
            except:
                followups.append({
                    "day": days[i],
                    "subject": "Following up",
                    "body": "Follow-up parsing failed"
                })
        
        return followups
    
    def _get_style_description(self, style: str) -> str:
        """Get style description"""
        styles = {
            "professional": "McKinsey partner writing to Fortune 500 C-suite",
            "casual": "Successful founder reaching out to peer founder",
            "bold": "Direct operator who's seen the pattern before"
        }
        return styles.get(style, styles["professional"])