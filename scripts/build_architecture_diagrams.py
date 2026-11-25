"""Build readable architecture SVGs and editable Mermaid from one specification.

Structure only: model CSVs are used without connecting to a database. PNGs are
rendered separately. Nothing in this build starts services or changes access.
"""
import csv
from collections import defaultdict
import hashlib
import html
import json
from pathlib import Path
import textwrap

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'diagrams'
LIBRARY=ROOT/'backend/kestrel/data/resource_library'
SPECS=[]


def add(number,folder,title,steps,note,evidence,status='CURRENT CODE',edges=None,positions=None):
    slug=f'{number:02d}_'+title.lower().replace(' ','_')
    nodes=[{'id':f'N{i+1}','title':heading,'lines':lines} for i,(heading,lines) in enumerate(steps)]
    if edges is None:edges=[(i,i+1,'') for i in range(1,len(nodes))]
    SPECS.append({'id':slug,'folder':folder,'title':title,'status':status,'nodes':nodes,
                  'edges':edges,'positions':positions,'note':note,'evidence':evidence})


def write_svg(spec):
    nodes=spec['nodes'];positions=spec.get('positions')
    for i,node in enumerate(nodes):
        row=i//3;col=(i%3 if row%2==0 else 2-i%3)
        if positions:col,row=positions[i]
        node.update(x=50+435*col,y=153+246*row,w=370,h=182)
    bottom=max(n['y']+n['h'] for n in nodes)
    foot=textwrap.wrap(spec['note'],width=140,break_long_words=False)
    height=bottom+70+len(foot)*22
    esc=html.escape
    svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="1340" height="{height}" viewBox="0 0 1340 {height}" role="img" aria-labelledby="title desc">',
         f'<title id="title">{esc(spec["title"])}</title><desc id="desc">{esc(spec["note"])}</desc>',
         f'<rect width="1340" height="{height}" fill="white"/>',
         '<defs><marker id="arrow" markerWidth="9" markerHeight="9" refX="7" refY="4" orient="auto"><path d="M0 0 L7 4 L0 8Z" fill="#59778A"/></marker></defs>',
         f'<text x="50" y="47" font-family="Arial,sans-serif" font-size="28" font-weight="700" fill="#153C52">{esc(spec["title"])}</text>',
         f'<text x="50" y="79" font-family="Arial,sans-serif" font-size="15" fill="#536C7B">{esc(spec["status"])}  |  Project Kestrel  |  Model and code snapshot 24 November 2026</text>',
         '<text x="50" y="112" font-family="Arial,sans-serif" font-size="15" fill="#536C7B">'+('Arrows point from a child foreign key to its parent table. Selected keys are shown; full detail is in the area ER views.' if spec.get('entity_view') else 'Arrows show the labelled workflow or dependency. Source code status is separate from deployment acceptance.')+'</text>']
    for source,target,label in spec['edges']:
        a,b=nodes[source-1],nodes[target-1]
        if a['y']==b['y']:
            forward=b['x']>a['x'];sx=a['x']+a['w'] if forward else a['x'];ex=b['x'] if forward else b['x']+b['w']
            sy=ey=a['y']+91;points=f'M{sx},{sy} L{ex},{ey}';lx=(sx+ex)/2;ly=sy-12
            if abs(a['x']-b['x'])>500:
                sx=a['x']+185;ex=b['x']+185;sy=ey=a['y'];mid=sy-14
                points=f'M{sx},{sy} L{sx},{mid} L{ex},{mid} L{ex},{ey}';lx=(sx+ex)/2;ly=mid-6
        elif a['x']==b['x']:
            down=b['y']>a['y'];sx=ex=a['x']+185;sy=a['y']+182 if down else a['y'];ey=b['y'] if down else b['y']+182
            points=f'M{sx},{sy} L{ex},{ey}';lx=sx+10;ly=(sy+ey)/2
        else:
            down=b['y']>a['y'];sx=a['x']+185;ex=b['x']+185;sy=a['y']+182 if down else a['y'];ey=b['y'] if down else b['y']+182
            mid=(sy+ey)/2;points=f'M{sx},{sy} L{sx},{mid} L{ex},{mid} L{ex},{ey}';lx=(sx+ex)/2;ly=mid-7
        dashed=' stroke-dasharray="6 4"' if 'proposed' in label.lower() else ''
        svg.append(f'<path d="{points}" fill="none" stroke="#59778A" stroke-width="2" marker-end="url(#arrow)"{dashed}/>')
        if label and not spec.get('entity_view'):
            labels=textwrap.wrap(label,width=10,break_long_words=True)
            w=max(len(line) for line in labels)*5.5+6;start=ly-(len(labels)-1)*13
            svg.append(f'<rect x="{lx-w/2}" y="{start-11}" width="{w}" height="{len(labels)*13+3}" fill="white"/>')
            for j,line in enumerate(labels):svg.append(f'<text x="{lx}" y="{start+j*13}" text-anchor="middle" font-family="Arial,sans-serif" font-size="10.5" fill="#365568">{esc(line)}</text>')
    colors=['#E8F2F7','#EEF2FA','#FFF5DF','#EAF5ED']
    for i,node in enumerate(nodes):
        x,y=node['x'],node['y'];color='#FFF4DF' if spec['status'].startswith('TARGET') else colors[(i//3)%4]
        svg.append(f'<rect x="{x}" y="{y}" width="370" height="182" rx="9" fill="{color}" stroke="#A8BFCD"/>')
        heading=textwrap.wrap(node['title'],width=30,break_long_words=False)
        for j,line in enumerate(heading):
            svg.append(f'<text x="{x+18}" y="{y+29+j*23}" font-family="Arial,sans-serif" font-size="18" font-weight="700" fill="#173F56">{esc(line)}</text>')
        line_y=y+57+(len(heading)-1)*23
        lines=[]
        for line in node['lines']:lines.extend(textwrap.wrap(line,width=40,break_long_words=False))
        if line_y+(len(lines)-1)*22>y+167:raise ValueError('Too much text: '+node['title'])
        for j,line in enumerate(lines):
            svg.append(f'<text x="{x+18}" y="{line_y+j*22}" font-family="Arial,sans-serif" font-size="16" fill="#294958">{esc(line)}</text>')
    for j,line in enumerate(foot):
        svg.append(f'<text x="50" y="{bottom+43+j*22}" font-family="Arial,sans-serif" font-size="15" fill="#3C596B">{esc(line)}</text>')
    svg.append('</svg>')
    folder=OUT/spec['folder'];folder.mkdir(parents=True,exist_ok=True)
    (folder/(spec['id']+'.svg')).write_text('\n'.join(svg),encoding='utf-8')
    mmd=['flowchart LR']
    for node in nodes:mmd.append(f'  {node["id"]}["'+esc(node['title'])+'<br/>'+'<br/>'.join(esc(line) for line in node['lines'])+'"]')
    for a,b,label in spec['edges']:mmd.append(f'  N{a} -->'+('|"'+label+'"|' if label else '')+f' N{b}')
    if spec.get('entity_view'):
        mmd=['erDiagram']
        for node in nodes:
            mmd.append('  '+node['title']+' {')
            mmd.extend('    string '+field for field in node['lines']);mmd.append('  }')
        for a,b,label in spec['edges']:
            mandatory='||' if spec.get('edge_nullable',{}).get(f'{a}:{label}',False) is False else '|o'
            mmd.append(f'  {nodes[b-1]["title"]} {mandatory}..o{{ {nodes[a-1]["title"]} : "{label}"')
    (folder/(spec['id']+'.mmd')).write_text('\n'.join(mmd)+'\n',encoding='utf-8')
    links='\n'.join(f'- `{path}`' for path in spec['evidence'])
    (folder/(spec['id']+'.md')).write_text(f'# {spec["title"]}\n\n**{spec["status"]}.** {spec["note"]}\n\n![{spec["title"]}]({spec["id"]}.svg)\n\n[PNG image]({spec["id"]}.png) · [Editable Mermaid]({spec["id"]}.mmd)\n\n## Evidence\n\n{links}\n',encoding='utf-8')


def domain(table):
    prefixes=[('agent_profile','07_agent_registry'),('ddr_','08_ddr_execution'),('financial_','09_financial_evidence'),
              ('intelligence_','10_review_intelligence'),('table_view','11_saved_views'),('tracker_','12_tracker_exchange'),
              ('vdr_','13_vdr_intake'),('disclosure_','06_sanitized_disclosures'),('checklist_','05_checklists'),
              ('review_','04_review_work'),('sla_','04_review_work'),('collaboration_','14_collaboration')]
    for prefix,name in prefixes:
        if table.startswith(prefix):return name
    if table in {'document_checklist_links'}:return '05_checklists'
    if table in {'source_findings','finding_reviews','legal_finding_revisions','finding_reconciliations','reconciliation_decisions'}:return '03_findings'
    if table.startswith(('governance_','impact_','ai_','analysis_','operation_','processing_','task_')):return '15_governance_and_analysis'
    if table.startswith(('document_','content_','ocr_','custodian_')) or table in {'documents','source_versions','source_embeddings','record_custodians'}:return '02_document_evidence'
    if table.startswith(('report_','release_','policy_')):return '16_reports_and_releases'
    if table.startswith(('lifecycle_','matter_lifecycle','source_archive','audit_')):return '17_lifecycle_and_audit'
    if table in {'client_submissions','submission_acceptances'}:return '14_collaboration'
    return '01_identity_and_access'


def data_views():
    with (LIBRARY/'Implemented_Schema_Fields.csv').open(encoding='utf-8-sig',newline='') as stream:fields=list(csv.DictReader(stream))
    tables=defaultdict(list)
    for field in fields:tables[field['table']].append(field)
    relationships=[]
    for field in fields:
        for reference in filter(None,field['foreign_keys'].split('; ')):
            parent,target=reference.rsplit('.',1)
            assert parent in tables and any(row['field']==target for row in tables[parent])
            one=field['unique']=='True' or field['primary_key']=='True' and sum(r['primary_key']=='True' for r in tables[field['table']])==1
            relationships.append({'child_table':field['table'],'child_field':field['field'],'parent_table':parent,'parent_field':target,'nullable':field['nullable'],'identifying':field['primary_key']=='True','reverse_max':'one' if one else 'many'})
    folder=OUT/'04_data';folder.mkdir(parents=True,exist_ok=True)
    with (folder/'all_foreign_key_relationships.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(relationships[0]));writer.writeheader();writer.writerows(relationships)
    grouped=defaultdict(list)
    for table in tables:grouped[domain(table)].append(table)
    index=['# Implemented data model','',f'This model snapshot contains **{len(tables)} tables, {len(fields)} columns and {len(relationships)} declared foreign keys**. It describes code structure, not an inspected deployed database. No row data was read.','',
           '[Readable data overview](16_the_data_story.md) · [Core entity relationships](18_core_entity_relationships.md) · [Complete foreign key CSV](all_foreign_key_relationships.csv)','',
           'The detailed views show primary and foreign key fields. Drawing types are simplified; exact declared types and other attributes remain in the [implemented field dictionary](../../backend/kestrel/data/resource_library/Implemented_Schema_Fields.csv). Cross-domain parent tables appear as key-only context. Cardinality uses nullability and single-column primary/unique flags. A solid identifying relationship means the child foreign key belongs to its primary key. Composite uniqueness and service rules still require the model and migrations. References inside JSON payloads are not invented as database foreign keys.','',
           '| Area | Owned tables | Relationship view |','|---|---:|---|']
    table_map=[]
    areas=folder/'areas';areas.mkdir(parents=True,exist_ok=True)
    for name,owned in sorted(grouped.items()):
        rels=[r for r in relationships if r['child_table'] in owned]
        parents={r['parent_table'] for r in rels};included=set(owned)|parents
        mmd=['erDiagram']
        for table in sorted(included):
            mmd.append(f'  {table} {{')
            for row in tables[table]:
                if row['primary_key']!='True' and (table not in owned or not row['foreign_keys']):continue
                kind='int' if row['type'].startswith('INTEGER') else 'boolean' if row['type']=='BOOLEAN' else 'string'
                keys=' PK, FK' if row['primary_key']=='True' and row['foreign_keys'] else ' PK' if row['primary_key']=='True' else ' FK' if row['foreign_keys'] else ''
                mmd.append(f'    {kind} {row["field"]}{keys}')
            mmd.append('  }')
        for rel in rels:
            mandatory='||' if rel['nullable']=='False' else '|o'
            connector='--' if rel['identifying'] else '..';reverse='o|' if rel['reverse_max']=='one' else 'o{'
            mmd.append(f'  {rel["parent_table"]} {mandatory}{connector}{reverse} {rel["child_table"]} : "{rel["child_field"]}"')
        source='\n'.join(mmd)+'\n';(areas/(name+'.mmd')).write_text(source,encoding='utf-8')
        title=name[3:].replace('_',' ').title()
        (areas/(name+'.md')).write_text(f'# {title}\n\nImplemented model snapshot. This area owns {len(owned)} tables. Key-only parent tables provide cross-area context.\n\n```mermaid\n{source}```\n\n[Editable Mermaid]({name}.mmd) · [All data views](../README.md)\n',encoding='utf-8')
        index.append(f'| {title} | {len(owned)} | [Open diagram](areas/{name}.md) |')
        table_map.extend({'table':table,'domain':title,'diagram':'areas/'+name+'.md','fields':len(tables[table])} for table in sorted(owned))
    (folder/'README.md').write_text('\n'.join(index)+'\n',encoding='utf-8')
    with (folder/'table_diagram_index.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(table_map[0]));writer.writeheader();writer.writerows(table_map)
    core=['organizations','accounts','matters','matter_assignments','documents','source_versions','document_sources','source_findings','legal_finding_revisions','document_policy_versions','release_packages','report_versions','release_approvals']
    core_fields={name:[r['field']+(' PK' if r['primary_key']=='True' else ' FK') for r in sorted(tables[name],key=lambda r:r['primary_key']!='True') if r['primary_key']=='True' or r['foreign_keys']][:5] for name in core}
    steps=[(name,core_fields[name]) for name in core]
    edges=[(core.index(r['child_table'])+1,core.index(r['parent_table'])+1,r['child_field']) for r in relationships if r['child_table'] in core and r['parent_table'] in core]
    add(18,'04_data','Core entity relationships',steps,
        'Solid arrows are declared foreign keys from child to parent. This is a selected core view; the 17 detailed area views cover every table. Report body_json and release references_json retain additional provenance that is not a declared foreign key.',
        ['backend/kestrel/models.py','backend/kestrel/data/resource_library/Implemented_Schema_Fields.csv'],edges=edges)
    # Core SVG uses a relationship matrix: exact links remain legible without a dense crossing-line poster.
    spec=SPECS[-1];spec['matrix']=True
    entities=['matters','accounts','matter_assignments','documents','document_sources','source_versions','legal_finding_revisions','source_findings','document_policy_versions','report_versions','release_packages','release_approvals']
    selected=[('matter_assignments','account_id'),('matter_assignments','matter_id'),('documents','matter_id'),('document_sources','document_id'),('document_sources','source_id'),('source_findings','source_id'),('legal_finding_revisions','candidate_id'),('source_findings','policy_id'),('report_versions','release_id'),('release_approvals','release_id'),('release_packages','policy_id')]
    selected_rels=[r for r in relationships if (r['child_table'],r['child_field']) in selected]
    assert len(selected_rels)==len(selected)
    node_fields=[]
    for name in entities:
        keys=[r for r in sorted(tables[name],key=lambda r:r['primary_key']!='True') if r['primary_key']=='True' or r['foreign_keys']][:4]
        node_fields.append((name,[r['field']+(' PK' if r['primary_key']=='True' else ' FK') for r in keys]))
    add(17,'04_data','Implemented core ERD',node_fields,
        'This visual ERD shows selected real foreign keys. Each arrow points from the child record to its referenced parent. Additional keys, optional links and all 153 tables are documented in the 17 area views and complete relationship CSV.',
        ['backend/kestrel/models.py','backend/kestrel/data/resource_library/Implemented_Schema_Fields.csv'],edges=[(entities.index(r['child_table'])+1,entities.index(r['parent_table'])+1,r['child_field']) for r in selected_rels],positions=[(i%3,i//3) for i in range(len(entities))])
    SPECS[-1]['entity_view']=True
    SPECS[-1]['edge_nullable']={f'{entities.index(r["child_table"])+1}:{r["child_field"]}':r['nullable']=='True' for r in selected_rels}
    text=(folder/'README.md').read_text(encoding='utf-8').replace('[Readable data overview](16_the_data_story.md)', '[Readable data overview](16_the_data_story.md) · [Visual core ERD](17_implemented_core_erd.md)')
    (folder/'README.md').write_text(text,encoding='utf-8')
    stats={'tables':len(tables),'fields':len(fields),'foreign_keys':len(relationships),'domains':len(grouped),
           'owned_tables':len(table_map),'model_sha256':hashlib.sha256((ROOT/'backend/kestrel/models.py').read_text(encoding='utf-8').encode('utf-8')).hexdigest(),
           'model_hash_encoding':'UTF-8 source with normalized LF line endings'}
    (folder/'model_provenance.json').write_text(json.dumps(stats,indent=2),encoding='utf-8')
    return stats


def matrix_svg(spec):
    # A compact exact relationship diagram, not a guessed chain between unrelated tables.
    with (OUT/'04_data/all_foreign_key_relationships.csv').open(encoding='utf-8-sig',newline='') as stream:all_rels=list(csv.DictReader(stream))
    core={node['title'] for node in spec['nodes']}
    rels=[r for r in all_rels if r['child_table'] in core and r['parent_table'] in core]
    w=1340;h=180+len(rels)*42+90;esc=html.escape
    svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}"><title>Core entity relationships</title>',f'<rect width="{w}" height="{h}" fill="white"/>',
         '<text x="45" y="47" font-family="Arial" font-size="28" font-weight="700" fill="#173F56">Core entity relationships</text>',
         '<text x="45" y="80" font-family="Arial" font-size="16" fill="#536C7B">Declared database links. Read each row from a child field to its parent key.</text>',
         '<text x="45" y="126" font-family="Arial" font-size="17" font-weight="700">Child table and foreign key</text>',
         '<text x="815" y="126" font-family="Arial" font-size="17" font-weight="700">Parent table and key</text>']
    for i,row in enumerate(rels):
        y=153+i*42;fill='#EDF4F8' if i%2==0 else '#F8FAFC'
        svg += [f'<rect x="35" y="{y-22}" width="1270" height="37" rx="3" fill="{fill}"/>',
                f'<text x="45" y="{y}" font-family="Arial" font-size="16" fill="#25495E">{esc(row["child_table"]+"."+row["child_field"])}</text>',
                f'<text x="727" y="{y}" font-family="Arial" font-size="20" fill="#25495E">→</text>',
                f'<text x="815" y="{y}" font-family="Arial" font-size="16" fill="#25495E">{esc(row["parent_table"]+"."+row["parent_field"])}</text>']
    svg.append(f'<text x="45" y="{h-44}" font-family="Arial" font-size="15" fill="#536C7B">Complete model: 153 tables and 442 foreign keys. Area ER diagrams and the relationship CSV provide full detail.</text></svg>')
    path=OUT/spec['folder']/(spec['id']+'.svg');path.write_text('\n'.join(svg),encoding='utf-8')
    # Keep a conventional ER view beside the readable exact-link matrix.
    relmmd=['erDiagram']
    for node in spec['nodes']:
        relmmd.append('  '+node['title']+' {')
        relmmd.extend('    string '+field for field in node['lines']);relmmd.append('  }')
    for r in rels:relmmd.append(f'  {r["parent_table"]} '+('||' if r['nullable']=='False' else '|o')+f'..o{{ {r["child_table"]} : "{r["child_field"]}"')
    (path.with_suffix('.mmd')).write_text('\n'.join(relmmd)+'\n',encoding='utf-8')
    page=path.with_suffix('.md');text=page.read_text(encoding='utf-8')
    text+='\n## Entity relationship view\n\nThe image above prioritizes exact readable links. This key-only ER view shows selected core entities; the area views contain every key. Reverse multiplicity is permissive and optional parent links depend on the detailed dictionary.\n\n```mermaid\n'+'\n'.join(relmmd)+'\n```\n'
    page.write_text(text,encoding='utf-8')


def main():
    add(1,'01_system','System context',[
        ('Seller data room',['Seller-hosted source system','Authorized CSV and folder intake','Originals remain source evidence']),
        ('Firm legal team',['Associates receive documents','Lawyers verify exact passages','Legal SMEs decide independently']),
        ('Kestrel review platform',['Versioned evidence and workflow','Review, reporting and audit','Shared permission checks']),
        ('Halden deal team',['Only released client packages','Named source grants are separate','Can ask questions and upload']),
        ('Castlegate advisers',['Only released commercial subset','No privileged internal advice','No general source access']),
        ('Technical administration',['Accounts and system settings','No blanket source privilege','No legal self-approval'])],
        'The platform is an independent synthetic demonstration. Enterprise VDR, identity, document-management and wall connections need firm-approved integrations.',
        ['docs/01_design/00_SOURCE_AND_SCOPE.md','backend/kestrel/services/auth.py'],edges=[(1,3,'intake'),(2,3,'review'),(3,4,'released only'),(3,5,'released only'),(6,3,'technical scope')],positions=[(0,0),(0,1),(1,1),(2,0),(2,2),(0,2)])
    add(2,'01_system','Application containers',[
        ('React browser application',['One TypeScript codebase','Host selects organization shell','Session cookies stay host-only']),
        ('Caddy reverse proxy',['Exact configured HTTPS hosts','Forward only to loopback API','Private proxy proof in public mode']),
        ('FastAPI application',['Typed request validation','Authenticated identity and CSRF','Shared policy and service layer']),
        ('PostgreSQL database',['Versioned business records','Durable jobs and decisions','Alembic schema migrations']),
        ('Background worker',['Scoped OCR and analysis jobs','Bounded DDR graph execution','Recheck authority for each stage']),
        ('Private retained artifacts',['Original versions and derivatives','Encrypted archive bindings','Opaque DDR checkpoints'])],
        'These are logical runtime components. The Azure deployment requires separate real-service, HTTPS and owner acceptance. Windows DPAPI and service identities need reviewed Linux replacements.',
        ['backend/kestrel/main.py','backend/kestrel/preview.py','deployment/azure/services/README.md'],edges=[(1,2,'HTTPS'),(2,3,'loopback'),(3,4,'records'),(4,5,'durable work'),(3,6,'authorized I/O'),(5,6,'scoped artifacts')])
    add(3,'01_system','Azure DNS and deployment',[
        ('GoDaddy DNS',['portal.ramijaloudi.com','firm, halden, castlegate and admin','Five exact A records; TTL 600']),
        ('Azure public address',['52.162.140.174','Windows VM network boundary','TCP ingress requires approval']),
        ('Shared Caddy gateway',['Exact SNI and Host checks','Kestrel loopback upstream','Preserve existing RPlus route']),
        ('Private application services',['FastAPI, worker and PostgreSQL','Separate service accounts','Protected local configuration']),
        ('TLS validation window',['Verify public certificate chain','Check all five names and redirects','Application can remain CLOSED']),
        ('Public application acceptance',['Genuine eight-check evidence','Independent owner approval','Explicit controlled activation'])],
        'DNS records are configured. This is the intended deployment and acceptance sequence, not a claim that public HTTPS or application activation is complete.',
        ['deployment/azure/README.md','backend/kestrel/deployment_settings.py'],status='CONFIGURED DNS / GATED DEPLOYMENT')
    add(4,'01_system','API architecture',[
        ('Organization portal',['Same-origin browser requests','Server session identifies person','CSRF protects state changes']),
        ('FastAPI routers',['Pydantic request contracts','Account and organization checks','OpenAPI grouped by capability']),
        ('Shared services and policy',['Matter, wall, label and source','Independent approval rules','Current audience entitlements']),
        ('Evidence and review APIs',['Intake, reader and findings','Checklists and review tasks','Financial evidence and disclosures']),
        ('Governance and report APIs',['Playbooks, impacts and registry','DDR runs and report versions','Separate release and audit']),
        ('Persistence and adapters',['SQLAlchemy and PostgreSQL','Private file and provider ports','Workers enforce fresh authority'])],
        'A known endpoint or visible API schema does not grant an operation. See the implemented model dictionaries for structure and the current OpenAPI contract for requests.',
        ['backend/kestrel/main.py','backend/kestrel/preview.py','backend/kestrel/api'],edges=[(1,2,''),(2,3,''),(3,4,'permitted'),(3,5,'permitted'),(4,6,''),(5,6,'')])
    add(5,'01_system','Authenticated request sequence',[
        ('Browser sends request',['HTTPS on the expected host','Session cookie with the request','CSRF token for a state change']),
        ('Boundary verifies request',['Check host and original client','Authenticate the current session','Reject invalid origin or token']),
        ('Service checks the object',['Recheck current source policy','Apply matter and audience limits','Require exact version authority']),
        ('Prepare the result',['Read or commit permitted records','Bind the result to exact content','Keep confidential data out of logs']),
        ('Check before returning',['Recheck authority for guarded output','Deny changed or revoked scope','Do not reuse old approval blindly']),
        ('Return and retain audit',['No-store protected responses','Only permitted content returned','Retain scoped audit metadata'])],
        'Specific services use their own transaction and recheck boundaries. This diagram describes the shared pattern, not a claim of one identical implementation on every endpoint.',
        ['backend/kestrel/services/auth.py','backend/kestrel/public_boundary.py','backend/kestrel/api/resource_assets.py'])
    add(6,'02_workflows','Document evidence lifecycle',[
        ('Receive and identify',['Associate checks the VDR batch','Retain document and source identity','Record version and content hash']),
        ('Extract and verify',['Retain exact original-language text','Use OCR for eligible scans','Verify transcripts before analysis']),
        ('Apply handling rules',['Source and passage labels','Matter, walls and clean-team scope','Custodian and party provenance']),
        ('Review and record findings',['Only authorized processing','AI candidates need lawyer review','Exact versions and citations retained']),
        ('Create audience products',['Draft reports from reviewed findings','Sanitized disclosures are separate','Independent approvals and release']),
        ('Retain the history',['Preserve prior versions and decisions','Signing snapshot and legal holds','Governed eligible-copy deletion'])],
        'A document is more than extracted data: its original bytes, provenance, access restrictions, evidence anchors and review history all matter. Receipt is separate from completed review.',
        ['backend/kestrel/models.py','backend/kestrel/services/workflow.py','backend/kestrel/services/disclosures.py'])
    add(7,'02_workflows','Permission first search',[
        ('Authorize the corpus',['Current identity and organization','Matter, walls and source labels','External corpus is released content']),
        ('Choose a supported mode',['Automatic defaults to lexical BM25','Internal semantic or hybrid is explicit','Financial mode uses typed facts']),
        ('Check provider permission',['No default model call for lexical','Semantic needs permitted processing','Apply shared provider cost limits']),
        ('Rank eligible evidence',['Search only permitted passages','Keep exact source-version anchors','Verify financial fact dimensions']),
        ('Present cited results',['Open only permitted citations','Mark missing or unknown evidence','AI prose remains unreviewed output']),
        ('Recheck retained answers',['Old answers do not preserve access','Revocation can deny stored results','Search is not complete diligence'])],
        'There is no general automatic four-engine fusion or universal reranking stage. Metadata grids and verified-financial filters are distinct supported paths. External semantic indexing is not enabled.',
        ['backend/kestrel/services/questions.py','docs/02_workflows/60_PERMISSION_FIRST_RETRIEVAL.md'])
    add(8,'02_workflows','DDR graph execution',[
        ('Coordinator',['Validate the retained run snapshot','Check source and profile authority','Apply deadline and call limits']),
        ('Contracts specialist',['Sole implemented specialist','Use authorized reviewed evidence','Retain typed output and usage']),
        ('Draft report stage',['Use retained specialist output','Keep exact source citations','Retain an unapproved version']),
        ('Citation validator',['Validate exact draft evidence','Runs alongside quality checking','Produces a retained result']),
        ('Quality review stage',['Independent AI quality result','Runs alongside citation checking','No authority to approve a report']),
        ('Join the check results',['Both required checks must pass','Failure creates follow-up work','No automatic revision loop']),
        ('Independent human review',['Retained task and human interrupt','Different cleared reviewer decides','Decision binds exact report hashes']),
        ('Internal completion',['Revalidate decision before resume','Approve or reject internally','Audience release remains separate'])],
        'The graph has coordinator, contracts, draft, quality, citations, join, review_task and human_gate nodes. A registry entry does not implement another specialist. Ambiguous live provider completion is not automatically resent.',
        ['backend/kestrel/ddr/graph.py','backend/kestrel/services/ddr_execution.py'],edges=[(1,2,''),(2,3,''),(3,4,'parallel'),(3,5,'parallel'),(4,6,''),(5,6,''),(6,7,'pass only'),(7,8,'decision')],positions=[(0,0),(1,0),(2,0),(2,1),(1,1),(1,2),(0,2),(0,3)])
    add(9,'02_workflows','Report review and release',[
        ('Select reviewed evidence',['Permitted lawyer-reviewed findings','Exact source and finding revisions','Coverage and open items retained']),
        ('Create a report version',['Draft prose and annex snapshots','Word draft for internal review','Keep report and content hashes']),
        ('Check quality and citations',['Verify the retained evidence','Fix through an explicit new version','Changed drafts need new review']),
        ('Independent internal decision',['Clearance and independence checked','Approve or reject the exact version','Record rationale and history']),
        ('Separate audience release',['Halden and Castlegate differ','Apply antitrust gate when required','No unreviewed external publication']),
        ('Download permitted package',['Recheck source and audience scope','Keep prior approved versions','Revocation cannot recall copies'])],
        'The former generic agent chain is replaced by the actual report and approval boundaries. AI checks do not replace lawyer or audience decisions.',
        ['backend/kestrel/services/reports.py','backend/kestrel/services/ddr_runs.py'])
    add(10,'02_workflows','Financial evidence and decisions',[
        ('Read a permitted source',['Original or approved transcript','Retain literal amount and anchor','Do not execute spreadsheet formulas']),
        ('Capture exact dimensions',['Entity, metric, period and currency','Scale and accounting context','Unknown dimensions stay unknown']),
        ('Independent verification',['Different cleared lawyer checks','Verify the number and dimensions','Original evidence remains retained']),
        ('Compare eligible facts',['Require matching dimensions','Use exact decimal arithmetic','No inferred FX conversion']),
        ('Retain a conflict decision',['Keep both conflicting facts','Independent source-cleared decision','Prefer a source or stay unresolved']),
        ('Release selected facts',['Approved sanitized source required','Independent fact release decision','Bank feature and item gates both apply'])],
        'This baseline does not implement a general financial analyst agent, broad automatic table recognition, or a valuation/materiality engine.',
        ['backend/kestrel/services/financial.py','docs/02_workflows/76_FINANCIAL_CONTEXT_AND_STAGING.md'])
    add(11,'02_workflows','Playbook change and approved rerun',[
        ('Author a replacement draft',['Version the playbook or profile','Retain exact change and tests','Technical author cannot self-approve']),
        ('Independent legal decision',['Authorized Legal SME reviews','Approve the exact revision','Publication is its own action']),
        ('Retain a material impact',['Identify affected source versions','Preserve prior findings and releases','Create protected tasks and notices']),
        ('Authorize an exact scope',['Independent cleared SME decides','Rationale and impact hash required','Reading a notice is not approval']),
        ('Queue the approved rerun',['Explicit idempotent queue action','Workers recheck current authority','New candidates or new draft run']),
        ('Review and release again',['Keep historical approved versions','Lawyers review new results','Separate audience decision again'])],
        'Publication does not silently rerun historic material, replace a reviewed finding or republish a client package.',
        ['backend/kestrel/services/action_center.py','backend/kestrel/services/agent_registry.py'])
    add(12,'03_security_operations','Access and audience boundaries',[
        ('Verify the person',['Active account and server session','Correct organization on the host','Roles are not supplied by headers']),
        ('Check current matter scope',['Assigned and permitted action','Ethical wall denial overrides','Named clean-team scope and expiry']),
        ('Check the exact source',['Document and passage restrictions','Processing permission when relevant','Current source-version entitlement']),
        ('Check the output decision',['Lawyer and report review','Audience-specific release','Separate antitrust gate if required']),
        ('Serve only allowed content',['Recheck guarded output','No-store downloads and responses','Safe denials and scoped audit']),
        ('Keep duties separate',['Admin has no blanket content right','Halden release is not bank release','Membership alone grants no source'])],
        'Each source or output retains its restrictions. The shared policy engine applies current access rather than trusting the portal, an old link, a cached result or an administrator title.',
        ['backend/kestrel/services/auth.py','backend/kestrel/services/policy.py','backend/kestrel/services/response_guard.py'])
    add(13,'03_security_operations','Sanitized source disclosure',[
        ('Propose exact redactions',['Permitted original and version','Exact Unicode ranges and rationale','Audience, purpose and expiry']),
        ('Independent plan review',['Different cleared lawyer decides','Whole-document review required','A preview is not sanitization']),
        ('Build a new transcript',['Reconstruct sanitized text as PDF','Exclude original metadata and objects','Validate the generated bytes']),
        ('Approve exact output',['Independent Legal SME decision','Additional antitrust gate if required','Bind decisions to retained hashes']),
        ('Release to a named audience',['Only the intended organization','Purpose and expiry are enforced','Native Word and Excel not released']),
        ('Recheck future access',['Source or approval changes can deny','Search uses released transcript units','Downloaded copies cannot be recalled'])],
        'This is a new text-only artifact workflow, not a claim that the original PDF, Word or spreadsheet has been safely redacted in place.',
        ['backend/kestrel/services/disclosures.py','docs/02_workflows/59_VALIDATED_SANITIZED_DISCLOSURES.md'])
    add(14,'03_security_operations','Durable work and failure handling',[
        ('Authorize and queue',['Exact immutable source and config','Idempotent request identity','No approval from queue membership']),
        ('Claim a bounded attempt',['Worker token and finite lease','Retain an attempt before producer','Recheck cancellation and expiry']),
        ('Run within the limits',['OCR or analysis or DDR stage','Fresh authority for source access','Provider budget and deadline checks']),
        ('Retain outcomes',['Typed result and content digest','Durable usage and state records','Private checkpoint references']),
        ('Pause an uncertain outcome',['Do not automatically resend paid work','Record safe failure and follow-up','Manual bounded recovery where allowed']),
        ('Complete through human gates',['Independent review where required','Release remains a separate workflow','Monitor and shut down explicitly'])],
        'The database supplies durable work records. Azure Service Bus, Redis or a managed orchestrator are not silently substituted into this demo.',
        ['backend/kestrel/services/ddr_execution.py','backend/kestrel/services/jobs.py'])
    add(15,'03_security_operations','Audit backup and retention',[
        ('Retain scoped audit',['Actor, action, time and object','Avoid confidential source passages','Export only permitted event scope']),
        ('Protect source archives',['Encrypted retained source bytes','Separate protected key bindings','Verify integrity before reading']),
        ('Test recovery separately',['Restore an isolated database','Check source and archive access','Keep actual recovery evidence']),
        ('Freeze the signing record',['Exact manifest and version bindings','Independent authorized decision','Operational history remains separate']),
        ('Apply holds and instructions',['Confirm retention obligations','Hold can block eligible copy deletion','No blanket client deletion promise']),
        ('Record authorized disposal',['Independent closing/security controls','Retain firm records where required','Do not delete audit history silently'])],
        'Local integrity evidence is not external WORM storage or proven disaster recovery. The Azure restore and service acceptance are separate live operations.',
        ['backend/kestrel/services/archives.py','backend/kestrel/services/lifecycle.py','docs/04_operations/43_BACKUP_ARCHIVE_AND_VERIFICATION.md'])
    add(16,'04_data','The data story',[
        ('People and matters',['organizations and accounts','matters and matter_assignments','wall and clean-team records']),
        ('Documents and evidence',['documents and document_sources','source_versions retain exact versions','Policy and evidence anchors persist']),
        ('Analysis and lawyer review',['source_findings are candidates','legal_finding_revisions retain review','Playbook and run versions bind results']),
        ('Reports and release',['report_versions retain body_json','release_packages retain references_json','release_approvals record decisions']),
        ('Operations and governance',['DDR attempts, artifacts and tasks','Impacts, notifications and reruns','Immutable decision histories']),
        ('Audit and lifecycle',['audit_events and source_archives','Signing snapshots and holds','Controlled eligible-copy deletion'])],
        'These arrows describe the business lifecycle, not a foreign key for every step. The next core entity diagram and 17 detailed model views show declared database relationships. The proposed 809-field design is separate.',
        ['backend/kestrel/models.py','backend/kestrel/data/resource_library/Implemented_Schema_Fields.csv'])
    add(19,'05_target_design','Enterprise integration boundaries',[
        ('Current synthetic application',['Local real accounts and policy','Authorized folder and CSV intake','Configured OpenAI path is governed']),
        ('Firm identity and walls',['Target Entra and Intapp integration','Firm-approved authoritative grants','Replace mock mappings with controls']),
        ('Firm document systems',['Target iManage and approved VDR','Confirm export and processing rights','Bind evidence to retained versions']),
        ('Approved collaboration',['Use existing approved channels first','External portal needs security review','No new client login promise on day one']),
        ('Approved AI and search',['Enterprise region and processing rules','Provider quality and cost acceptance','No inherited vendor entitlement']),
        ('Production operations',['Managed secrets, queue and storage','Independent security acceptance','Measured scale and recovery evidence'])],
        'The enterprise services shown are target integrations. The candidate does not claim working firm Entra, Intapp, iManage, M365 or enterprise AI connectivity.',
        ['docs/01_design/12_MOCK_INTEGRATIONS_AND_OPERATIONS.md','docs/01_design/00_SOURCE_AND_SCOPE.md'],status='TARGET DESIGN / NOT IMPLEMENTED CONNECTIONS')
    add(20,'05_target_design','Additional specialist roadmap',[
        ('Current governed baseline',['Coordinator and contracts specialist','Drafter, quality and citation checks','Human review and separate release']),
        ('Proposed specialist workstreams',['Corporate, employment and IP','Privacy and regulatory specialists','A financial analyst specialist']),
        ('Required implementation work',['Build real typed nodes and tools','Source permission and evidence checks','Budgets, deadlines and failure states']),
        ('Required quality evidence',['Counsel-labelled test evidence','Exact citation verification','Measure each specialist separately']),
        ('Governed synthesis proposal',['Preserve conflicting conclusions','Retain source and version lineage','No assumed automatic correction loop']),
        ('Independent adoption decision',['Legal and security acceptance','Versioned approved configurations','Human and audience gates still apply'])],
        'This replaces the old parallel-specialist image as a roadmap. Registering a role does not make it executable; only the implemented contracts specialist is claimed today.',
        ['backend/kestrel/ddr/graph.py','docs/05_validation/80_GATE_ACCEPTANCE_STATUS.md'],status='TARGET DESIGN / FUTURE SPECIALISTS')
    stats=data_views()
    for spec in SPECS:
        write_svg(spec)
        if spec.get('matrix'):matrix_svg(spec)
    catalogue=[]
    for spec in sorted(SPECS,key=lambda s:s['id']):
        catalogue.append({key:spec[key] for key in ['id','folder','title','status','note','evidence']})
    (OUT/'catalog.json').write_text(json.dumps({'diagrams':catalogue,'data_model':stats},indent=2),encoding='utf-8')
    lines=['# Architecture diagram library','',
           'Start with the system context, application containers and data story. Each diagram has a readable SVG, a PNG for slides, an editable Mermaid source and a short evidence page. **Current code**, **configured DNS** and **target design** are labelled separately.','',
           '| Order | Diagram | Status |','|---:|---|---|']
    lines += [f'| {item["id"][:2]} | [{item["title"]}]({item["folder"]}/{item["id"]}.md) | {item["status"]} |' for item in catalogue]
    lines += ['','## Data model','',f'[Open the complete data diagram index](04_data/README.md): {stats["tables"]} tables, {stats["fields"]} fields, {stats["foreign_keys"]} declared foreign keys, and {stats["domains"]} detailed area ER views. A table-to-diagram CSV makes every table findable.','',
              '## Earlier inputs','', '[Source archive and replacement map](99_source_archive/README.md) preserves the five supplied PNGs, the older presentation Mermaid files and earlier resource diagrams. These are dated inputs, not additional current architecture claims.','',
              '## Updating diagrams','', 'Edit `scripts/build_architecture_diagrams.py`, rebuild the SVG/Mermaid/evidence pages, then render PNGs with `scripts/render_architecture_diagrams.mjs`. Review the diagrams before updating the generated portal download copies. No database, service or Azure setting is changed by authoring diagrams.']
    (OUT/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({'architecture_diagrams':len(SPECS),**stats}))


if __name__=='__main__':main()
