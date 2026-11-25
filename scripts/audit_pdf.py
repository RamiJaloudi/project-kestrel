"""Bounded scoped audit PDF renderer. Input is the already-authorized event selection."""
import io,json,sys
from datetime import datetime,timezone
from html import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4,landscape
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,LongTable,TableStyle
value=json.loads(sys.stdin.buffer.read());output=io.BytesIO();styles=getSampleStyleSheet()
small=ParagraphStyle('AuditCell',fontName='Helvetica',fontSize=7,leading=9,splitLongWords=True)
rows=[[Paragraph(escape(label),small) for label in ['Time (UTC)','Actor / scope','Action / outcome','Object / event ID']]]
for row in value['rows']:
    cells=[datetime.fromtimestamp(row['occurred_at'],timezone.utc).strftime('%Y-%m-%d\n%H:%M:%S'),str(row['actor_id'] or '')+'\n'+str(row['clean_team_scope'] or ''),row['action']+'\n'+row['outcome'],str(row['object_id'] or '')+'\n'+row['id']]
    rows.append([Paragraph(escape(cell).replace('\n','<br/>'),small) for cell in cells])
table=LongTable(rows,colWidths=[80,180,185,325],repeatRows=1,hAlign='LEFT')
table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e7eef5')),('GRID',(0,0),(-1,-1),.3,colors.HexColor('#cbd5e1')),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),5),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
story=[Paragraph('Project Kestrel — scoped audit report',styles['Title']),Paragraph(escape(json.dumps(value['filters'],sort_keys=True)),styles['Normal']),Paragraph('Exported identity: '+escape(value['exported_by'])+' · Events: '+str(len(value['rows'])),styles['Normal']),Spacer(1,12),table]
def footer(canvas,doc):
    canvas.setFont('Helvetica',8);canvas.drawString(36,20,'Scoped synthetic audit · refer to the accompanying integrity manifest');canvas.drawRightString(805,20,'Page '+str(doc.page))
SimpleDocTemplate(output,pagesize=landscape(A4),leftMargin=36,rightMargin=36,topMargin=30,bottomMargin=36).build(story,onFirstPage=footer,onLaterPages=footer)
sys.stdout.buffer.write(output.getvalue())
