"""Receive sanitized text only on stdin; emit a new self-contained PDF, never original bytes."""
import io,json,sys,html
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
p=json.load(sys.stdin)
from portable_fonts import register
register('DisclosureArial')
s=getSampleStyleSheet();s['BodyText'].fontName='DisclosureArial';s['BodyText'].fontSize=10;s['BodyText'].leading=14
s['Heading1'].fontName='DisclosureArial';s['Heading1'].fontSize=14;s['Heading1'].leading=18
story=[Paragraph(html.escape(p['title']),s['Heading1']),Paragraph('Sanitized text transcript. Original layout, images, attachments and hidden container content are omitted.',s['BodyText']),Spacer(1,12)]
for u in p['units']:
 story.append(Paragraph(html.escape(u['locator']),s['Heading2']))
 for line in u['text'].splitlines():
  story.append(Paragraph(html.escape(line) or '&#160;',s['BodyText']))
 story.append(Spacer(1,10))
def footer(c,d):
 c.setFont('Helvetica',8);c.drawString(42,25,'Sanitized transcript - page '+str(d.page))
out=io.BytesIO();SimpleDocTemplate(out,title='Sanitized disclosure',author='Project Kestrel',subject='Reviewed sanitized text transcript',leftMargin=42,rightMargin=42,topMargin=42,bottomMargin=42,invariant=1).build(story,onFirstPage=footer,onLaterPages=footer)
sys.stdout.buffer.write(out.getvalue())
