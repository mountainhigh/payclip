"""报表：区域收款 / 成本构成 / 12 月趋势"""
import json
from datetime import date
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..database import get_db
from ..models import User, PaymentRecord, Company, Subscription, FeeHistory
from ..core.auth import get_current_user

router = APIRouter(prefix="/api/reports", tags=["报表中心"])


@router.get("/region")
def report_region(year: int, month: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    pq = db.query(PaymentRecord).filter(
        func.year(PaymentRecord.payment_date) == year, func.month(PaymentRecord.payment_date) == month,
        PaymentRecord.verify_status == "approved", PaymentRecord.usage_type == "public")
    if user.tenant_id:
        pq = pq.filter(PaymentRecord.tenant_id == user.tenant_id)
    payments = pq.all()
    regions = {}
    for p in payments:
        cq = db.query(Company).filter(Company.id == p.company_id)
        if user.tenant_id:
            cq = cq.filter(Company.tenant_id == user.tenant_id)
        c = cq.first()
        tags = json.loads(c.region_tags) if c and isinstance(c.region_tags, str) else (c.region_tags if c else [])
        for tag in tags:
            regions[tag] = regions.get(tag, 0) + float(p.amount)
    return {"code": 200, "data": [{"region": k, "amount": v} for k, v in regions.items()]}


@router.get("/cost")
def report_cost(year: int, month: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sq = db.query(Subscription).filter(Subscription.is_active == True, Subscription.is_archived == False, Subscription.is_cost_type == True)
    if user.tenant_id:
        sq = sq.filter(Subscription.tenant_id == user.tenant_id)
    subs = sq.all()
    cost_items = []
    for s in subs:
        fq = db.query(FeeHistory).filter(FeeHistory.subscription_id == s.id, FeeHistory.effective_date <= date(year, month, 1))
        if user.tenant_id:
            fq = fq.filter(FeeHistory.tenant_id == user.tenant_id)
        fees = fq.order_by(FeeHistory.effective_date.desc()).first()
        monthly = fees.new_fee if fees else s.monthly_fee
        cost_items.append({"type": s.service_type, "amount": float(monthly)})
    return {"code": 200, "data": cost_items}


@router.get("/trend")
def report_trend(end_year: int, end_month: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    result = []
    for i in range(11, -1, -1):
        y, m = end_year, end_month - i
        if m <= 0: y -= 1; m += 12
        tq = db.query(func.sum(PaymentRecord.amount)).filter(
            func.year(PaymentRecord.payment_date) == y, func.month(PaymentRecord.payment_date) == m,
            PaymentRecord.verify_status == "approved", PaymentRecord.usage_type == "public")
        if user.tenant_id:
            tq = tq.filter(PaymentRecord.tenant_id == user.tenant_id)
        total = tq.scalar() or 0
        result.append({"year": y, "month": m, "amount": float(total)})
    return {"code": 200, "data": result}
