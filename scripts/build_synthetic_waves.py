"""Author small fictional matter inputs. Run with the bundled artifact Python."""
import hashlib
import json
from pathlib import Path
import textwrap
from docx import Document
from docx.shared import Inches,Pt,RGBColor
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from PIL import Image,ImageDraw,ImageFont

ROOT=Path(__file__).resolve().parents[1]
TARGET=ROOT.parent/'Synthetic_Data'
QA=ROOT/'.runtime/fixture-qa'
FONT=Path('C:/Windows/Fonts/arial.ttf')

def docx_file(path,title,paragraphs):
    if path.exists():return
    doc=Document();section=doc.sections[0]
    section.page_width=Inches(8.5);section.page_height=Inches(11)
    section.top_margin=section.bottom_margin=section.left_margin=section.right_margin=Inches(.85)
    normal=doc.styles['Normal'];normal.font.name='Arial';normal.font.size=Pt(11);normal.paragraph_format.space_after=Pt(9)
    normal.font.color.rgb=RGBColor(0,0,0)
    doc.styles['Title'].font.name='Arial';doc.styles['Title'].font.size=Pt(16);doc.styles['Title'].font.color.rgb=RGBColor(0,0,0)
    for style in doc.styles:
        for border in style.element.xpath('./w:pPr/w:pBdr'):border.getparent().remove(border)
    doc.add_paragraph(title,'Title')
    for paragraph in paragraphs:doc.add_paragraph(paragraph)
    doc.core_properties.title=title;doc.core_properties.author='Project Kestrel synthetic fixtures';doc.save(path)

def pdf_file(path,title,paragraphs,scan=False):
    if path.exists():return
    if scan:
        image=Image.new('RGB',(1700,2200),'white');draw=ImageDraw.Draw(image)
        body=ImageFont.truetype(str(FONT),34);heading=ImageFont.truetype(str(FONT),46)
        y=130
        for line in textwrap.wrap(title,55):draw.text((130,y),line,font=heading,fill='black');y+=62
        y+=35
        for paragraph in paragraphs:
            for line in textwrap.wrap(paragraph,76):draw.text((130,y),line,font=body,fill='black');y+=48
            y+=32
        output=canvas.Canvas(str(path),pagesize=(612,792));output.drawImage(ImageReader(image),0,0,width=612,height=792);output.save();return
    pdfmetrics.registerFont(TTFont('FixtureArial',str(FONT)))
    styles=getSampleStyleSheet()
    for style in styles.byName.values():style.fontName='FixtureArial'
    styles['Title'].fontSize=16;styles['Title'].leading=20;styles['BodyText'].fontSize=11;styles['BodyText'].leading=16
    story=[Paragraph(title,styles['Title']),Spacer(1,14)]
    for paragraph in paragraphs:story.extend([Paragraph(paragraph,styles['BodyText']),Spacer(1,10)])
    SimpleDocTemplate(str(path),pagesize=(612,792),leftMargin=60,rightMargin=60,topMargin=60,bottomMargin=60).build(story)

