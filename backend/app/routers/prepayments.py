"""预付款明细：余额列表 + 变动流水 + 手动调整"""
from decimal import Decimal
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import (User, Company, CustomerPrepayment, PrepaymentLog,
                      PaymentRecord, Bill)
from ..core.auth import (get_current_user, check_permission, require_tenant_user,
                         require_write_access)
from ..utils import parse_date

router = APIRouter(prefix="/api/prepayments", tags=["预付款明细"])


def _serialize_prepayment(p, db):
    company = db.query(Company).filter(Company.id == p.company_id).first()
    return {"id": p.id, "company_id": p.company_id,
            "company_name": company.name if company else "",
            "balance": float(p.balance), "source": p.source,
            "remark": p.remark or "",
            "created_at": str(p.created_at) if p.created_at else "",
            "updated_at": str(p.updated_at) if p.updated_at else ""}


@router.get("")
def list_prepayments(keyword: str = "", page: int = 1, page_size: int = 20,
                     user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """预付款余额列表（按客户汇总）"""
    q = db.query(CustomerPrepayment)
    if user.tenant_id:
        q = q.filter(CustomerPrepayment.tenant_id == user.tenant_id)
    if keyword:
        company_ids = [c.id for c in db.query(Company.id).filter(
            Company.name.contains(keyword)).all()]
        if company_ids:
            q = q.filter(CustomerPrepayment.company_id.in_(company_ids))
        else:
            q = q.filter(CustomerPrepayment.id == -1)
    total = q.count()
    items = q.order_by(CustomerPrepayment.id.desc()).offset((page-1)*page_size).limit(page_size).all()
    return {"code": 200, "data": {"items": [_serialize_prepayment(p, db) for p in items],
            "total": total, "page": page, "page_size": page_size}}


@router.get("/{company_id}/logs")
def list_prepayment_logs(company_id: int,
                         user: User = Depends(get_current_user),
                         db: Session = Depends(get_db)):
    """指定客户的预付款变动流水"""
    q = db.query(PrepaymentLog).filter(PrepaymentLog.company_id == company_id)
    if user.tenant_id:
        q = q.filter(PrepaymentLog.tenant_id == user.tenant_id)
    items = q.order_by(PrepaymentLog.created_at.desc(), PrepaymentLog.id.desc()).all()
    result = []
    for log in items:
        operator = db.query(User).filter(User.id == log.operator_id).first() if log.operator_id else None
        company = db.query(Company).filter(Company.id == log.company_id).first()
        payment_info = None
        if log.payment_record_id:
            pay = db.query(PaymentRecord).filter(PaymentRecord.id == log.payment_record_id).first()
            if pay:
                payment_info = {
                    "id": pay.id, "amount": float(pay.amount),
                    "payment_date": str(pay.payment_date) if pay.payment_date else "",
                    "verify_status": pay.verify_status,
                    "channel": pay.channel,
                    "submitter_name": db.query(User).filter(User.id == pay.submitter_id).first().name if pay.submitter_id else ""
                }
        result.append({
            "id": log.id, "company_id": log.company_id,
            "company_name": company.name if company else "",
            "change_type": log.change_type, "amount": float(log.amount),
            "balance_after": float(log.balance_after), "source": log.source,
            "payment_record_id": log.payment_record_id,
            "payment_info": payment_info,
            "bill_id": log.bill_id,
            "operator_name": operator.name if operator else "",
            "remark": log.remark or "",
            "created_at": str(log.created_at) if log.created_at else "",
        })
    return {"code": 200, "data": result}


@router.post("/manual-adjust")
def manual_adjust(body: dict, user: User = Depends(require_tenant_user),
                  db: Session = Depends(get_db)):
    """手动调整预付款余额（增加或扣减）"""
    if not (check_permission(user, "admin:config") or user.role == "tenant_admin"):
        raise HTTPException(403, "权限不足")
    company_id = body["company_id"]
    amount = Decimal(str(body["amount"]))
    change_type = body.get("change_type", "in")
    if change_type not in ("in", "out"):
        raise HTTPException(400, "change_type 必须为 in 或 out")
    if amount <= 0:
        raise HTTPException(400, "调整金额必须大于0")

    q = db.query(CustomerPrepayment).filter(CustomerPrepayment.company_id == company_id)
    if user.tenant_id:
        q = q.filter(CustomerPrepayment.tenant_id == user.tenant_id)
    prepay = q.first()
    if not prepay:
        if change_type == "out":
            raise HTTPException(400, "该客户无预付款余额，不能扣减")
        prepay = CustomerPrepayment(tenant_id=user.tenant_id, company_id=company_id,
                                    balance=Decimal("0"), source="manual")
        db.add(prepay)
        db.flush()

    if change_type == "in":
        prepay.balance = Decimal(str(prepay.balance)) + amount
    else:
        if Decimal(str(prepay.balance)) < amount:
            raise HTTPException(400, f"扣减金额超出当前余额（{prepay.balance}）")
        prepay.balance = Decimal(str(prepay.balance)) - amount

    log = PrepaymentLog(tenant_id=user.tenant_id, company_id=company_id,
                        change_type=change_type, amount=amount,
                        balance_after=prepay.balance, source="manual",
                        operator_id=user.id, remark=body.get("remark", ""))
    db.add(log)
    db.commit()
    return {"code": 200, "data": {"balance": float(prepay.balance)}, "message": "已调整"}
