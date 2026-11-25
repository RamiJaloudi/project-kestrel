import io,json,sys,html,os
from pathlib import Path
raw=sys.stdin.buffer.read(2*1024*1024+1)
if len(raw)>2*1024*1024:raise ValueError('Report request exceeded bounds')
data=json.loads(raw);body=data['body'];kind=data['format'];status=data['status']
def paragraphs():
    yield 'Title',body['title'];yield 'Subtitle',status;yield 'Normal',body['overview'];yield 'Heading 1','Scope and coverage';yield 'Normal',body['coverage']
    for s in body['sections']:
        yield 'Heading 1',s['heading'];yield 'Normal',s['text'];yield 'Normal','Citation: '+s['reference']
    for key,label in [('risks','Risk annex'),('consents','Consent annex')]:
        yield 'Heading 1',label
        if not body[key]:yield 'Normal','No qualifying reviewed findings were selected for this annex.'
        for i,row in enumerate(body[key],1):
            yield 'Heading 2','Item '+str(i)
            yield 'Normal','\n'.join(f'{k.replace("_"," ").capitalize()}: {v}' for k,v in row.items())
if kind=='xlsx':
    from portable_workbooks import annex
    sys.stdout.buffer.write(annex(body,status))
elif kind=='docx':
    from docx import Document
    from docx.shared import Inches,Pt,RGBColor
    doc=Document();doc.sections[0].top_margin=doc.sections[0].bottom_margin=Inches(.7)
    doc.styles['Normal'].font.name='Arial';doc.styles['Normal'].font.size=Pt(10)
    title=doc.styles['Title']
    for name in ['Title','Subtitle','Heading 1','Heading 2']:
        doc.styles[name].font.color.rgb=RGBColor(0,0,0)
    for border in list(title.element.xpath('.//w:pBdr')):border.getparent().remove(border)
    for name,value in paragraphs():
        p=doc.add_paragraph(value,name)
        if name=='Normal' and '\n' in value:p.paragraph_format.keep_together=True
    output=io.BytesIO();doc.save(output);sys.stdout.buffer.write(output.getvalue())
elif kind=='pdf':
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,KeepTogether
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    # ReportLab bundles redistributable Bitstream Vera fonts. Explicit font paths
    # support another licensed Unicode font without a Windows installation path.
    from portable_fonts import register
    register('ReportFont')
    styles=getSampleStyleSheet();style=styles['BodyText'];style.fontName='ReportFont';style.fontSize=10;style.leading=14
    output=io.BytesIO();story=[]
    for name,value in paragraphs():
        import copy
        selected=copy.copy(style)
        if name=='Title':selected.fontName='ReportFontBold';selected.fontSize=20;selected.leading=25
        elif name.startswith('Heading'):selected.fontName='ReportFontBold';selected.fontSize=12;selected.leading=16;selected.keepWithNext=True
        parts=[Paragraph(html.escape(str(value)).replace('\n','<br/>'),selected)]
        if name.startswith('Heading'):selected.spaceBefore=8;selected.spaceAfter=8
        else:parts.append(Spacer(1,10))
        story.extend([KeepTogether(parts)] if name=='Normal' and '\n' in value else parts)
    SimpleDocTemplate(output,title=body['title'],leftMargin=45,rightMargin=45,topMargin=45,bottomMargin=45).build(story)
    sys.stdout.buffer.write(output.getvalue())
else:raise ValueError('Unsupported report format')
