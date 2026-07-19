"""收款管理：列表/详情/新建/单条核对/批量核对/截图上传"""
import os
import uuid
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..database import get_db
from ..models import (User, PaymentRecord, PaymentBillAllocation, PaymentScreenshot,
                      Bill, CustomerPrepayment, Company, LedgerValidation)
from ..core.auth import (get_current_user, check_permission, require_tenant_user)
from ..config import UPLOAD_DIR, ALLOWED_IMAGE_TYPES, MAX_UPLOAD_SIZE
from ..utils import parse_date

router = APIRouter(prefix="/api/payments", tags=["收款管理"])


def _serialize_payment(p, db):
    aq = db.query(PaymentBillAllocation).filter(PaymentBillAllocation.payment_record_id == p.id)
    if p.tenant_id:
        aq = aq.filter(PaymentBillAllocation.tenant_id == p.tenant_id)
    allocs = aq.all()
    company = db.query(Company).filter(Company.id == p.company_id).first()
    submitter = db.query(User).filter(User.id == p.submitter_id).first()
    verifier = db.query(User).filter(User.id == p.assigned_verifier_id).first()
    sq = db.query(PaymentScreenshot).filter(PaymentScreenshot.payment_record_id == p.id)
    if p.tenant_id:
        sq = sq.filter(PaymentScreenshot.tenant_id == p.tenant_id)
    screenshots = sq.all()
    return {"id": p.id, "company_id": p.company_id,
            "company_name": company.name if company else "",
            "amount": float(p.amount), "payment_date": str(p.payment_date),
            "channel": p.channel, "submitter_id": p.submitter_id,
            "submitter_name": submitter.name if submitter else "",
            "assigned_verifier_id": p.assigned_verifier_id,
            "verifier_name": verifier.name if verifier else "",
            "verify_status": p.verify_status, "reject_reason": p.reject_reason,
            "usage_type": p.usage_type, "remark": p.remark,
            "bill_allocations": [{"bill_id": a.bill_id, "allocation_amount": float(a.allocation_amount),
                                  "source": a.source} for a in allocs],
            "screenshots": [{"id": ss.id, "file_path": ss.file_path, "file_name": ss.file_name} for ss in screenshots]}


