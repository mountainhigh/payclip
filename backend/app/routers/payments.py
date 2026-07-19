"""收款管理：列表/详情/新建/单条核对/批量核对/截图上传"""
import os
import uuid
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..database import get_db
from ..models import (User, PaymentRecord, PaymentBillAllocation, PaymentScreenshot,
                      Bill, CustomerPrepayment, Company, LedgerValidation, PrepaymentLog)
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
    # 关联账单详情（含账单年月、应收、已收、剩余）
    bill_ids = [a.bill_id for a in allocs]
    bill_map = {}
    if bill_ids:
        for b in db.query(Bill).filter(Bill.id.in_(bill_ids)).all():
            bill_map[b.id] = b
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
                                  "source": a.source,
                                  "bill_info": _bill_brief(bill_map.get(a.bill_id))} for a in allocs],
            "screenshots": [{"id": ss.id, "file_path": ss.file_path, "file_name": ss.file_name} for ss in screenshots]}


def _bill_brief(b):
    """账单简要信息（用于详情展示）"""
    if not b:
        return None
    return {"id": b.id, "bill_type": b.bill_type, "billing_year": b.billing_year,
            "billing_month": b.billing_month, "receivable_amount": float(b.receivable_amount),
            "paid_amount": float(b.paid_amount), "payment_status": b.payment_status,
            "remaining": float(b.receivable_amount - b.paid_amount)}


