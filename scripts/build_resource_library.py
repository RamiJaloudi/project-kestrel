"""Build authored synthetic resources, with a closed manifest of downloadable files.

Use the bundled document runtime. Model-only schema export is a separate step.
No source documents, credentials, row data or original third-party forms are read.
"""
import csv
import hashlib
import html
import json
import re
import shutil
import zipfile
from pathlib import Path
from docx import Document
from docx.shared import Inches, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'backend/kestrel/data/resource_library'
WORKSPACE = ROOT.parent
DELIVERABLES = WORKSPACE / 'Deliverables/Project_Kestrel_Written_Deliverables_2026-11-24'
CATALOG = []


def register(filename, title, description, category, audiences=('firm', 'halden', 'castlegate'), status='Authored synthetic example'):
    path = OUT / filename
    mime = {'.csv': 'text/csv', '.md': 'text/markdown', '.txt': 'text/plain', '.svg': 'image/svg+xml',
            '.mmd': 'text/plain', '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.pdf': 'application/pdf', '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation', '.zip':'application/zip'}[path.suffix]
    asset_id = path.stem.lower().replace('_', '-')
    if category in {'Diagrams', 'Forms and trackers'}: asset_id += '-'+path.suffix.lstrip('.')
    if any(entry['id'] == asset_id for entry in CATALOG): raise ValueError('Duplicate asset ID: '+asset_id)
    CATALOG.append({'id': asset_id, 'filename': filename, 'title': title,
                    'description': description, 'category': category, 'audiences': list(audiences),
                    'status': status, 'media_type': mime, 'bytes': path.stat().st_size,
                    'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'updated': '2026-11-24'})


def text_asset(filename, title, text, category='Guides', **kwargs):
    (OUT / filename).write_text(text, encoding='utf-8')
    paragraphs = text.split('\n\n')
    description = re.split(r'(?<=[.!?])\s+', paragraphs[min(1, len(paragraphs)-1)].replace('\n', ' '))[0]
    if category in {'Guides','API and schema'}: kwargs.setdefault('status','Authored project guide')
    register(filename, title, description[:400], category, **kwargs)


def copy_asset(source, filename, title, description, category, **kwargs):
    if source.is_file():
        shutil.copyfile(source, OUT / filename)
        register(filename, title, description, category, **kwargs)


def csv_asset(filename, title, headers, rows, definitions, **kwargs):
    with (OUT / filename).open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.writer(stream); writer.writerow(headers); writer.writerows(rows)
    register(filename, title, 'Fictional example rows. This file is not an application export or approval record. Column meanings are in Ledger_Field_Definitions.csv.', 'Sample ledgers', **kwargs)
    return [{'file': filename, 'field': key, 'definition': definition, 'example_status': 'SYNTHETIC EXAMPLE'} for key, definition in zip(headers, definitions, strict=True)]


def report(filename, title, audience, sections):
    doc = Document()
    section = doc.sections[0]; section.top_margin = section.bottom_margin = Inches(.65)
    section.left_margin = section.right_margin = Inches(.75)
    normal = doc.styles['Normal']; normal.font.name = 'Calibri'; normal.font.size = Pt(10.5)
    normal.paragraph_format.space_after = Pt(6)
    doc.styles['Title'].font.size = Pt(23); doc.styles['Title'].font.color.rgb = RGBColor(0, 0, 0)
    for name in ['Heading 1', 'Heading 2']:
        doc.styles[name].font.color.rgb = RGBColor.from_string('173E58')
        doc.styles[name].font.size = Pt(13 if name == 'Heading 1' else 11)
    doc.add_paragraph(title, 'Title')
    doc.add_paragraph('Project Kestrel | Fictional example | 24 November 2026')
    doc.add_paragraph(f'Prepared by the Kestrel project team for {audience}. This example shows report structure and pending decisions. It is not legal advice, an approved report, or evidence of an application release.')
    for heading, paragraphs in sections:
        doc.add_paragraph(heading, 'Heading 1')
        for paragraph in paragraphs: doc.add_paragraph(paragraph)
    foot = section.footer.paragraphs[0]; foot.text = 'SYNTHETIC SAMPLE   •   No application approval or release recorded'
    foot.runs[0].font.size = Pt(8)
    doc.core_properties.author = 'Kestrel project team'; doc.core_properties.last_modified_by = 'Kestrel project team'
    for element in [doc.element, doc.styles.element]:
        for border in element.xpath('.//w:pBdr'):
            border.getparent().remove(border)
    doc.save(OUT / filename)


def diagram(stem, title, subtitle, boxes, footer, category='Diagrams'):
    # Four stages with concrete labels; native SVG stays readable when enlarged.
    colors = ['#E8F2F7', '#EEF1FA', '#FFF4DE', '#E6F4EC']
    width = 1280; height = 470
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
           f'<title id="title">{html.escape(title)}</title><desc id="desc">{html.escape(subtitle + " " + footer)}</desc>',
           '<rect width="1280" height="470" fill="#FFFFFF"/>',
           '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6" fill="#567083"/></marker></defs>',
           f'<text x="42" y="52" font-family="Arial,sans-serif" font-size="29" fill="#15384D" font-weight="700">{html.escape(title)}</text>',
           f'<text x="42" y="86" font-family="Arial,sans-serif" font-size="17" fill="#4C6373">{html.escape(subtitle)}</text>']
    for i, (heading, lines) in enumerate(boxes):
        x = 42 + i * 305
        svg += [f'<rect x="{x}" y="127" width="278" height="228" rx="10" fill="{colors[i]}" stroke="#AEC1CE"/>',
                f'<text x="{x+19}" y="163" font-family="Arial,sans-serif" font-size="19" fill="#173E58" font-weight="700">{i+1}  {html.escape(heading)}</text>']
        for n, line in enumerate(lines):
            svg.append(f'<text x="{x+19}" y="{202+n*28}" font-family="Arial,sans-serif" font-size="16" fill="#263F4F">{html.escape(line)}</text>')
        if i < 3: svg.append(f'<path d="M{x+281},241 L{x+301},241" stroke="#567083" stroke-width="2" marker-end="url(#arrow)"/>')
    for i, line in enumerate(footer.split('\n')):
        svg.append(f'<text x="42" y="{398+i*25}" font-family="Arial,sans-serif" font-size="16" fill="#344F60">{html.escape(line)}</text>')
    svg.append('</svg>')
    text_asset(stem+'.svg', title, '\n'.join(svg), category, status='Current code and explicit deployment limits')
    CATALOG[-1]['description'] = subtitle + ' ' + footer.replace('\n', ' ')
    mermaid = ['flowchart LR']
    for i,(heading,lines) in enumerate(boxes):
        mermaid.append(f'  S{i}["{heading}<br/>'+ '<br/>'.join(lines) + '"]')
        if i: mermaid.append(f'  S{i-1} --> S{i}')
    text_asset(stem+'.mmd', title+' editable source', '\n'.join(mermaid), category, status='Editable Mermaid source')
    CATALOG[-1]['description'] = subtitle


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    text_asset('Resource_Library_Guide.md', 'Find and use project assets', '''# Find and use project assets

Resources brings together workflow guides, diagrams, sample ledgers, report examples, forms and technical dictionaries. Sign in through your own portal. Downloads are checked against your current account and organization.

## Where to start

- Guides: read the short guide, then use the role-specific Excel walkthrough below it. Record actual approvals in the application.
- Diagrams: open SVG for a readable picture or download Mermaid source to edit it. The deployment diagram shows the DNS configuration, not a completed public launch.
- Sample ledgers: six fictional registers cover intake, financial entries, findings, decisions, releases and audit events. Read Ledger Field Definitions before reusing a column.
- Sample reports: the firm sees the internal DD draft. Halden sees the client-format example. Castlegate sees the commercial-format example. These examples contain no real matter data and create no release entitlement.
- Forms and trackers: use the authored checklist and associate tracker as review aids. Their completion does not approve a source or release a report.
- API and schema: the Portal Home API explorer card links to Resources with the API and schema category selected. API explorer pages also link to the same downloads on the current portal.

## What is included

Static examples and documentation only. Live documents, reports, audit exports, source access, clean-team grants and approvals remain in their governed workspaces. A downloaded copy cannot be recalled by revoking the server session.

## Update discipline

Each download lists its date, size and SHA256 digest. The catalogue is a fixed allowlist of bundled files. Rebuild and review it after changing an asset. Never place credentials, real client material or original third-party source forms in this library.
''')
    text_asset('API_and_Schema_Guide.md', 'Understand the API and schema files', '''# Understand the API and schema files

Use OpenAPI to see the requests the application accepts today. Use the implemented model dictionaries to understand the tables declared by the code. Use the proposed design dictionaries to discuss the larger target architecture. These are different sources and must not be treated as the same schema.

## Read the files in this order

1. Implemented Schema Tables counts columns in each declared SQLAlchemy table. Implemented Schema Fields lists type, nullability, primary and foreign keys, and the basis for each explanation. This export reads code only. It does not connect to a database or prove that a deployed database has applied every migration.
2. Proposed Schema Fields explains the 809-field design snapshot. Proposed Schema Groups explains its documentation domains. The group field is a documentation category, not an account group or access grant.
3. Schema CSV Column Guide explains the headers in the proposed dictionary. Entity Catalogue and Foreign Key Relationships provide the corresponding target structure.
4. Tech Stack and Linux Portability records why each component was chosen and the work needed to move it from the Windows Azure VM. Portability is an engineering assessment, not a completed Linux test.
5. The Word schema guide tells the field story in a few pages. OpenAPI remains the request and response contract; neither dictionary grants API access or replaces service validation.

## Follow the data story

Identify a person and matter. Retain a document and immutable version. Bind exact evidence to a candidate finding and the playbook used. Record a lawyer decision. Build a report version. Approve a named audience separately. Retain audit history and apply holds and retention rules.

Stable identifiers connect records. Labels describe them. Version and hash fields bind a decision to exact content. Status fields record progress. Approval and release fields express separate decisions. Time and expiry fields bound access. Sensitivity fields help the shared policy engine decide who can act.

## Read definitions carefully

Declared types and keys are extracted facts. Some descriptions are inferred from field names because the source has no separate definition. The definition basis column flags that limitation. Check the relevant service, migrations and tests before changing a constraint. Missing data is not zero, and a pending decision is not approval.
''', category='API and schema')
    text_asset('Report_and_Ledger_Guide.md', 'Read sample reports and ledgers', '''# Read sample reports and ledgers

Every sample is fictional and separate from live matter records. Use the examples to learn the layout and field meanings. Reusing a row or typing Approved into a spreadsheet cannot create an application approval.

## Ledger types

Document review tracks receipt, exact version, assigned reviewer and coverage. Financial entries show double-entry debits and credits with a source pointer. Findings track an issue, exact citation, recommendation and legal review. Decisions identify the exact subject version, independent reviewer and rationale. Releases record the separate audience decision. Audit events show an ordered activity trail with minimal content.

The financial example is in EUR for November 2026 and balances at 15000.00 in both debit and credit columns. It demonstrates recording entries only, not valuation, tax, a financial-materiality score or a verified financial fact. Source references are illustrative and cannot open a real document.

## Report types

The internal DD draft explains one fictional contract issue, its evidence and missing facts. The Halden example shows a client-facing action summary. The Castlegate example shows a smaller commercial update without privileged legal analysis or restricted pricing. None is approved or released in the application.

## Use real workspaces for real decisions

Use Documents for ingestion, Risk Review for lawyer findings, Financial Evidence for verified numeric facts, DDR Runs for governed drafting, Reports for versioned packages, Release Desk for audience decisions, and Audit for permitted event exports. Downloading a sample performs none of those actions.
''')
    definitions = []
    definitions += csv_asset('Document_Review_Ledger.csv','Document review ledger',
        ['example_status','document_id','version','vdr_reference','title','received_on','reviewer','review_status','finding_id','next_action'],
        [['SYNTHETIC','DOC-001','1','VDR-DEMO-001','Customer agreement','2026-11-20','Reviewer A','Review complete','FND-001','Obtain consent analysis'],
         ['SYNTHETIC','DOC-002','1','VDR-DEMO-002','Software licence','2026-11-21','Reviewer B','Awaiting review','','Check assignment terms'],
         ['SYNTHETIC','DOC-001','2','VDR-DEMO-001-v2','Customer agreement amendment','2026-11-24','Reviewer A','Awaiting comparison','','Compare with version 1']],
        ['Marks all rows fictional.','Stable example document key.','Exact example source version.','Illustrative seller data-room reference.','Safe document label.','Receipt date in ISO format.','Fictional assigned reviewer.','Coverage state; not audience approval.','Related example finding if recorded.','Specific outstanding task.'], audiences=('firm',))
    definitions += csv_asset('Financial_Transaction_Ledger.csv','Financial transaction ledger',
        ['example_status','entry_id','date','entity','account','description','currency','debit','credit','source_reference','verification_status'],
        [['SYNTHETIC','JE-001','2026-11-01','Demo Target','Bank','Owner funding','EUR','10000.00','0.00','DEMO-JOURNAL-1 rows 1-2','Illustrative only'],
         ['SYNTHETIC','JE-001','2026-11-01','Demo Target','Equity','Owner funding','EUR','0.00','10000.00','DEMO-JOURNAL-1 rows 1-2','Illustrative only'],
         ['SYNTHETIC','JE-002','2026-11-02','Demo Target','Software expense','Supplier invoice','EUR','2500.00','0.00','DEMO-INVOICE-1','Illustrative only'],
         ['SYNTHETIC','JE-002','2026-11-02','Demo Target','Accounts payable','Supplier invoice','EUR','0.00','2500.00','DEMO-INVOICE-1','Illustrative only'],
         ['SYNTHETIC','JE-003','2026-11-15','Demo Target','Accounts payable','Invoice payment','EUR','2500.00','0.00','DEMO-BANK-1','Illustrative only'],
         ['SYNTHETIC','JE-003','2026-11-15','Demo Target','Bank','Invoice payment','EUR','0.00','2500.00','DEMO-BANK-1','Illustrative only']],
        ['Marks all rows fictional.','Journal entry key joining its debit and credit lines.','Posting date.','Fictional reporting entity.','Account receiving the debit or credit.','Plain explanation of the entry.','ISO currency code; no FX conversion.','Debit amount as an exact decimal string.','Credit amount as an exact decimal string.','Illustrative evidence pointer.','These rows have not undergone application fact verification.'])
    definitions += csv_asset('Findings_and_Issues_Ledger.csv','Findings and open issues ledger',
        ['example_status','finding_id','document_id','source_version','citation','issue','proposed_risk','legal_review','recommendation','owner','due_on'],
        [['SYNTHETIC','FND-001','DOC-001','1','DEMO clause 8.2','Consent may be needed on change of control','High','Pending','Obtain complete agreement and consent position','Reviewer A','2026-11-27'],
         ['SYNTHETIC','FND-002','DOC-002','1','DEMO clause 5','Licence assignment treatment is unclear','Unknown','Pending','Confirm transaction structure and assignment trigger','Reviewer B','2026-11-28']],
        ['Marks all rows fictional.','Stable issue identifier.','Related fictional document.','Exact source version.','Illustrative citation, not retrievable evidence.','Question or risk for review.','Unapproved priority suggestion; Unknown is not Low.','Lawyer decision state.','Team proposed next step.','Fictional responsible reviewer.','Suggested task date.'], audiences=('firm',))
    definitions += csv_asset('Approval_Decision_Ledger.csv','Approval and decision ledger',
        ['example_status','decision_id','subject_type','subject_id','subject_version','author','reviewer','decision','rationale','decided_at'],
        [['SYNTHETIC','DEC-001','Report','REP-001','1','Reviewer A','Reviewer C','Pending','Independent review not yet recorded',''],
         ['SYNTHETIC','DEC-002','Playbook','PB-001','2','Editor A','SME B','Illustrative rejection','Example missed a scope exception','2026-11-23T15:00:00Z']],
        ['Marks all rows fictional.','Decision record key.','Kind of controlled item.','Item identifier.','Exact revision submitted.','Fictional creator; cannot self-approve.','Fictional independent decision maker.','Sample state; not an application decision.','Reason for the decision or pending work.','UTC decision time; blank while pending.'], audiences=('firm',))
    definitions += csv_asset('Audience_Release_Ledger.csv','Audience release ledger',
        ['example_status','release_id','report_id','report_version','audience','internal_review','audience_decision','antitrust_decision','expires_at','next_action'],
        [['SYNTHETIC','REL-001','REP-001','1','Halden','Pending','Pending','Applicability to be checked','','Finish exact-version internal review'],
         ['SYNTHETIC','REL-002','REP-002','1','Castlegate','Pending','Pending','Applicability to be checked','','Confirm commercial scope and exclusions']],
        ['Marks all rows fictional.','Release proposal key.','Target report.','Exact report revision.','Intended organization.','Independent internal report decision.','Separate audience decision.','Separate counsel gate when applicable.','Expiry if an actual release is approved.','Outstanding prerequisite.'], audiences=('firm',))
    definitions += csv_asset('Audit_Event_Ledger.csv','Audit event ledger',
        ['example_status','event_id','occurred_at','actor','action','object_type','object_id','outcome','correlation_id','integrity_note'],
        [['SYNTHETIC','EVT-001','2026-11-24T14:00:00Z','Reviewer A','Read','Document version','DOC-001-v1','Permitted','DEMO-CORR-001','Example only; no hash chain proof'],
         ['SYNTHETIC','EVT-002','2026-11-24T14:05:00Z','Reviewer A','Submit review','Finding','FND-001','Pending independent decision','DEMO-CORR-002','Example only; not a retained event']],
        ['Marks all rows fictional.','Example event key.','UTC event time.','Fictional acting person.','Attempted action.','Type of affected record.','Example record key.','Observed or proposed outcome.','Connects related request activity without source text.','States the limit of this illustrative file.'], audiences=('firm',))
    with (OUT/'Ledger_Field_Definitions.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(definitions[0]));writer.writeheader();writer.writerows(definitions)
    register('Ledger_Field_Definitions.csv','Ledger field definitions','Column meanings for all six synthetic ledger formats. This dictionary describes examples, not database import contracts.','Sample ledgers')

    report('Internal_Due_Diligence_Sample.docx','Internal due diligence draft','the internal legal review team',[
        ('Scope and conclusion',['Review the change-of-control position before relying on the fictional customer agreement. The complete contract and any waiver are missing. We cannot yet conclude that consent is required or that completion would breach the agreement.']),
        ('Evidence and issue',['Fictional source DOC-001 version 1, clause 8.2: “A change of control requires the supplier’s prior written consent.” This invented clause is provided only to demonstrate a citation. Its parties, definitions and exceptions must be checked in a complete agreement.']),
        ('Assumption and recommendation',['Working assumption: the proposed acquisition may change control of the relevant contracting party. Confirm the transaction structure, the defined trigger and who must consent. Ask the associate to obtain the complete contract, all amendments and the counterparty consent position.']),
        ('Review and release status',['Risk suggestion: High, pending lawyer assessment. Owner: Reviewer A. Target follow-up: 27 November 2026. No independent report review, client release or bank release has been recorded. Any restricted source would also require its applicable clean-team and antitrust controls.'])])
    register('Internal_Due_Diligence_Sample.docx','Internal due diligence report example','Short internal draft with a fictional citation, assumptions, team recommendation and pending decisions.','Sample reports',audiences=('firm',))
    report('Halden_Due_Diligence_Sample.docx','Client due diligence summary example','the fictional Halden deal team',[
        ('Action requested',['Ask the legal team to confirm whether a material customer contract needs counterparty consent for the acquisition. Obtain the missing complete contract and amendments before treating the issue as resolved.']),
        ('Current position',['The fictional review remains incomplete. Transaction structure, contractual definitions and any consent waiver are unconfirmed. No financial impact has been verified. This example intentionally omits internal legal deliberations and restricted pricing.']),
        ('Follow up and publication',['Proposed owner: client transaction lead with the legal team. Proposed follow-up: 27 November 2026. This document illustrates the client report format only. The application requires an approved exact report version and separate Halden audience release before any real report is visible.'])])
    register('Halden_Due_Diligence_Sample.docx','Halden report example','Client-format action summary using fictional facts; no source material or application release.','Sample reports',audiences=('firm','halden'))
    report('Castlegate_Commercial_Report_Sample.docx','Commercial diligence update example','the fictional Castlegate advisory team',[
        ('Commercial action',['One fictional customer contract remains subject to a consent-status check. Keep the item open in the transaction timetable until the deal team confirms the position.']),
        ('Information available',['No revenue exposure, valuation adjustment or financial loss has been verified. This example supplies no original contract, legal advice, competitive pricing or internal review notes.']),
        ('Next update and release',['Request an approved commercial status update from the deal team. This example is not an actual disclosure. A real Castlegate package requires its own exact-version audience release and all source-specific restrictions.'])])
    register('Castlegate_Commercial_Report_Sample.docx','Castlegate commercial report example','Commercial-format status update with explicit missing financial impact and no privileged legal analysis.','Sample reports',audiences=('firm','castlegate'))
    diagram('Document_to_Report','From a VDR document to a report','Implemented workflow overview. Each stage retains its source and version.',[
        ('Receive and retain',['Associate checks intake','Keep original and version','Classify access restrictions','Track missing documents']),
        ('Review the evidence',['Apply an approved playbook','AI proposes a candidate','Lawyer checks exact passage','Record corrections and gaps']),
        ('Draft and approve',['Draft from reviewed findings','Keep citations and annexes','Independent report review','Changed draft needs review']),
        ('Release to an audience',['Separate Halden decision','Separate Castlegate decision','Apply antitrust gate if needed','Recheck access on download'])],
        'Search answers a question over permitted evidence. It does not prove that every document was reviewed.\nThis diagram describes the code workflow; it does not prove acceptance on the Azure VM.')
    diagram('Access_and_Release','How access and release are checked','The hostname chooses the screen. The server decides whether the person may act.',[
        ('Verify the person',['Signed-in server session','Correct organization portal','Active account and roles','No role from request headers']),
        ('Check the scope',['Matter assignment','Ethical walls and labels','Named clean-team scope','Expiry and source limits']),
        ('Check the output',['Lawyer-reviewed finding','Independent report decision','Audience release decision','Antitrust decision if required']),
        ('Serve allowed content',['Check again on each request','Keep client and bank separate','Record permitted audit data','Deny when a gate is missing'])],
        'Root Admin has no blanket legal or source-reading privilege. Notification read is not approval.\nThe Resource library contains authored examples only; it does not expose live matter exports.')
    diagram('Azure_Deployment','Azure portal deployment','DNS configured on 24 November 2026. HTTPS and application activation have separate acceptance gates.',[
        ('Five portal names',['portal.ramijaloudi.com','firm / halden / castlegate','admin under portal domain','GoDaddy A records; TTL 600']),
        ('Azure Windows VM',['Static IP 52.162.140.174','Windows Server runtime','Shared proxy is controlled','Existing RPlus route preserved']),
        ('Private app services',['Caddy to loopback FastAPI','React screens and OpenAPI','PostgreSQL and worker','Separate service identities']),
        ('Activation still gated',['Check real restore and backup','Validate exact HTTPS names','Review effective access rules','Obtain public acceptance'])],
        'Configured hostnames are not evidence of a live public application. Do not bypass the CLOSED gate.\nLinux requires replacements for DPAPI, Windows service control and the owner approval boundary.')
    diagram('Schema_Story','The schema follows the review','Use implemented dictionaries for model structure and proposed dictionaries for target design.',[
        ('People and sources',['Accounts and organizations','Matter and access grants','Document identity and version','Exact evidence location']),
        ('Analysis and review',['Playbook and model version','Run and candidate finding','Lawyer review and correction','Independent governance']),
        ('Reports and audiences',['Report and annex version','Internal review decision','Named audience release','Expiry and revoked access']),
        ('History and retention',['Audit event and correlation','Immutable version bindings','Signing snapshot and holds','Eligible copy deletion'])],
        'The proposed dictionary contains 809 fields. Its group column is a documentation domain, not an access grant.\nThe implemented model export reads structure only; applied database migrations need separate verification.')
    diagram('API_Architecture','How the API connects the application','One typed API supports the portals. Calling an endpoint never creates permission.',[
        ('Portal and account',['React and TypeScript screens','Current organization session','Same-origin API requests','CSRF token for state changes']),
        ('FastAPI boundary',['Pydantic request validation','Current identity dependency','Audience and route checks','Grouped OpenAPI explorer']),
        ('Policy and services',['Shared source access policy','Evidence and review rules','Independent approval rules','Controlled worker operations']),
        ('Retained records',['PostgreSQL and migrations','Exact document versions','Private source artifacts','Durable decisions and audit'])],
        'OpenAPI describes current request and response contracts. Model CSVs describe the code-declared structure.\nThe proposed 809-field design is separate. Enterprise integrations remain design or mock adapters where stated.')
    diagram('Search_Architecture','How a cited question is answered','Search uses the evidence the signed-in person may currently read.',[
        ('Select eligible evidence',['Check organization and matter','Apply walls and source labels','Check release and expiry','Exclude unauthorized text']),
        ('Choose search mode',['Default is lexical BM25','No default provider call','Internal semantic or hybrid','Needs approved provider use']),
        ('Retrieve and cite',['Rank permitted passages','Keep exact version anchors','Show uncertainty and gaps','Recheck old stored answers']),
        ('Review the answer',['Open permitted citations','Verify the source passage','Record a legal finding apart','External corpus is released'])],
        'A ranked answer does not establish complete diligence or lawyer approval. Missing evidence stays unknown.\nProvider-backed semantic search remains subject to processing policy and the shared cost cap.')

    internal=('firm',)
    for filename,title,desc in [
        ('Implemented_Schema_Fields.csv','Implemented schema fields','Code-derived table, column, type, key and nullability snapshot, with definition basis. No database rows.'),
        ('Implemented_Schema_Tables.csv','Implemented schema tables','Code-derived table inventory and field counts. Not proof of deployed migrations.')]:
        if (OUT/filename).exists():register(filename,title,desc,'API and schema',audiences=internal,status='Implemented model snapshot')
    for src,dest,title,desc in [
        ('08_Tech_Stack_and_Schema/Schema_Fields_Story_and_Linux_Portability.csv','Proposed_Schema_Fields.csv','Proposed schema fields with definitions','All 809 proposed fields, group meanings, definition basis and portability notes. Not implemented DDL.'),
        ('08_Tech_Stack_and_Schema/Schema_CSV_Column_Guide.csv','Schema_CSV_Column_Guide.csv','Schema CSV column guide','Explains the 21 headers in the proposed schema dictionary.'),
        ('08_Tech_Stack_and_Schema/Tech_Stack_and_Linux_Portability.csv','Tech_Stack_and_Linux_Portability.csv','Tech stack and Linux portability','Component versions, purpose, selection reasons and Windows-to-Linux migration work.'),
        ('08_Tech_Stack_and_Schema/Tech_Stack_and_Schema_Guide.docx','Tech_Stack_and_Schema_Guide.docx','Tech stack and schema story','Concise Word guide to the field families and portability limits.'),
        ('05_Schema/Schema_Groups.csv','Proposed_Schema_Groups.csv','Proposed schema groups','Definitions and counts of documentation domains. These are not account groups.'),
        ('05_Schema/Entity_Catalog.csv','Proposed_Entity_Catalog.csv','Proposed entity catalogue','Entity purpose and design domains in the proposed target schema.'),
        ('05_Schema/FK_Relationships.csv','Proposed_FK_Relationships.csv','Proposed foreign key relationships','Target schema relationship design; check actual migrations before implementation.')]:
        copy_asset(DELIVERABLES/src,dest,title,desc,'API and schema',audiences=internal,status='Proposed target design' if 'Proposed' in dest else 'Authored technical documentation')
    # Only authored deliverables; original supplied reference files are excluded.
    for folder in ['03_DDR_Checklist','04_VDR_Tracker']:
        for path in sorted((DELIVERABLES/folder).glob('*')):
            if path.is_file() and path.suffix in {'.xlsx','.docx','.pdf','.csv'}:
                copy_asset(path,path.name,path.stem.replace('_',' '),'Authored synthetic checklist or associate review tracker. Not an original Freshfields form.','Forms and trackers',audiences=internal)
    presentation=DELIVERABLES/'01_Presentation/Project_Kestrel_Plain_English_v3.pptx'
    if presentation.is_file():
        with zipfile.ZipFile(OUT/'Presentation_and_Companions.zip','w',zipfile.ZIP_DEFLATED) as archive:
            archive.write(presentation,'Project_Kestrel_Plain_English_v3.pptx')
            for path in sorted((presentation.parent/'companions').rglob('*')):
                if path.is_file() and not path.name.startswith('~$'):
                    archive.write(path,'companions/'+path.relative_to(presentation.parent/'companions').as_posix())
        register('Presentation_and_Companions.zip','Plain English presentation and companions','PPTX with speaker notes and its linked schema and tracker companions. Extract the folder before opening the presentation.','Guides',audiences=internal,status='Authored assessment presentation')
    for path in sorted((DELIVERABLES/'02_Partner_Note').glob('*')):
        if path.suffix.lower() in {'.docx','.pdf'}:
            copy_asset(path,path.name,'One page partner note '+path.suffix.lstrip('.').upper(),'Plain-language partner briefing from the written deliverables.','Guides',audiences=internal,status='Authored assessment note')
    (OUT/'catalog.json').write_text(json.dumps({'version':1,'updated':'2026-11-24','assets':CATALOG},indent=2),encoding='utf-8')
    docs=ROOT/'docs/resources';docs.mkdir(parents=True,exist_ok=True)
    links=['# Project resource library','', 'Authored documentation and fictional examples. Portal downloads require sign-in. Files in a public source repository are publicly readable.','']
    for category in dict.fromkeys(a['category'] for a in CATALOG):
        links += ['## '+category,'']
        links += [f"- [{a['title']}](../../backend/kestrel/data/resource_library/{a['filename']}) — {a['description']}" for a in CATALOG if a['category']==category]
        links += ['']
    (docs/'README.md').write_text('\n'.join(links),encoding='utf-8')
    from sync_diagram_resources import sync
    synchronized=sync(ROOT)
    print(json.dumps({'assets':synchronized or len(CATALOG),'categories':list(dict.fromkeys(a['category'] for a in CATALOG))}))


if __name__=='__main__':main()
