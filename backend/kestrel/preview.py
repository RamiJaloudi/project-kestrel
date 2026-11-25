"""Local static portals and offline Swagger: same origin, same API/policy."""
import copy
from pathlib import Path
from fastapi import HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import get_swagger_ui_html
from kestrel.deployment_settings import settings_for


def public_groups(actor):
    from kestrel.domain import Role as R
    base={'auth','portal','resources'}
    if actor.org.value!='firm':
        if not actor.roles&{R.CLIENT,R.BANK}:return base
        return base|{'financial','reports','trackers','disclosures','questions','collaboration','intelligence'}
    if actor.roles & {R.ROOT_ADMIN,R.LAWYER,R.SME,R.ANTITRUST}:return set(GROUPS)
    if actor.roles & {R.SECURITY}:return base|{'processing-policy','content-labels','lifecycle','audit'}
    if actor.roles & {R.CONFLICTS}:return base|{'ethical-walls','wall-checker','audit','validation'}
    return base|({'audit'} if actor.roles&{R.AUDITOR,R.CLEAN_AUDITOR} else set())


def swagger_access(request,group=None):
    if not settings_for(request).public:return None
    from kestrel.services import auth
    with request.app.state.sessions() as db:
        actor=auth.authenticate(db,request)[2];allowed=public_groups(actor)
        if group is not None and group not in allowed:raise HTTPException(403,'API explorer audience denied')
        return actor


def schema_for(app,request,group=None):
    actor=swagger_access(request,group);schema=copy.deepcopy(app.openapi())
    allowed=public_groups(actor) if actor else set(GROUPS)
    prefixes=[GROUPS[group]] if group else [GROUPS[key] for key in allowed]
    if actor is not None or group is not None:
        schema['paths']={p:value for p,value in schema['paths'].items() if any(p==prefix.rstrip('/') or p.startswith(prefix.rstrip('/')+'/') for prefix in prefixes)}
    if actor and actor.org.value!='firm':
        filtered={}
        for path,operations in schema['paths'].items():
            if '/api/v1/financial' in path and path not in {'/api/v1/financial/query','/api/v1/financial/compare'}:continue
            if '/api/v1/trackers' in path and '/exports' not in path:continue
            if '/api/v1/disclosures/plans' in path or '/api/v1/resources/playbooks/' in path or '/api/v1/resources/engines' in path:continue
            if '/api/v1/intelligence' in path and path!='/api/v1/intelligence/query':continue
            read_only=any(path.startswith('/api/v1/'+name) for name in ['reports','trackers','disclosures'])
            selected={method:operation for method,operation in operations.items() if not read_only or method=='get'}
            if selected:filtered[path]=selected
        schema['paths']=filtered
        # Omit unrelated component schemas instead of leaking the full internal
        # configuration catalogue through an external audience's filtered paths.
        components=schema.get('components',{}).get('schemas',{});needed=set()
        def references(value):
            if isinstance(value,dict):
                ref=value.get('$ref','')
                if ref.startswith('#/components/schemas/'):
                    name=ref.rsplit('/',1)[-1]
                    if name not in needed:needed.add(name);references(components.get(name,{}))
                for item in value.values():references(item)
            elif isinstance(value,list):
                for item in value:references(item)
        references(schema['paths']);schema.setdefault('components',{})['schemas']={k:v for k,v in components.items() if k in needed}
    fresh=swagger_access(request,group)
    if actor and (fresh.id!=actor.id or fresh.org!=actor.org or public_groups(fresh)!=allowed):raise HTTPException(403,'API explorer audience changed')
    return schema

GROUPS = {"financial-context":"/api/v1/financial-context", "agent-registry":"/api/v1/agent-registry", "ddr":"/api/v1/ddr", "intelligence":"/api/v1/intelligence", "table-views":"/api/v1/table-views", "tables":"/api/v1/tables", "readers":"/api/v1/readers", "financial":"/api/v1/financial", "disclosures":"/api/v1/disclosures", "content-labels":"/api/v1/content-labels", "checklist-records":"/api/v1/checklist-records", "sla-alerts":"/api/v1/sla-alerts", "review-clocks":"/api/v1/review-clocks", "review-work":"/api/v1/review-work", "vdr-imports":"/api/v1/vdr-imports", "checklists":"/api/v1/checklists", "trackers":"/api/v1/trackers", "action-center":"/api/v1/action-center", "wall-checker":"/api/v1/wall-checker", "archives":"/api/v1/archives", "lifecycle":"/api/v1/lifecycle", "client-uploads":"/api/v1/client-uploads", "source-access":"/api/v1/source-access", "collaboration":"/api/v1/collaboration", "questions":"/api/v1/questions", "processing-policy": "/api/v1/processing-policy", "ocr": "/api/v1/ocr", "ai-provider": "/api/v1/ai-provider", "reports": "/api/v1/reports", "diligence": "/api/v1/diligence", "workflow": "/api/v1/workflow", "auth": "/api/v1/auth/", "portal": "/api/v1/portal/",
          "jobs": "/api/v1/jobs", "audit": "/api/v1/audit/", "policy-editor": "/api/v1/policy-editor", "resources": "/api/v1/resources",
          "client-matter-validations": "/api/client-matter-validations", "ethical-walls": "/api/ethical-walls",
          "document-authorizations": "/api/v1/document-authorizations", "oauth": "/oauth/",
          "validation": "/api/v1/validation/",
          "admin": "/api/v1/admin/", "governance": "/api/v1/governance/"}


