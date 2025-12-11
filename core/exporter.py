import io
from typing import Dict
from datetime import datetime
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY


class CampaignExporter:
    """Export campaign results to various formats"""
    
    def __init__(self):
        pass
    
    def export_to_docx(self, campaign_data: Dict) -> io.BytesIO:
        """
        Export campaign to professional Word document
        
        Returns:
            BytesIO buffer containing .docx file
        """
        doc = Document()
        
        # Set document styling
        style = doc.styles['Normal']
        font = style.font
        font.name = 'Calibri'
        font.size = Pt(11)
        
        # Title
        title = doc.add_heading('Cold Email Campaign', 0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Company info
        company = campaign_data.get('company', {})
        doc.add_heading(f"Target: {company.get('name', 'Unknown')}", level=2)
        
        info = doc.add_paragraph()
        info.add_run(f"Industry: ").bold = True
        info.add_run(f"{company.get('industry', 'N/A')}\n")
        info.add_run(f"Company Size: ").bold = True
        info.add_run(f"{company.get('size', 'N/A')}\n")
        info.add_run(f"Generated: ").bold = True
        info.add_run(f"{datetime.utcnow().strftime('%B %d, %Y')}\n")
        
        doc.add_paragraph()
        
        # Strategic Analysis
        doc.add_heading('📊 Strategic Analysis', level=1)
        analysis = campaign_data.get('analysis', {}).get('strategic_brief', {})
        
        # Pain Points
        pain_points = analysis.get('top_3_pain_points', [])
        if pain_points:
            doc.add_heading('🎯 Top 3 Pain Points', level=2)
            for i, pain in enumerate(pain_points, 1):
                p = doc.add_paragraph(style='List Number')
                p.add_run(f"{pain.get('pain_point', 'N/A')}").bold = True
                doc.add_paragraph(pain.get('description', ''), style='List Bullet 2')
                if pain.get('urgency'):
                    urgency = doc.add_paragraph(style='List Bullet 2')
                    urgency.add_run(f"Urgency: ").italic = True
                    urgency.add_run(pain['urgency'])
        
        doc.add_page_break()
        
        # Cold Emails
        doc.add_heading('📧 Cold Email Campaigns', level=1)
        
        emails = campaign_data.get('cold_emails', {})
        for i, (approach, email_data) in enumerate(emails.items(), 1):
            doc.add_heading(f"Approach {i}: {approach.replace('_', ' ').title()}", level=2)
            
            # Subject
            subject = doc.add_paragraph()
            subject.add_run('SUBJECT: ').bold = True
            subject.add_run(email_data.get('subject', 'N/A'))
            
            # Subject variants
            variants = email_data.get('subject_variants', [])
            if variants:
                var_para = doc.add_paragraph()
                var_para.add_run('Alternative Subjects: ').bold = True
                for variant in variants:
                    doc.add_paragraph(f"• {variant}", style='List Bullet')
            
            doc.add_paragraph()
            
            # Email body
            body = doc.add_paragraph()
            body.add_run('EMAIL BODY:\n').bold = True
            
            # Add email text with proper formatting
            email_text = email_data.get('email', 'N/A')
            for line in email_text.split('\n'):
                if line.strip():
                    doc.add_paragraph(line.strip())
            
            doc.add_paragraph()
            doc.add_paragraph('─' * 80)
            doc.add_paragraph()
        
        doc.add_page_break()
        
        # Follow-up Sequence
        doc.add_heading('📅 Follow-Up Sequence', level=1)
        
        followups = campaign_data.get('followup_sequence', [])
        for i, followup in enumerate(followups, 1):
            doc.add_heading(f"Follow-up {i} (Day {followup.get('day', 'N/A')})", level=2)
            
            subject = doc.add_paragraph()
            subject.add_run('SUBJECT: ').bold = True
            subject.add_run(followup.get('subject', 'N/A'))
            
            doc.add_paragraph()
            
            body_text = followup.get('body', 'N/A')
            for line in body_text.split('\n'):
                if line.strip():
                    doc.add_paragraph(line.strip())
            
            doc.add_paragraph()
        
        doc.add_page_break()
        
        # Recommendations
        doc.add_heading('💡 Strategic Recommendations', level=1)
        recommendations = campaign_data.get('recommendations', {}).get('strategic_recommendations', 'N/A')
        
        # Split and add recommendations
        for line in recommendations.split('\n'):
            if line.strip().startswith('#'):
                # Header
                level = line.count('#')
                text = line.replace('#', '').strip()
                doc.add_heading(text, level=min(level, 3))
            elif line.strip():
                doc.add_paragraph(line.strip())
        
        # Save to BytesIO
        buffer = io.BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        
        return buffer
    
def export_to_pdf(self, campaign_data: Dict) -> io.BytesIO:
        """
        Export campaign to professional PDF report
        
        Returns:
            BytesIO buffer containing PDF file
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter,
                                rightMargin=72, leftMargin=72,
                                topMargin=72, bottomMargin=18)
        
        # Container for the 'Flowable' objects
        elements = []
        
        # Define styles - CHECK IF EXISTS FIRST
        styles = getSampleStyleSheet()
        
        # Only add if not exists
        if 'CustomTitle' not in styles:
            styles.add(ParagraphStyle(
                name='CustomTitle',
                parent=styles['Heading1'],
                fontSize=24,
                textColor=colors.HexColor('#667eea'),
                spaceAfter=30,
                alignment=TA_CENTER
            ))
        
        if 'SectionHeader' not in styles:
            styles.add(ParagraphStyle(
                name='SectionHeader',
                parent=styles['Heading2'],
                fontSize=16,
                textColor=colors.HexColor('#764ba2'),
                spaceAfter=12,
                spaceBefore=12
            ))
        
        if 'SubHeader' not in styles:
            styles.add(ParagraphStyle(
                name='SubHeader',
                parent=styles['Heading3'],
                fontSize=13,
                textColor=colors.HexColor('#667eea'),
                spaceAfter=10,
                spaceBefore=10
            ))
        
        if 'CustomBody' not in styles:
            styles.add(ParagraphStyle(
                name='CustomBody',
                parent=styles['Normal'],
                fontSize=10,
                leading=14,
                alignment=TA_JUSTIFY
            ))
        
        if 'EmailBody' not in styles:
            styles.add(ParagraphStyle(
                name='EmailBody',
                parent=styles['Normal'],
                fontSize=9,
                leading=12,
                leftIndent=20,
                rightIndent=20,
                spaceAfter=6
            ))
        
        # Title
        elements.append(Paragraph("Cold Email Campaign Report", styles['CustomTitle']))
        elements.append(Spacer(1, 0.3*inch))
        
        # Company info
        company = campaign_data.get('company', {})
        elements.append(Paragraph(f"<b>Target Company:</b> {company.get('name', 'Unknown')}", styles['CustomBody']))
        elements.append(Paragraph(f"<b>Industry:</b> {company.get('industry', 'N/A')}", styles['CustomBody']))
        elements.append(Paragraph(f"<b>Company Size:</b> {company.get('size', 'N/A')}", styles['CustomBody']))
        elements.append(Paragraph(f"<b>Generated:</b> {datetime.utcnow().strftime('%B %d, %Y at %H:%M UTC')}", styles['CustomBody']))
        
        elements.append(Spacer(1, 0.4*inch))
        
        # Strategic Analysis
        elements.append(Paragraph("📊 Strategic Analysis", styles['SectionHeader']))
        elements.append(Spacer(1, 0.1*inch))
        
        analysis = campaign_data.get('analysis', {}).get('strategic_brief', {})
        
        # Pain Points
        pain_points = analysis.get('top_3_pain_points', [])
        if pain_points:
            elements.append(Paragraph("🎯 Top 3 Pain Points", styles['SubHeader']))
            for i, pain in enumerate(pain_points, 1):
                elements.append(Paragraph(f"<b>{i}. {pain.get('pain_point', 'N/A')}</b>", styles['CustomBody']))
                elements.append(Paragraph(pain.get('description', ''), styles['EmailBody']))
                if pain.get('urgency'):
                    elements.append(Paragraph(f"<i>Urgency: {pain['urgency']}</i>", styles['EmailBody']))
                elements.append(Spacer(1, 0.1*inch))
        
        # Key Objections
        objections = analysis.get('key_objections', [])
        if objections and len(objections) > 0:
            elements.append(Spacer(1, 0.2*inch))
            elements.append(Paragraph("🛡️ Key Objections", styles['SubHeader']))
            for obj in objections[:3]:  # Top 3
                if obj.get('objection'):
                    elements.append(Paragraph(f"<b>Objection:</b> {obj['objection']}", styles['CustomBody']))
                    if obj.get('reframe_strategy'):
                        elements.append(Paragraph(f"<b>Strategy:</b> {obj['reframe_strategy']}", styles['EmailBody']))
                    elements.append(Spacer(1, 0.08*inch))
        
        elements.append(PageBreak())
        
        # Cold Emails
        elements.append(Paragraph("📧 Cold Email Campaigns", styles['SectionHeader']))
        elements.append(Spacer(1, 0.2*inch))
        
        emails = campaign_data.get('cold_emails', {})
        for i, (approach, email_data) in enumerate(emails.items(), 1):
            elements.append(Paragraph(f"Approach {i}: {approach.replace('_', ' ').title()}", styles['SubHeader']))
            
            # Subject line
            subject = email_data.get('subject', 'N/A')
            elements.append(Paragraph(f"<b>SUBJECT:</b> {subject}", styles['CustomBody']))
            
            # Subject variants
            variants = email_data.get('subject_variants', [])
            if variants:
                variants_text = " | ".join(variants)
                elements.append(Paragraph(f"<i>Alternatives:</i> {variants_text}", styles['EmailBody']))
            
            elements.append(Spacer(1, 0.1*inch))
            
            # Email body - escape for XML
            email_text = email_data.get('email', 'N/A')
            email_text_safe = email_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            
            # Create bordered box for email
            email_table = Table([[email_text_safe]], colWidths=[6.5*inch])
            email_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8f9fa')),
                ('BORDER', (0, 0), (-1, -1), 1, colors.HexColor('#667eea')),
                ('PADDING', (0, 0), (-1, -1), 12),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
            ]))
            
            elements.append(email_table)
            elements.append(Spacer(1, 0.3*inch))
            
            # Add page break after every 2 emails
            if i % 2 == 0 and i < len(emails):
                elements.append(PageBreak())
        
        if len(emails) % 2 != 0:  # Only add page break if we didn't just add one
            elements.append(PageBreak())
        
        # Follow-up Sequence
        elements.append(Paragraph("📅 Follow-Up Sequence", styles['SectionHeader']))
        elements.append(Spacer(1, 0.2*inch))
        
        followups = campaign_data.get('followup_sequence', [])
        for i, followup in enumerate(followups, 1):
            day = followup.get('day', 'N/A')
            elements.append(Paragraph(f"Follow-up {i} (Day {day})", styles['SubHeader']))
            
            subject = followup.get('subject', 'N/A')
            elements.append(Paragraph(f"<b>SUBJECT:</b> {subject}", styles['CustomBody']))
            elements.append(Spacer(1, 0.08*inch))
            
            body = followup.get('body', 'N/A')
            body_safe = body.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            
            for line in body_safe.split('\n'):
                if line.strip():
                    elements.append(Paragraph(line.strip(), styles['EmailBody']))
            
            elements.append(Spacer(1, 0.2*inch))
        
        elements.append(PageBreak())
        
        # Recommendations Summary
        elements.append(Paragraph("💡 Strategic Recommendations", styles['SectionHeader']))
        elements.append(Spacer(1, 0.1*inch))
        
        recommendations = campaign_data.get('recommendations', {}).get('strategic_recommendations', 'N/A')
        
        # Parse and add first section of recommendations
        rec_lines = recommendations.split('\n')
        for line in rec_lines[:30]:  # First 30 lines to keep PDF concise
            line = line.strip()
            # Escape XML characters
            line = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            
            if line.startswith('##'):
                text = line.replace('##', '').strip()
                elements.append(Paragraph(text, styles['SubHeader']))
            elif line.startswith('#'):
                text = line.replace('#', '').strip()
                elements.append(Paragraph(text, styles['SubHeader']))
            elif line.startswith('-'):
                text = line.replace('-', '•', 1).strip()
                elements.append(Paragraph(text, styles['CustomBody']))
            elif line:
                elements.append(Paragraph(line, styles['CustomBody']))
        
        elements.append(Spacer(1, 0.3*inch))
        elements.append(Paragraph("<i>Full strategic recommendations available in the web interface.</i>", styles['CustomBody']))
        
        # Footer
        elements.append(Spacer(1, 0.5*inch))
        elements.append(Paragraph("─" * 80, styles['CustomBody']))
        elements.append(Paragraph(
            f"<i>Generated by Cold Email Generator Pro | {datetime.utcnow().strftime('%B %d, %Y')}</i>",
            styles['CustomBody']
        ))
        
        # Build PDF
        doc.build(elements)
        buffer.seek(0)
        
        return buffer