def build():
    QA.mkdir(parents=True,exist_ok=True)
    all_rows=[]
    common=['Synthetic transaction example. All parties, amounts and clauses are fictional.','Matter 012345-789012. Proposed buyer Halden Industries plc; target Vireo Systems GmbH.']
    fixtures=[
      (1,'C001','C001_v1_customer_contract.pdf','Customer services agreement',common+[
        'Parties: Vireo Systems GmbH and Orion Demo AG. Services start on 1 January 2027 for a three year term.',
        'Clause 9. A change of control of the supplier requires the customer\'s prior written consent before completion.',
        'Clause 12. Assignment of this agreement requires prior written consent. A consent request must identify the acquiring entity.',
        'Clause 18. This agreement is governed by the law of England and Wales.'], 'ordinary','contract','en','England and Wales',False),
      (1,'L001','L001_v1_software_licence.docx','Synthetischer Softwarelizenzvertrag',[
        'Synthetisches Transaktionsbeispiel. Parteien, Klauseln und Beträge sind frei erfunden.',
        'Aktenzeichen 012345-789012. Lizenzgeber ist Vireo Systems GmbH. Lizenznehmer ist Larch Synthetic GmbH.',
        'Ziffer 7. Bei einem Kontrollwechsel des Lizenzgebers ist die vorherige schriftliche Zustimmung des Lizenznehmers erforderlich.',
        'Ziffer 8. Eine Abtretung der Rechte aus diesem Vertrag bedarf der Zustimmung der anderen Partei.',
        'Ziffer 14. Dieser deutschsprachige Vertrag unterliegt dem Recht von England und Wales. Die Vertragssprache bestimmt nicht das anwendbare Recht.'],
        'ordinary','licence','de','England and Wales',False),
      (1,'P001','P001_v1_clean_team_pricing.xlsx','Synthetic clean team pricing',[], 'clean_team','pricing','en','unconfirmed',False),
      (1,'A001','A001_v1_privileged_legal_note.docx','Synthetic internal legal advice',common+[
        'Privileged internal legal advice prepared only as a synthetic workflow example. Do not include this note in a bank package.',
        'The change of control clause in the customer agreement should be checked against its full context and the transaction structure.',
        'The presence of prior written consent language is a triage signal, not a legal conclusion about whether consent is required.',
        'A qualified lawyer must decide materiality and audience release. No actual legal research or legal opinion is supplied.'],
        'privileged','legal_advice','en','unconfirmed',False),
      (1,'S001','S001_v1_scanned_assignment.pdf','Synthetic scanned assignment schedule',common+[
        'Clause 4. Assignment requires prior written consent from the customer before the transfer takes effect.',
        'This file contains an image of text. It is an OCR coverage test and must remain pending if no OCR engine is configured.'],
        'ordinary','contract','en','unconfirmed',True),
      (2,'C001','C001_v2_customer_contract.pdf','Customer services agreement revised',common+[
        'Wave 2 replaces C001 version 1. Preserve the previous source and its reviewed findings.',
        'Clause 9 revised. A change of control requires notice to the customer within forty days after completion. Prior written consent is required only for assignment outside the permitted group.',
        'Clause 12. Assignment to a permitted group company is allowed on notice. Assignment to another party requires prior written consent.',
        'Clause 18. The governing law remains England and Wales.'], 'ordinary','contract','en','England and Wales',False),
      (2,'L002','L002_v1_data_processing.docx','Synthetic data processing agreement',common+[
        'The parties are Vireo Systems GmbH and Fable Test Ltd. This is a new document in Wave 2.',
        'Clause 6. The supplier may not make an assignment of processing obligations without prior written consent.',
        'Clause 10. No AI processing of this agreement or its underlying records is permitted. Human review is required.',
        'Clause 15. Governing law is not confirmed in this synthetic intake exercise.'], 'ordinary','contract','en','unconfirmed',False),
      (2,'P001','P001_v2_clean_team_pricing.xlsx','Synthetic clean team pricing revised',[], 'clean_team','pricing','en','unconfirmed',False),
      (2,'A002','A002_v1_privileged_legal_note.docx','Synthetic second wave legal advice',common+[
        'Privileged internal legal advice. This is a new internal source; the bank must not receive it or derived privileged material.',
        'Wave 2 changes the customer consent wording. Compare the exact source versions rather than silently overwriting earlier findings.',
        'Review the assignment exception and the change of control notice period with qualified transaction counsel.'], 'privileged','legal_advice','en','unconfirmed',False),
      (2,'C002','C002_v1_supply_contract.pdf','Synthetischer Liefervertrag',[
        'Synthetisches Transaktionsbeispiel. Keine echten Parteien oder vertraulichen Informationen.',
        'Parteien sind Vireo Systems GmbH und Meridian Testtechnik GmbH. Dieser Vertrag ist neu in Welle 2.',
        'Ziffer 11. Ein Kontrollwechsel ist dem Kunden unverzüglich mitzuteilen. Eine Abtretung bedarf der vorherigen schriftlichen Zustimmung.',
        'Ziffer 17. Es gilt deutsches Recht. Ein Rechtsanwalt muss die Bedeutung im konkreten Transaktionskontext prüfen.'],
        'ordinary','contract','de','Germany',False),
      (2,'S002','S002_v1_scanned_service_order.pdf','Synthetic scanned service order',common+[
        'New Wave 2 service order. A change of control requires prior written consent under clause 5.',
        'This is an image-only file for OCR testing. Do not treat absent extracted text as a negative finding.'], 'ordinary','contract','en','unconfirmed',True)
    ]
    for wave,key,name,title,paragraphs,label,kind,lang,law,scan in fixtures:
        folder=TARGET/f'Wave_{wave}';folder.mkdir(parents=True,exist_ok=True);path=folder/name
        if path.suffix=='.docx':docx_file(path,title,paragraphs)
        elif path.suffix=='.pdf':pdf_file(path,title,paragraphs,scan)
        all_rows.append({'file_name':name,'logical_key':key,'wave':'wave'+str(wave),'classification':label,'resource_type':kind,
            'language':lang,'governing_law':law,'clean_team_scope':'pricing' if label=='clean_team' else '',
            'synthetic':True,'wave_number':wave,'previous_key':key if wave==2 and key in {'C001','P001'} else None,'scan':scan})
    (QA/'wave-build.json').write_text(json.dumps(all_rows,indent=2,ensure_ascii=False),encoding='utf-8')
    print('PDF and Word fixtures created without overwriting existing local files; Excel build metadata ready.')

if __name__=='__main__':build()