@router.get("")
def list_payments(company_id: int = None, verify_status: str = None,
                  year: int = None, month: int = None,
                  page: int = 1, page_size: int = 20,
                  user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(PaymentRecord)
    if user.tenant_id:
        q = q.filter(PaymentRecord.tenant_id == user.tenant_id)
    # tenant_admin 可查看所有收款记录；employee 按 data_scope 限制
    if user.role == "employee":
        if user.data_scope == "SELF":
            if check_permission(user, "payment:verify"):
                # 有核对权限的员工：看待核对自己的 + 自己提交的
                q = q.filter((PaymentRecord.assigned_verifier_id == user.id) |
                             (PaymentRecord.submitter_id == user.id))
            else:
                # 普通员工：只看自己提交的
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
    # 必选账单：至少分配一张账单（若无未结清账单，前端应先调用 /api/bills/generate 生成）
    allocs = body.get("bill_allocations", [])
    if not allocs:
        raise HTTPException(400, "请至少选择一张账单进行分配")
    # v3: 逐笔填报仅用于公司收款，强制 usage_type=public；私用仅批量导入流水场景产生（见 §4.8）
    p = PaymentRecord(tenant_id=user.tenant_id, company_id=body["company_id"],
                      amount=Decimal(str(body["amount"])), payment_date=pdate,
                      channel=body["channel"], submitter_id=user.id,
                      assigned_verifier_id=body["assigned_verifier_id"],
                      usage_type="public", remark=body.get("remark"))
    db.add(p)
    db.flush()
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
            db.add(PrepaymentLog(tenant_id=user.tenant_id, company_id=body["company_id"],
                                 change_type="in", amount=over, balance_after=prepay.balance,
                                 source="overpayment", payment_record_id=p.id,
                                 operator_id=user.id, remark="收款超额转入预付款"))
        else:
            db.add(CustomerPrepayment(tenant_id=user.tenant_id, company_id=body["company_id"],
                                      balance=over, source="overpayment"))
            db.add(PrepaymentLog(tenant_id=user.tenant_id, company_id=body["company_id"],
                                 change_type="in", amount=over, balance_after=over,
                                 source="overpayment", payment_record_id=p.id,
                                 operator_id=user.id, remark="收款超额转入预付款"))
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
    # tenant_admin 可核对所有收款；其他用户只能核对自己的
    if user.role != "tenant_admin" and p.assigned_verifier_id != user.id and user.data_scope != "ALL":
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


@router.put("/{pid}/allocations")
def update_allocations(pid: int, body: dict,
                       user: User = Depends(require_tenant_user),
                       db: Session = Depends(get_db)):
    if not check_permission(user, "payment:verify") and user.role != "tenant_admin":
        raise HTTPException(403, "权限不足")
    q = db.query(PaymentRecord).filter(PaymentRecord.id == pid)
    if user.tenant_id:
        q = q.filter(PaymentRecord.tenant_id == user.tenant_id)
    p = q.first()
    if not p:
        raise HTTPException(404, "收款记录不存在")
    # 待核对或已驳回都可以重新分配账单（驳回后重新提交场景）
    if p.verify_status not in ("pending", "rejected"):
        raise HTTPException(409, "仅待核对或已驳回状态可调整账单")
    lq = db.query(LedgerValidation).filter(
        LedgerValidation.ledger_year == p.payment_date.year,
        LedgerValidation.ledger_month == p.payment_date.month,
        LedgerValidation.status == "locked")
    if user.tenant_id:
        lq = lq.filter(LedgerValidation.tenant_id == user.tenant_id)
    if lq.first():
        raise HTTPException(409, "该月已锁定，无法调整账单")
    old_allocs = db.query(PaymentBillAllocation).filter(
        PaymentBillAllocation.payment_record_id == pid).all()
    p_amount = Decimal(str(p.amount))
    old_total = sum((a.allocation_amount for a in old_allocs), Decimal("0"))
    pq = db.query(CustomerPrepayment).filter(CustomerPrepayment.company_id == p.company_id)
    if user.tenant_id:
        pq = pq.filter(CustomerPrepayment.tenant_id == user.tenant_id)
    prepay = pq.first()
    if old_total < p_amount and prepay:
        prepay.balance -= (p_amount - old_total)
    for a in old_allocs:
        db.delete(a)
    total_alloc = Decimal("0")
    new_allocs = body.get("bill_allocations", [])
    if not new_allocs:
        raise HTTPException(400, "请至少选择一张账单进行分配")
    for a in new_allocs:
        amt = Decimal(str(a["allocation_amount"]))
        db.add(PaymentBillAllocation(tenant_id=user.tenant_id, payment_record_id=pid,
                                     bill_id=a["bill_id"], allocation_amount=amt))
        total_alloc += amt
    if total_alloc < p_amount:
        over = p_amount - total_alloc
        if prepay:
            prepay.balance += over
            db.add(PrepaymentLog(tenant_id=user.tenant_id, company_id=p.company_id,
                                 change_type="in", amount=over, balance_after=prepay.balance,
                                 source="overpayment", payment_record_id=p.id,
                                 operator_id=user.id, remark="调整账单后超额转入预付款"))
        else:
            db.add(CustomerPrepayment(tenant_id=user.tenant_id, company_id=p.company_id,
                                      balance=over, source="overpayment"))
            db.add(PrepaymentLog(tenant_id=user.tenant_id, company_id=p.company_id,
                                 change_type="in", amount=over, balance_after=over,
                                 source="overpayment", payment_record_id=p.id,
                                 operator_id=user.id, remark="调整账单后超额转入预付款"))
    db.commit()
    return {"code": 200, "message": "分配已更新"}


@router.post("/{pid}/resubmit")
def resubmit_payment(pid: int, body: dict,
                     user: User = Depends(require_tenant_user),
                     db: Session = Depends(get_db)):
    """驳回后重新提交：更新备注/账单分配，状态改为 pending"""
    if not check_permission(user, "payment:submit") and user.role != "tenant_admin":
        raise HTTPException(403, "权限不足")
    q = db.query(PaymentRecord).filter(PaymentRecord.id == pid)
    if user.tenant_id:
        q = q.filter(PaymentRecord.tenant_id == user.tenant_id)
    p = q.first()
    if not p:
        raise HTTPException(404, "收款记录不存在")
    if p.verify_status != "rejected":
        raise HTTPException(409, "仅已驳回的收款可重新提交")
    # 更新备注
    if "remark" in body:
        p.remark = body["remark"]
    # 清除驳回原因
    p.reject_reason = None
    p.verify_status = "pending"
    # 若提供了新的账单分配，更新分配
    new_allocs = body.get("bill_allocations")
    if new_allocs is not None:
        if not new_allocs:
            raise HTTPException(400, "请至少选择一张账单进行分配")
        old_allocs = db.query(PaymentBillAllocation).filter(
            PaymentBillAllocation.payment_record_id == pid).all()
        for a in old_allocs:
            db.delete(a)
        for a in new_allocs:
            amt = Decimal(str(a["allocation_amount"]))
            db.add(PaymentBillAllocation(tenant_id=user.tenant_id, payment_record_id=pid,
                                         bill_id=a["bill_id"], allocation_amount=amt))
    db.commit()
    return {"code": 200, "message": "已重新提交，等待核对"}


@router.post("/{pid}/void")
def void_payment(pid: int, user: User = Depends(require_tenant_user), db: Session = Depends(get_db)):
    """作废收款记录（仅 rejected 状态可作废）"""
    if not check_permission(user, "payment:submit") and user.role != "tenant_admin":
        raise HTTPException(403, "权限不足")
    q = db.query(PaymentRecord).filter(PaymentRecord.id == pid)
    if user.tenant_id:
        q = q.filter(PaymentRecord.tenant_id == user.tenant_id)
    p = q.first()
    if not p:
        raise HTTPException(404, "收款记录不存在")
    if p.verify_status != "rejected":
        raise HTTPException(409, "仅已驳回的收款可作废")
    # 删除关联的账单分配
    db.query(PaymentBillAllocation).filter(
        PaymentBillAllocation.payment_record_id == pid).delete()
    p.verify_status = "void"
    p.remark = (p.remark or "") + " | 已作废"
    db.commit()
    return {"code": 200, "message": "已作废"}


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
        # tenant_admin 可核对所有；其他用户只能核对自己的
        if user.role != "tenant_admin" and p.assigned_verifier_id != user.id and user.data_scope != "ALL":
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
