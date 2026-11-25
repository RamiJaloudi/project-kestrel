"""Withhold prepared read responses when current authorization inputs change."""
from fastapi import HTTPException

def protected(db,request,actor,matter,operation,prepare,*,scope_check=None):
    from kestrel.services.data_tables import begin,finish,authorization_inputs
    from kestrel.services.auth import authenticate
    try:
        if scope_check is None:before,fresh=begin(db,request,matter)
        else:
            before=authorization_inputs(db,matter,authenticate(db,request)[2].id)
            db.expire_all();fresh=authenticate(db,request)[2];scope_check(fresh)
        result=prepare(fresh)
        if scope_check is None:finish(db,request,matter,before)
        else:
            db.expire_all();fresh=authenticate(db,request)[2];scope_check(fresh)
            if authorization_inputs(db,matter,fresh.id)!=before:raise HTTPException(409,'Authorization changed while preparing response')
        return result
    except HTTPException as error:
        if error.status_code in {401,403,409}:
            db.rollback()
            from kestrel.services.auth import audit
            audit(db,operation+'.denied','denied',actor.id,category='access');db.commit()
        raise


def member_check(matter):
    def check(actor):
        from kestrel.domain import member_and_not_walled
        if not member_and_not_walled(actor,matter):raise HTTPException(403,'Matter denied')
    return check
