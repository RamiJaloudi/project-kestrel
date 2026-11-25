from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,ConfigDict,Field
from kestrel.api.auth import identity,database
from kestrel.services.administration import require_admin
from kestrel.adapters import provider_secrets,openai_review
from kestrel.services.ai_budget import status
from kestrel.services.auth import audit
router=APIRouter(prefix='/api/v1/ai-provider',tags=['Private local AI provider settings'])
class Settings(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    api_key:str=Field(default='',max_length=512,repr=False,json_schema_extra={'format':'password','writeOnly':True})
    enabled:bool
@router.get('')
def get(actor=Depends(identity),db=Depends(database)):
    require_admin(actor[2]);enabled,key=openai_review.configuration()
    return {'enabled':enabled,'key_configured':bool(key),'model':openai_review.MODEL,'protection':'Windows DPAPI CurrentUser',**status(db)}
@router.post('')
def save(payload:Settings,actor=Depends(identity),db=Depends(database)):
    require_admin(actor[2])
    if payload.api_key and (not payload.api_key.startswith('sk-') or any(c.isspace() for c in payload.api_key)):raise HTTPException(422,'Enter a valid-format OpenAI API key')
    provider_secrets.save(payload.api_key,payload.enabled)
    audit(db,'ai_provider.configure','saved',actor[2].id,category='administrative');db.commit()
    return get(actor,db)