@router.get("")
def list_payments(company_id: int = None, verify_status: str = None,
                  year: int = None, month: int = None,
                  page: int = 1, page_size: int = 20,
                  user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(PaymentRecord)
    if user.tenant_id:
        q = q.filter(PaymentRecord.tenant_id == user.tenant_id)
    if user.data_scope == "SELF" and user.role == "employee":
        if check_permission(user, "payment:verify"):
            q = q.filter(PaymentRecord.assigned_verifier_id == user.id)
        else:
            q = q.filter(PaymentRecord.submitter_id == user.id)
    if company_id:
        q = q.filter(PaymentRecord.company_id == company_id)
    if verify_status:
        q = q.filter(PaymentRecord.verify_status == verify_status)
    if year and month:
        q = q.filter(func.year(PaymentRecord.payment_date) == year, func.month(PaymentRecord.payment_date) == month)
    total = q.count()
    items = q.order_by(PaymentRecord.id.desc()).offset((page-1)*page_size).limit(page_size).all()
    return {"code": 200, "data": {"items": [_serialize_payment(p, db) for p in items],
            "total": total, "page": page, "page_size": page_size}}


@router.get("/{pid}")
def get_payment(pid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(PaymentRecord).filter(PaymentRecord.id == pid)
    if user.tenant_id:
        q = q.filter(PaymentRecord.tenant_id == user.tenant_id)
    p = q.first()
    if not p:
        raise HTTPException(404, "收款记录不存在")
    return {"code": 200, "data": _serialize_payment(p, db)}


@router.post("")
def create_payment(body: dict, user: User = Depends(require_tenant_user), db: Session = Depends(get_db)):
    if not check_permission(user, "payment:submit") and user.role != "tenant_admin":
        raise HTTPException(403, "权限不足")
    pdate = parse_date(body["payment_date"])
    lq = db.query(LedgerValidation).filter(LedgerValidation.ledger_year == pdate.year,
         LedgerValidation.ledger_month == pdate.month, LedgerValidation.status == "locked")
    if user.tenant_id:
        lq = lq.filter(LedgerValidation.tenant_id == user.tenant_id)
    locked = lq.first()
    if locked:
        raise HTTPException(409, "该月已锁定，无法新增收款")
    p = PaymentRecord(tenant_id=user.tenant_id, company_id=body["company_id"],
                      amount=Decimal(str(body["amount"])), payment_date=pdate,
                      channel=body["channel"], submitter_id=user.id,
                      assigned_verifier_id=body["assigned_verifier_id"],
                      usage_type=body.get("usage_type", "public"), remark=body.get("remark"))
    db.add(p)
    db.flush()
    allocs = body.get("bill_allocations", [])
    total_alloc = Decimal("0")
    for a in allocs:
        amt = Decimal(str(a["allocation_amount"]))
        db.add(PaymentBillAllocation(tenant_id=user.tenant_id, payment_record_id=p.id,
                                     bill_id=a["bill_id"], allocation_amount=amt))
        total_alloc += amt
    p_amount = Decimal(str(body["amount"]))
    if total_alloc < p_amount:
        over = p_amount - total_alloc
        pq = db.query(CustomerPrepayment).filter(CustomerPrepayment.company_id == body["company_id"])
        if user.tenant_id:
            pq = pq.filter(CustomerPrepayment.tenant_id == user.tenant_id)
        prepay = pq.first()
        if prepay:
            prepay.balance += over
        else:
            db.add(CustomerPrepayment(tenant_id=user.tenant_id, company_id=body["company_id"],
                                      balance=over, source="overpayment"))
    db.commit()
    return {"code": 200, "data": {"id": p.id}}


@router.post("/{pid}/verify")
def verify_payment(pid: int, body: dict, user: User = Depends(require_tenant_user), db: Session = Depends(get_db)):
    if not check_permission(user, "payment:verify") and user.role != "tenant_admin":
        raise HTTPException(403, "权限不足")
    q = db.query(PaymentRecord).filter(PaymentRecord.id == pid)
    if user.tenant_id:
        q = q.filter(PaymentRecord.tenant_id == user.tenant_id)
    p = q.first()
    if not p:
        raise HTTPException(404, "收款记录不存在")
    if p.assigned_verifier_id != user.id and user.data_scope != "ALL" and user.role != "tenant_admin":
        raise HTTPException(403, "无权核对非自己的收款")
    action = body["action"]
    if action == "approve":
        p.verify_status = "approved"
        if p.usage_type == "public":
            aq = db.query(PaymentBillAllocation).filter(PaymentBillAllocation.payment_record_id == pid)
            if user.tenant_id:
                aq = aq.filter(PaymentBillAllocation.tenant_id == user.tenant_id)
            allocs = aq.all()
            for a in allocs:
                bill = db.query(Bill).filter(Bill.id == a.bill_id).first()
                if bill:
                    bill.paid_amount = Decimal(str(bill.paid_amount)) + a.allocation_amount
                    if bill.paid_amount >= bill.receivable_amount:
                        bill.payment_status = "paid"
                    elif bill.paid_amount > 0:
                        bill.payment_status = "partial"
    else:
        p.verify_status = "rejected"
        p.reject_reason = body.get("reject_reason", "")
    db.commit()
    return {"code": 200, "message": "核对完成"}


@router.post("/batch-verify")
def batch_verify(body: dict, user: User = Depends(require_tenant_user), db: Session = Depends(get_db)):
    if not check_permission(user, "payment:verify") and user.role != "tenant_admin":
        raise HTTPException(403, "权限不足")
    action = body["action"]
    for pid in body["ids"]:
        q = db.query(PaymentRecord).filter(PaymentRecord.id == pid)
        if user.tenant_id:
            q = q.filter(PaymentRecord.tenant_id == user.tenant_id)
        p = q.first()
        if not p:
            continue
        if p.assigned_verifier_id != user.id and user.data_scope != "ALL" and user.role != "tenant_admin":
            continue
        p.verify_status = "approved" if action == "approve" else "rejected"
        if action == "approve" and p.usage_type == "public":
            aq = db.query(PaymentBillAllocation).filter(PaymentBillAllocation.payment_record_id == pid)
            if user.tenant_id:
                aq = aq.filter(PaymentBillAllocation.tenant_id == user.tenant_id)
            allocs = aq.all()
            for a in allocs:
                bill = db.query(Bill).filter(Bill.id == a.bill_id).first()
                if bill:
                    bill.paid_amount = Decimal(str(bill.paid_amount)) + a.allocation_amount
                    bill.payment_status = "paid" if bill.paid_amount >= bill.receivable_amount else "partial"
    db.commit()
    return {"code": 200, "message": "批量核对完成"}


@router.post("/{pid}/screenshots")
async def upload_screenshot(pid: int, file: UploadFile = File(...),
                             user: User = Depends(require_tenant_user), db: Session = Depends(get_db)):
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(400, "仅支持 JPG/PNG 格式")
    contents = await file.read()
    if len(contents) > MAX_UPLOAD_SIZE:
        raise HTTPException(400, "文件超过5MB")
    q = db.query(PaymentScreenshot).filter(PaymentScreenshot.payment_record_id == pid)
    if user.tenant_id:
        q = q.filter(PaymentScreenshot.tenant_id == user.tenant_id)
    count = q.count()
    if count >= 3:
        raise HTTPException(400, "每条收款限3张截图")
    ext = file.filename.rsplit('.',1)[-1] if '.' in file.filename else 'jpg'
    fname = f"{uuid.uuid4().hex}.{ext}"
    fpath = os.path.join(UPLOAD_DIR, fname)
    with open(fpath, "wb") as f:
        f.write(contents)
    ss = PaymentScreenshot(tenant_id=user.tenant_id, payment_record_id=pid,
                          file_path=f"/uploads/{fname}", file_name=file.filename, file_size=len(contents))
    db.add(ss)
    db.commit()
    return {"code": 200, "data": {"id": ss.id, "file_path": ss.file_path}}