def install_preview(app):
    dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"

    @app.get('/launch-info',include_in_schema=False)
    def launch_info():
        return {'api_groups':list(GROUPS)}

    @app.get('/site-config',include_in_schema=False)
    def site_config(request:Request):return settings_for(request).site_config()

    @app.get('/openapi.json',include_in_schema=False)
    def full_schema(request:Request):return schema_for(app,request)

    @app.get("/docs", include_in_schema=False)
    @app.get("/docs/{group}", include_in_schema=False)
    def swagger(request: Request, group: str | None = None):
        if group is not None and group not in GROUPS:
            raise HTTPException(404, "API group not found")
        swagger_access(request,group)
        html = get_swagger_ui_html(
            openapi_url=f"/openapi/{group}.json" if group else "/openapi.json",
            title=f"Kestrel {group or 'all APIs'} — {request.url.hostname}",
            swagger_js_url="/swagger/swagger-ui-bundle.js", swagger_css_url="/swagger/swagger-ui.css",
            swagger_favicon_url="data:,",
            swagger_ui_parameters={"persistAuthorization": False, "withCredentials": True})
        # Same-origin Origin and CSRF header are supplied by the authenticated
        # portal, not a role/identity override. Never store CSRF in localStorage.
        page = html.body.decode().replace('<div id="swagger-ui">',
            '<p style="font:14px system-ui;padding:12px">'
            '<a href="/">Portals</a> · <a href="/portal">Account / login</a> · '
            '<a href="/docs">All APIs</a> · <a href="/docs/auth">Auth</a> · '
            '<a href="/portal?view=Resources&amp;resourceCategory=schema">Schema CSVs and definitions</a> · '
            '<a href="/docs/portal">Portal</a> · <a href="/docs/admin">Admin (closed)</a> · '
            '<a href="/docs/governance">Governance (closed)</a><br>'
            'One shared API. Closed workflows return denial. Sign in through Account / login '
            'and select Remember to reuse your sign-in here. State changes restore session CSRF automatically.</p><div id="swagger-ui">')
        page=page.replace('<script src="/swagger/swagger-ui-bundle.js">','<script src="/swagger-session.js"></script><script src="/swagger/swagger-ui-bundle.js">')
        page=page.replace('"withCredentials": true,','"withCredentials": true,\nrequestInterceptor: window.kestrelSwaggerRequest,')
        return HTMLResponse(page)

    @app.get('/swagger-session.js',include_in_schema=False)
    def swagger_session(request:Request):
        swagger_access(request)
        return FileResponse(Path(__file__).with_name('swagger_session.js'),media_type='application/javascript')

    @app.get("/openapi/{group}.json", include_in_schema=False)
    def group_schema(group: str,request:Request):
        if group not in GROUPS:
            raise HTTPException(404, "API group not found")
        schema = schema_for(app,request,group)
        schema["info"]["title"] = f"Kestrel — {group} API"
        return schema

    @app.get("/", include_in_schema=False)
    @app.get("/portal", include_in_schema=False)
    @app.get("/preview", include_in_schema=False)
    @app.get("/admin/validation", include_in_schema=False)
    def portal():
        if not (dist / "index.html").is_file():
            return HTMLResponse(f"<h1>Project Kestrel</h1><p>Frontend not built. Run START_KESTREL.bat.</p>", status_code=503)
        return FileResponse(dist / "index.html")

    app.mount("/assets", StaticFiles(directory=dist / "assets", check_dir=False), name="assets")
    app.mount("/swagger", StaticFiles(directory=dist / "swagger", check_dir=False), name="swagger-assets")



