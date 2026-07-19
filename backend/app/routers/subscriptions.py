"""长期业务管理"""
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import User, Subscription, FeeHistory
from ..core.auth import (get_current_user, check_permission, require_tenant_user,
                         require_write_access)
from ..utils import parse_date

router = APIRouter(prefix="/api/subscriptions", tags=["长期业务"])


def _serialize_sub(s, db):
    owner = db.query(User).filter(User.id == s.service_owner_id).first()
    sales = db.query(User).filter(User.id == s.sales_owner_id).first() if s.sales_owner_id else None
    return {"id": s.id, "company_id": s.company_id, "service_type": s.service_type,
            "billing_period": s.billing_period, "monthly_fee": float(s.monthly_fee),
            "is_cost_type": s.is_cost_type, "monthly_cost": float(s.monthly_cost),
            "supplier_id": s.supplier_id, "service_owner_id": s.service_owner_id,
            "service_owner_name": owner.name if owner else "",
            "sales_owner_id": s.sales_owner_id,
            "sales_owner_name": sales.name if sales else "",
            "start_date": str(s.start_date) if s.start_date else None,
            "is_active": s.is_active}


@router.get("")
def list_subscriptions(company_id: int = None, page: int = 1, page_size: int = 20,
                       user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(Subscription).filter(Subscription.is_archived == False)
    if user.tenant_id:
        q = q.filter(Subscription.tenant_id == user.tenant_id)
    if company_id:
        q = q.filter(Subscription.company_id == company_id)
    total = q.count()
    items = q.offset((page-1)*page_size).limit(page_size).all()
    return {"code": 200, "data": {"items": [_serialize_sub(s, db) for s in items],
            "total": total, "page": page, "page_size": page_size}}


@router.post("")
def create_subscription(body: dict, user: User = Depends(require_tenant_user), db: Session = Depends(get_db)):
    if not (check_permission(user, "admin:config") or user.role == "tenant_admin"):
        raise HTTPException(403, "权限不足")
    s = Subscription(tenant_id=user.tenant_id, company_id=body["company_id"],
                     service_type=body["service_type"], billing_period=body["billing_period"],
                     monthly_fee=Decimal(str(body["monthly_fee"])),
                     is_cost_type=body.get("is_cost_type", False),
                     monthly_cost=Decimal(str(body.get("monthly_cost", 0))),
                     supplier_id=body.get("supplier_id"),
                     service_owner_id=body["service_owner_id"],
                     sales_owner_id=body.get("sales_owner_id"),
                     start_date=parse_date(body.get("start_date")))
    db.add(s)
    db.flush()
    fh = FeeHistory(tenant_id=user.tenant_id, subscription_id=s.id,
                    old_fee=Decimal("0"), new_fee=Decimal(str(body["monthly_fee"])),
                    effective_date=parse_date(body.get("start_date")), changed_by=user.id)
    db.add(fh)
    db.commit()
    return {"code": 200, "data": {"id": s.id}}


@router.put("/{sid}")
def update_subscription(sid: int, body: dict, user: User = Depends(require_write_access), db: Session = Depends(get_db)):
    if not (check_permission(user, "admin:config") or user.role == "tenant_admin"):
        raise HTTPException(403, "权限不足")
    q = db.query(Subscription).filter(Subscription.id == sid, Subscription.is_archived == False)
    if user.tenant_id:
        q = q.filter(Subscription.tenant_id == user.tenant_id)
    s = q.first()
    if not s:
        raise HTTPException(404, "业务不存在")
    for f in ["service_type","billing_period","is_cost_type"]:
        if f in body: setattr(s, f, body[f])
    for f_dec in ["monthly_fee","monthly_cost"]:
        if f_dec in body: setattr(s, f_dec, Decimal(str(body[f_dec])))
    for f_int in ["company_id","supplier_id","service_owner_id","sales_owner_id"]:
        if f_int in body: setattr(s, f_int, body[f_int])
    if "start_date" in body: s.start_date = parse_date(body["start_date"])
    db.commit()
    return {"code": 200, "message": "更新成功"}


@router.put("/{sid}/toggle")
def toggle_subscription(sid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(Subscription).filter(Subscription.id == sid)
    if user.tenant_id:
        q = q.filter(Subscription.tenant_id == user.tenant_id)
    s = q.first()
    if not s:
        raise HTTPException(404, "业务不存在")
    s.is_active = not s.is_active
    db.commit()
    return {"code": 200, "data": {"is_active": s.is_active}}


@router.post("/{sid}/fee-change")
def change_fee(sid: int, body: dict, user: User = Depends(require_write_access), db: Session = Depends(get_db)):
    if not (check_permission(user, "admin:config") or user.role == "tenant_admin"):
        raise HTTPException(403, "权限不足")
    q = db.query(Subscription).filter(Subscription.id == sid)
    if user.tenant_id:
        q = q.filter(Subscription.tenant_id == user.tenant_id)
    s = q.first()
    if not s:
        raise HTTPException(404, "业务不存在")
    old_fee = s.monthly_fee
    new_fee = Decimal(str(body["new_fee"]))
    eff_date = parse_date(body["effective_date"])
    s.monthly_fee = new_fee
    fh = FeeHistory(tenant_id=user.tenant_id, subscription_id=sid,
                    old_fee=old_fee, new_fee=new_fee, effective_date=eff_date, changed_by=user.id)
    db.add(fh)
    db.commit()
    return {"code": 200, "message": "月费已变更"}


@router.get("/{sid}/fee-history")
def get_fee_history(sid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(FeeHistory).filter(FeeHistory.subscription_id == sid)
    if user.tenant_id:
        q = q.filter(FeeHistory.tenant_id == user.tenant_id)
    items = q.order_by(FeeHistory.effective_date.desc()).all()
    return {"code": 200, "data": [{"id": f.id, "old_fee": float(f.old_fee), "new_fee": float(f.new_fee),
            "effective_date": str(f.effective_date)} for f in items]}
