"""This application's budget only; not an account-wide OpenAI billing limit."""
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from sqlalchemy import select,text,update
from kestrel.models import AIBudgetPeriod,AIReservation,OperationReservation
from kestrel.services.auth import clock

RUN_CENTS=200
MONTH_CENTS=1000

def period():return datetime.now(ZoneInfo('America/New_York')).strftime('%Y-%m')

def reserve(sessions,job_id,*,operation=False):
    model=OperationReservation if operation else AIReservation
    key="operation_id" if operation else "job_id"
    month=period()
    with sessions() as db:
        db.execute(text('INSERT INTO ai_budget_periods(period,spent_cents,reserved_cents) VALUES (:month,0,0) ON CONFLICT(period) DO NOTHING'),{'month':month})
        if db.get(model,job_id):raise HTTPException(409,'Live call already reserved; automatic provider retries are prohibited')
        changed=db.execute(update(AIBudgetPeriod).where(AIBudgetPeriod.period==month,
            AIBudgetPeriod.spent_cents+AIBudgetPeriod.reserved_cents+RUN_CENTS<=MONTH_CENTS)
            .values(reserved_cents=AIBudgetPeriod.reserved_cents+RUN_CENTS))
        if changed.rowcount!=1:raise HTTPException(429,'Monthly AI budget exhausted or reserved')
        db.add(model(**{key:job_id},period=month,reserved_cents=RUN_CENTS,created_at=clock()))
        db.commit()

def settle(sessions,job_id,input_tokens,output_tokens,*,operation=False):
    model=OperationReservation if operation else AIReservation
    column=model.operation_id if operation else model.job_id
    # Standard pinned GPT-5.4-mini pricing, conservatively ignoring cached-input discounts.
    if type(input_tokens) is not int or type(output_tokens) is not int or min(input_tokens,output_tokens)<0:
        raise HTTPException(409,'Provider usage unavailable; reservation retained')
    charge=(75*input_tokens+450*output_tokens+999999)//1000000
    if charge>RUN_CENTS:raise HTTPException(409,'Usage exceeds run cap; reservation retained for review')
    with sessions() as db:
        row=db.scalar(select(model).where(column==job_id).with_for_update())
        if row is None or row.state!='reserved':raise HTTPException(409,'Unsettled run reservation required')
        db.execute(update(AIBudgetPeriod).where(AIBudgetPeriod.period==row.period).values(
            reserved_cents=AIBudgetPeriod.reserved_cents-row.reserved_cents,spent_cents=AIBudgetPeriod.spent_cents+charge))
        row.state='settled';row.charged_cents=charge;db.commit()

def status(db):
    row=db.get(AIBudgetPeriod,period())
    return {'period':period(),'timezone':'America/New_York','run_limit_cents':RUN_CENTS,'month_limit_cents':MONTH_CENTS,
        'spent_estimate_cents':row.spent_cents if row else 0,'reserved_cents':row.reserved_cents if row else 0}


def reserve_aggregate(db,operation,limit_cents):
    """One graph reservation in the caller's locked transaction, never per node.

    Existing reservations are only reused for the same immutable operation. A
    settled aggregate cannot be reopened for a new paid invocation.
    """
    if operation.kind!='ddr_aggregate' or type(limit_cents) is not int or not 0<limit_cents<=RUN_CENTS:
        raise HTTPException(409,'Invalid aggregate run reservation')
    row=db.get(OperationReservation,operation.id)
    if row:
        if row.state!='reserved' or row.reserved_cents!=limit_cents:raise HTTPException(409,'Aggregate run reservation is closed or changed')
        return row
    month=period()
    db.execute(text('INSERT INTO ai_budget_periods(period,spent_cents,reserved_cents) VALUES (:month,0,0) ON CONFLICT(period) DO NOTHING'),{'month':month})
    changed=db.execute(update(AIBudgetPeriod).where(AIBudgetPeriod.period==month,
        AIBudgetPeriod.spent_cents+AIBudgetPeriod.reserved_cents+limit_cents<=MONTH_CENTS)
        .values(reserved_cents=AIBudgetPeriod.reserved_cents+limit_cents))
    if changed.rowcount!=1:raise HTTPException(429,'Monthly AI budget exhausted or reserved')
    row=OperationReservation(operation_id=operation.id,period=month,reserved_cents=limit_cents,created_at=clock())
    db.add(row);db.flush();return row


def settle_aggregate(db,operation,charge_cents):
    """Settle known whole-graph usage once; unknown completion never calls this."""
    row=db.scalar(select(OperationReservation).where(OperationReservation.operation_id==operation.id).with_for_update())
    if operation.kind!='ddr_aggregate' or not row or type(charge_cents) is not int or not 0<=charge_cents<=row.reserved_cents:
        raise HTTPException(409,'Known aggregate usage within its reservation required')
    if row.state=='settled':
        if row.charged_cents!=charge_cents:raise HTTPException(409,'Aggregate usage already bound to another charge')
        return row
    if row.state!='reserved':raise HTTPException(409,'Aggregate reservation unavailable')
    changed=db.execute(update(AIBudgetPeriod).where(AIBudgetPeriod.period==row.period,AIBudgetPeriod.reserved_cents>=row.reserved_cents)
        .values(reserved_cents=AIBudgetPeriod.reserved_cents-row.reserved_cents,spent_cents=AIBudgetPeriod.spent_cents+charge_cents))
    if changed.rowcount!=1:raise HTTPException(409,'Aggregate budget ledger inconsistent')
    row.state='settled';row.charged_cents=charge_cents
    return row


def settle_embeddings(sessions,operation_id,input_tokens):
    """Pinned text-embedding-3-small standard rate: 2 cents / million input tokens.

    Whole-cent ceiling is conservative. The same $2 reservation/$10 period is used.
    Never use this rate to settle a response-generation operation.
    """
    from kestrel.models import AIOperation
    if type(input_tokens) is not int or not 0<input_tokens<=64000:raise HTTPException(409,'Embedding usage unavailable or out of bounds; reservation retained')
    charge=(2*input_tokens+999999)//1000000
    with sessions() as db:
        operation=db.get(AIOperation,operation_id)
        row=db.scalar(select(OperationReservation).where(OperationReservation.operation_id==operation_id).with_for_update())
        if not operation or operation.kind!='semantic_retrieval' or not row or row.state!='reserved':raise HTTPException(409,'Matching unsettled embedding reservation required')
        if charge>row.reserved_cents:raise HTTPException(409,'Embedding estimate exceeds reservation')
        db.execute(update(AIBudgetPeriod).where(AIBudgetPeriod.period==row.period).values(reserved_cents=AIBudgetPeriod.reserved_cents-row.reserved_cents,spent_cents=AIBudgetPeriod.spent_cents+charge))
        row.state='settled';row.charged_cents=charge;db.commit()
