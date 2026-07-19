"""账单管理"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import User, Bill, Subscription, Company, CustomerPrepayment, PaymentBillAllocation
from ..core.auth import get_current_user, check_permission, require_tenant_user

router = APIRouter(prefix="/api/bills", tags=["账单管理"])


def _serialize_bill(b, db):
    company = db.query(Company).filter(Company.id == b.company_id).first()
    return {"id": b.id, "company_id": b.company_id,
            "company_name": company.name if company else "",
            "subscription_id": b.subscription_id, "onetime_project_id": b.onetime_project_id,
            "bill_type": b.bill_type, "billing_year": b.billing_year, "billing_month": b.billing_month,
            "receivable_amount": float(b.receivable_amount), "paid_amount": float(b.paid_amount),
            "payment_status": b.payment_status, "is_overdue": b.is_overdue}


@router.get("")
def list_bills(company_id: int = None, year: int = None, month: int = None,
               status: str = None, page: int = 1, page_size: int = 20,
               user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(Bill)
    if user.tenant_id:
        q = q.filter(Bill.tenant_id == user.tenant_id)
    if company_id:
        q = q.filter(Bill.company_id == company_id)
    if year:
        q = q.filter(Bill.billing_year == year)
    if month:
        q = q.filter(Bill.billing_month == month)
    if status:
        q = q.filter(Bill.payment_status == status)
    total = q.count()
    items = q.order_by(Bill.id.desc()).offset((page-1)*page_size).limit(page_size).all()
    return {"code": 200, "data": {"items": [_serialize_bill(b, db) for b in items],
            "total": total, "page": page, "page_size": page_size}}


@router.get("/{bid}")
def get_bill(bid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(Bill).filter(Bill.id == bid)
    if user.tenant_id:
        q = q.filter(Bill.tenant_id == user.tenant_id)
    b = q.first()
    if not b:
        raise HTTPException(404, "账单不存在")
    return {"code": 200, "data": _serialize_bill(b, db)}


@router.post("/generate")
def generate_bills(body: dict, user: User = Depends(require_tenant_user), db: Session = Depends(get_db)):
    if not check_permission(user, "salary:manage") and user.role != "tenant_admin":
        raise HTTPException(403, "权限不足")
    year, month = body["year"], body["month"]
    count = 0
    sq = db.query(Subscription).filter(Subscription.is_active == True, Subscription.is_archived == False)
    if user.tenant_id:
        sq = sq.filter(Subscription.tenant_id == user.tenant_id)
    subs = sq.all()
    for sub in subs:
        eq = db.query(Bill).filter(Bill.subscription_id == sub.id, Bill.billing_year == year, Bill.billing_month == month)
        if user.tenant_id:
            eq = eq.filter(Bill.tenant_id == user.tenant_id)
        existing = eq.first()
        if existing:
            continue
        bill = Bill(tenant_id=user.tenant_id or sub.tenant_id, company_id=sub.company_id,
                    subscription_id=sub.id, bill_type="subscription",
                    billing_year=year, billing_month=month,
                    receivable_amount=sub.monthly_fee, follow_up_user_id=sub.service_owner_id)
        db.add(bill)
        pq = db.query(CustomerPrepayment).filter(CustomerPrepayment.company_id == sub.company_id, CustomerPrepayment.balance > 0)
        if user.tenant_id:
            pq = pq.filter(CustomerPrepayment.tenant_id == user.tenant_id)
        prepay = pq.first()
        if prepay:
            use = min(prepay.balance, bill.receivable_amount)
            bill.paid_amount = use
            bill.payment_status = "paid" if use >= bill.receivable_amount else "partial"
            prepay.balance -= use
            db.add(PaymentBillAllocation(tenant_id=user.tenant_id or sub.tenant_id,
                                         payment_record_id=None, bill_id=bill.id,
                                         allocation_amount=use, source="prepayment"))
        count += 1
    db.commit()
    return {"code": 200, "data": {"generated": count}}
