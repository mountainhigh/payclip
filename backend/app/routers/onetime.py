"""一次性业务管理"""
from decimal import Decimal
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import User, OneTimeProject, Bill
from ..core.auth import (get_current_user, check_permission, require_tenant_user,
                         require_write_access)
from ..utils import parse_date

router = APIRouter(prefix="/api/onetime-projects", tags=["一次性业务"])


def _serialize_ot(o, db):
    owner = db.query(User).filter(User.id == o.owner_id).first()
    return {"id": o.id, "company_id": o.company_id, "project_type": o.project_type,
            "revenue": float(o.revenue), "cost": float(o.cost),
            "gross_profit": float(o.revenue - o.cost),
            "supplier_id": o.supplier_id, "owner_id": o.owner_id,
            "owner_name": owner.name if owner else "",
            "completion_date": str(o.completion_date) if o.completion_date else None,
            "is_received": o.is_received,
            "receive_date": str(o.receive_date) if o.receive_date else None}


@router.get("")
def list_onetime(company_id: int = None, page: int = 1, page_size: int = 20,
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(OneTimeProject).filter(OneTimeProject.is_archived == False)
    if user.tenant_id:
        q = q.filter(OneTimeProject.tenant_id == user.tenant_id)
    if company_id:
        q = q.filter(OneTimeProject.company_id == company_id)
    total = q.count()
    items = q.offset((page-1)*page_size).limit(page_size).all()
    return {"code": 200, "data": {"items": [_serialize_ot(o, db) for o in items],
            "total": total, "page": page, "page_size": page_size}}


@router.post("")
def create_onetime(body: dict, user: User = Depends(require_tenant_user), db: Session = Depends(get_db)):
    if not (check_permission(user, "admin:config") or user.role == "tenant_admin"):
        raise HTTPException(403, "权限不足")
    o = OneTimeProject(tenant_id=user.tenant_id, company_id=body["company_id"],
                       project_type=body["project_type"], revenue=Decimal(str(body["revenue"])),
                       cost=Decimal(str(body.get("cost", 0))),
                       supplier_id=body.get("supplier_id"), owner_id=body["owner_id"],
                       completion_date=parse_date(body.get("completion_date")))
    db.add(o)
    db.flush()
    bill = Bill(tenant_id=user.tenant_id, company_id=body["company_id"],
                onetime_project_id=o.id, bill_type="onetime",
                billing_year=o.completion_date.year if o.completion_date else date.today().year,
                billing_month=o.completion_date.month if o.completion_date else date.today().month,
                receivable_amount=o.revenue - o.cost, follow_up_user_id=o.owner_id)
    db.add(bill)
    db.commit()
    return {"code": 200, "data": {"id": o.id}}


@router.put("/{oid}")
def update_onetime(oid: int, body: dict, user: User = Depends(require_write_access), db: Session = Depends(get_db)):
    if not (check_permission(user, "admin:config") or user.role == "tenant_admin"):
        raise HTTPException(403, "权限不足")
    q = db.query(OneTimeProject).filter(OneTimeProject.id == oid)
    if user.tenant_id:
        q = q.filter(OneTimeProject.tenant_id == user.tenant_id)
    o = q.first()
    if not o:
        raise HTTPException(404, "业务不存在")
    for f in ["project_type"]:
        if f in body: setattr(o, f, body[f])
    if "revenue" in body: o.revenue = Decimal(str(body["revenue"]))
    if "cost" in body: o.cost = Decimal(str(body["cost"]))
    db.commit()
    return {"code": 200, "message": "更新成功"}


@router.put("/{oid}/receive")
def receive_onetime(oid: int, body: dict, user: User = Depends(require_write_access), db: Session = Depends(get_db)):
    q = db.query(OneTimeProject).filter(OneTimeProject.id == oid)
    if user.tenant_id:
        q = q.filter(OneTimeProject.tenant_id == user.tenant_id)
    o = q.first()
    if not o:
        raise HTTPException(404, "业务不存在")
    o.is_received = True
    o.receive_date = parse_date(body.get("receive_date"))
    bq = db.query(Bill).filter(Bill.onetime_project_id == oid)
    if user.tenant_id:
        bq = bq.filter(Bill.tenant_id == user.tenant_id)
    bill = bq.first()
    if bill:
        bill.payment_status = "paid"
        bill.paid_amount = bill.receivable_amount
    db.commit()
    return {"code": 200, "message": "已标记收款"}
