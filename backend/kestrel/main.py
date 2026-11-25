"""Local API plus separately owner-approved synthetic public runtime."""
import os
import time
import uuid
from sqlalchemy import text
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from kestrel.database import database_url, make_engine, factory
from kestrel.api.auth import router
from kestrel.deployment_settings import load_deployment
from kestrel.diagnostics import emit,activity


def create_app(engine=None):
    deployment=load_deployment()
    app = FastAPI(title='Project Kestrel API', version="0.3.0", docs_url=None, redoc_url=None,openapi_url=None)
    app.state.deployment=deployment
    app.state.sessions = factory(engine if engine is not None else make_engine(database_url()))

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        # Framework validation errors may echo submitted passwords/input.
        return JSONResponse({"detail": "Invalid request"}, status_code=422)

    @app.exception_handler(Exception)
    async def unavailable(request, exc):
        correlation_id=getattr(request.state,'correlation_id',str(uuid.uuid4()))
        emit('request.exception',correlation_id=correlation_id,exception=exc)
        activity('https','request.failed',failed=True,correlation_id=correlation_id)
        return JSONResponse({"detail": "Service unavailable", "correlation_id":correlation_id}, status_code=503,
                            headers={"Cache-Control": "no-store"})

    @app.middleware("http")
    async def local_only(request: Request, call_next):
        started=time.monotonic()
        request.state.correlation_id=str(uuid.uuid4())
        peer = request.client.host if request.client else ""
        if deployment.public and not getattr(request.state,'public_boundary',False):
            response = JSONResponse({"detail": "Trusted proxy required"}, status_code=403)
        elif not deployment.public and (request.url.hostname not in deployment.hosts or peer not in {"127.0.0.1", "::1", "testclient"}):
            response = JSONResponse({"detail": "Local portal denied"}, status_code=403)
        elif request.url.scheme != "https" and request.url.path.startswith("/api/"):
            response = JSONResponse({"detail": "Use HTTPS for authenticated APIs"},
                                    status_code=403 if request.cookies or request.url.path.endswith('/login') else 401)
        else:
            response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers['X-Correlation-ID']=request.state.correlation_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        if deployment.public:response.headers['Strict-Transport-Security']='max-age=86400'
        # Only the authenticated PDF preview explicitly opts into same-origin framing.
        response.headers.setdefault("Content-Security-Policy", "frame-ancestors 'none'")
        route=getattr(request.scope.get('route'),'path','unmatched')
        if not request.url.path.startswith(('/health','/assets','/swagger')):
            activity('https','request',failed=response.status_code>=500,method=request.method,status=response.status_code,
                route=route,duration_ms=round((time.monotonic()-started)*1000),correlation_id=request.state.correlation_id)
        return response

    @app.get("/health")
    def health():
        return {"status": "ok", "environment": "synthetic-public-demo" if deployment.public else "local-only", "protected_endpoints": "deny-by-default"}

    @app.get('/health/ready')
    def ready():
        try:
            with app.state.sessions() as db:
                db.execute(text('SELECT 1'))
                db.execute(text('SELECT id FROM vw_person_wall_entries WHERE 1=0'))
        except Exception as error:
            emit('readiness.database_failed',exception=error)
            return JSONResponse({'status':'unavailable'},status_code=503)
        return {'status':'ready'}

    app.include_router(router)
    from kestrel.api.trackers import router as trackers_router
    app.include_router(trackers_router)
    from kestrel.api.action_center import router as action_center_router
    app.include_router(action_center_router)
    from kestrel.api.profile import router as profile_router
    app.include_router(profile_router)
    from kestrel.api.administration import router as administration_router
    app.include_router(administration_router)
    from kestrel.api.integrations import router as integration_router
    app.include_router(integration_router)
    from kestrel.api.auditing import router as audit_router
    app.include_router(audit_router)
    from kestrel.api.governance import router as governance_router
    app.include_router(governance_router)
    from kestrel.api.resources import router as resources_router
    app.include_router(resources_router)
    from kestrel.api.resource_assets import router as resource_assets_router
    app.include_router(resource_assets_router)
    from kestrel.api.jobs import router as jobs_router
    app.include_router(jobs_router)
    from kestrel.api.workflow import router as workflow_router
    app.include_router(workflow_router)
    from kestrel.api.vdr_imports import router as vdr_router
    app.include_router(vdr_router)
    from kestrel.api.review_work import router as review_work_router
    app.include_router(review_work_router)
    from kestrel.api.review_clocks import router as review_clocks_router
    app.include_router(review_clocks_router)
    from kestrel.api.diligence import router as diligence_router
    app.include_router(diligence_router)
    from kestrel.api.reports import router as reports_router
    app.include_router(reports_router)
    from kestrel.api.ai_provider import router as ai_provider_router
    app.include_router(ai_provider_router)
    from kestrel.api.ocr import router as ocr_router
    app.include_router(ocr_router)
    from kestrel.api.processing_policy import router as processing_router
    app.include_router(processing_router)
    from kestrel.api.questions import router as questions_router
    app.include_router(questions_router)
    from kestrel.api.collaboration import router as collaboration_router
    app.include_router(collaboration_router)
    from kestrel.api.source_access import router as source_access_router
    app.include_router(source_access_router)
    from kestrel.api.client_uploads import router as client_uploads_router
    app.include_router(client_uploads_router)
    from kestrel.api.lifecycle import router as lifecycle_router
    app.include_router(lifecycle_router)
    from kestrel.api.archives import router as archives_router
    app.include_router(archives_router)
    from kestrel.api.wall_checker import router as wall_checker_router
    app.include_router(wall_checker_router)
    from kestrel.api.checklists import router as checklists_router
    app.include_router(checklists_router)
    from kestrel.api.checklist_records import router as checklist_records_router
    app.include_router(checklist_records_router)
    from kestrel.api.sla_alerts import router as sla_alerts_router
    app.include_router(sla_alerts_router)
    from kestrel.api.content_labels import router as content_labels_router
    app.include_router(content_labels_router)
    from kestrel.api.disclosures import router as disclosure_router
    app.include_router(disclosure_router)
    from kestrel.api.financial import router as financial_router
    app.include_router(financial_router)
    from kestrel.api.financial_context import router as financial_context_router
    app.include_router(financial_context_router)
    from kestrel.api.readers import router as readers_router
    app.include_router(readers_router)
    from kestrel.api.data_tables import router as tables_router
    app.include_router(tables_router)
    from kestrel.api.table_views import router as table_views_router
    app.include_router(table_views_router)
    from kestrel.api.intelligence import router as intelligence_router
    app.include_router(intelligence_router)
    from kestrel.api.source_attachments import router as source_attachments_router
    app.include_router(source_attachments_router)
    from kestrel.api.ddr import router as ddr_router
    app.include_router(ddr_router)
    from kestrel.api.agent_registry import router as agent_registry_router
    app.include_router(agent_registry_router)
    from kestrel.preview import install_preview
    install_preview(app)
    if deployment.public:
        from kestrel.public_boundary import PublicBoundary
        app.add_middleware(PublicBoundary,settings=deployment)
    return app


app = create_app()
