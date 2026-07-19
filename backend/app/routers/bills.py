"""账单管理"""
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from io import BytesIO
from ..database import get_db
from ..models import (User, Company, Bill, Subscription, OneTimeProject,
                      CustomerPrepayment, PaymentBillAllocation, LedgerValidation,
                      PrepaymentLog)
from ..core.auth import get_current_user, check_permission, require_tenant_user, require_write_access
from ..utils import export_rows, parse_import_file, build_template

router = APIRouter(prefix="/api/bills", tags=["账单管理"])


BILL_FIELDS = [
    ("客户名称", "company_name"), ("账单类型", "bill_type"),
    ("账单年份", "billing_year"), ("账单月份", "billing_month"),
    ("应收金额", "receivable_amount"), ("已收金额", "paid_amount"),
    ("付款状态", "payment_status"),
]


def _find_company_by_name(db, tenant_id, name):
    if not name:
        return None
    q = db.query(Company).filter(Company.name == name, Company.is_archived == False)
    if tenant_id:
        q = q.filter(Company.tenant_id == tenant_id)
    c = q.first()
    return c.id if c else None


def _serialize_bill(b, db):
    company = db.query(Company).filter(Company.id == b.company_id).first()
    follow_up_user_name = None
    if b.follow_up_user_id:
        u = db.query(User).filter(User.id == b.follow_up_user_id).first()
        follow_up_user_name = u.name if u else None
    return {"id": b.id, "company_id": b.company_id,
            "company_name": company.name if company else "",
            "subscription_id": b.subscription_id, "onetime_project_id": b.onetime_project_id,
            "bill_type": b.bill_type, "billing_year": b.billing_year, "billing_month": b.billing_month,
            "receivable_amount": float(b.receivable_amount), "paid_amount": float(b.paid_amount),
            "payment_status": b.payment_status, "is_overdue": b.is_overdue,
            "follow_up_user_id": b.follow_up_user_id,
            "follow_up_user_name": follow_up_user_name}


@router.get("")
def list_bills(company_id: int = None, year: int = None, month: int = None,
               status: str = None, follow_up_user_id: int = None,
               page: int = 1, page_size: int = 20,
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
    if follow_up_user_id:
        q = q.filter(Bill.follow_up_user_id == follow_up_user_id)
    total = q.count()
    items = q.order_by(Bill.id.desc()).offset((page-1)*page_size).limit(page_size).all()
    return {"code": 200, "data": {"items": [_serialize_bill(b, db) for b in items],
            "total": total, "page": page, "page_size": page_size}}


# ==================== Excel 导入导出（必须在 /{bid} 之前注册，避免被动态路径拦截） ====================

def _bill_to_row(b, db):
    company = db.query(Company).filter(Company.id == b.company_id).first()
    return {
        "company_name": company.name if company else "",
        "bill_type": b.bill_type, "billing_year": b.billing_year, "billing_month": b.billing_month,
        "receivable_amount": float(b.receivable_amount), "paid_amount": float(b.paid_amount),
        "payment_status": b.payment_status,
    }


@router.get("/export")
def export_bills(company_id: int = None, year: int = None, month: int = None,
                 status: str = None, follow_up_user_id: int = None,
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
    if follow_up_user_id:
        q = q.filter(Bill.follow_up_user_id == follow_up_user_id)
    items = q.order_by(Bill.id.desc()).all()
    rows = [_bill_to_row(b, db) for b in items]
    xlsx_bytes = export_rows(rows, BILL_FIELDS, "账单列表")
    return StreamingResponse(BytesIO(xlsx_bytes),
                             media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": "attachment; filename=bills.xlsx"})


@router.get("/template")
def bill_template(user: User = Depends(get_current_user)):
    sample = {"company_name": "示例客户", "bill_type": "subscription",
              "billing_year": 2025, "billing_month": 7, "receivable_amount": 2000,
              "paid_amount": 0, "payment_status": "unpaid"}
    xlsx_bytes = build_template(BILL_FIELDS, "账单列表", sample)
    return StreamingResponse(BytesIO(xlsx_bytes),
                             media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": "attachment; filename=bill_template.xlsx"})


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
        # 业务负责人优先取客户的 business_owner_id（快照当时的客户业务负责人）；
        # 客户未设置时 fallback 到订阅的 service_owner_id（保持向后兼容）
        customer = db.query(Company).filter(Company.id == sub.company_id).first()
        follow_up_uid = None
        if customer and customer.business_owner_id:
            follow_up_uid = customer.business_owner_id
        else:
            follow_up_uid = sub.service_owner_id
        bill = Bill(tenant_id=user.tenant_id or sub.tenant_id, company_id=sub.company_id,
                    subscription_id=sub.id, bill_type="subscription",
                    billing_year=year, billing_month=month,
                    receivable_amount=sub.monthly_fee, follow_up_user_id=follow_up_uid)
        db.add(bill)
        db.flush()
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
            db.add(PrepaymentLog(tenant_id=user.tenant_id or sub.tenant_id,
                                 company_id=sub.company_id, change_type="out",
                                 amount=use, balance_after=prepay.balance,
                                 source="prepayment_use", bill_id=bill.id,
                                 remark=f"账单自动抵扣（{year}-{month:02d}）"))
        count += 1
    db.commit()
    return {"code": 200, "data": {"generated": count}}


@router.post("/generate-for-company")
def generate_bills_for_company(body: dict, user: User = Depends(require_tenant_user), db: Session = Depends(get_db)):
    """按客户+周期生成账单（需求10：收款填报时若客户没有账单，弹窗按周期生成）。
    body: {company_id, start_year, start_month, months}
    - months 为生成的月数，默认 1
    - 只生成该客户的所有有效订阅的账单（跳过已存在的）
    """
    if not (check_permission(user, "payment:submit") or check_permission(user, "salary:manage") or user.role == "tenant_admin"):
        raise HTTPException(403, "权限不足")
    company_id = body["company_id"]
    start_year = int(body["start_year"])
    start_month = int(body["start_month"])
    months = int(body.get("months", 1))
    if not (1 <= start_month <= 12 and 2020 <= start_year <= 2100 and 1 <= months <= 24):
        raise HTTPException(400, "参数无效")
    # 校验客户存在且属于当前租户
    cq = db.query(Company).filter(Company.id == company_id, Company.is_archived == False)
    if user.tenant_id:
        cq = cq.filter(Company.tenant_id == user.tenant_id)
    customer = cq.first()
    if not customer:
        raise HTTPException(404, "客户不存在")
    # 查询该客户的有效订阅
    sq = db.query(Subscription).filter(
        Subscription.company_id == company_id,
        Subscription.is_active == True, Subscription.is_archived == False)
    if user.tenant_id:
        sq = sq.filter(Subscription.tenant_id == user.tenant_id)
    subs = sq.all()
    count = 0
    follow_up_uid = customer.business_owner_id
    for i in range(months):
        total_month = (start_year * 12 + (start_month - 1)) + i
        y, m = total_month // 12, (total_month % 12) + 1
        # 该月是否已锁定
        lq = db.query(LedgerValidation).filter(
            LedgerValidation.ledger_year == y, LedgerValidation.ledger_month == m,
            LedgerValidation.status == "locked")
        if user.tenant_id:
            lq = lq.filter(LedgerValidation.tenant_id == user.tenant_id)
        if lq.first():
            continue
        for sub in subs:
            eq = db.query(Bill).filter(
                Bill.subscription_id == sub.id, Bill.billing_year == y, Bill.billing_month == m)
            if user.tenant_id:
                eq = eq.filter(Bill.tenant_id == user.tenant_id)
            if eq.first():
                continue
            fu = follow_up_uid or sub.service_owner_id
            bill = Bill(tenant_id=user.tenant_id or sub.tenant_id, company_id=company_id,
                        subscription_id=sub.id, bill_type="subscription",
                        billing_year=y, billing_month=m,
                        receivable_amount=sub.monthly_fee, follow_up_user_id=fu)
            db.add(bill)
            db.flush()
            # 优先抵扣预付款
            pq = db.query(CustomerPrepayment).filter(
                CustomerPrepayment.company_id == company_id, CustomerPrepayment.balance > 0)
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
                db.add(PrepaymentLog(tenant_id=user.tenant_id or sub.tenant_id,
                                     company_id=company_id, change_type="out",
                                     amount=use, balance_after=prepay.balance,
                                     source="prepayment_use", bill_id=bill.id,
                                     remark=f"账单自动抵扣（{y}-{m:02d}）"))
            count += 1
    db.commit()
    return {"code": 200, "data": {"generated": count}}


@router.post("/import")
async def import_bills(file: UploadFile = File(...),
                       user: User = Depends(require_write_access),
                       db: Session = Depends(get_db)):
    """批量导入账单（用于迁移历史账单；已锁定月份不允许导入）"""
    if not (check_permission(user, "salary:manage") or user.role == "tenant_admin"):
        raise HTTPException(403, "权限不足")
    contents = await file.read()
    try:
        rows = parse_import_file(contents, ["客户名称", "账单类型", "账单年份", "账单月份", "应收金额"])
    except ValueError as e:
        raise HTTPException(400, str(e))

    success = updated = created = 0
    errors = []
    for idx, row in enumerate(rows, start=2):
        try:
            cust_name = row.get("客户名称", "").strip()
            btype = row.get("账单类型", "").strip()
            if not cust_name:
                errors.append({"row": idx, "reason": "客户名称为空"}); continue
            if btype not in ("subscription", "onetime"):
                errors.append({"row": idx, "reason": f"账单类型必须是 subscription 或 onetime，实际为「{btype}」"}); continue
            try:
                byear = int(row.get("账单年份", 0))
                bmonth = int(row.get("账单月份", 0))
                if not (2020 <= byear <= 2100 and 1 <= bmonth <= 12):
                    raise ValueError()
            except (ValueError, TypeError):
                errors.append({"row": idx, "reason": "账单年份/月份格式错误"}); continue

            # 校验该月未锁定
            lq = db.query(LedgerValidation).filter(
                LedgerValidation.ledger_year == byear, LedgerValidation.ledger_month == bmonth,
                LedgerValidation.status == "locked")
            if user.tenant_id:
                lq = lq.filter(LedgerValidation.tenant_id == user.tenant_id)
            if lq.first():
                errors.append({"row": idx, "reason": f"{byear}-{bmonth} 已锁定，无法导入账单"}); continue

            company_id = _find_company_by_name(db, user.tenant_id, cust_name)
            if not company_id:
                errors.append({"row": idx, "reason": f"客户「{cust_name}」不存在"}); continue

            receivable = Decimal(str(row.get("应收金额", 0) or 0))
            paid = Decimal(str(row.get("已收金额", 0) or 0))
            pstatus = row.get("付款状态", "unpaid").strip() or "unpaid"
            if pstatus not in ("unpaid", "partial", "paid"):
                pstatus = "paid" if paid >= receivable else ("partial" if paid > 0 else "unpaid")

            existing = db.query(Bill).filter(
                Bill.company_id == company_id, Bill.bill_type == btype,
                Bill.billing_year == byear, Bill.billing_month == bmonth)
            if user.tenant_id:
                existing = existing.filter(Bill.tenant_id == user.tenant_id)
            existing = existing.first()

            data = {
                "company_id": company_id, "bill_type": btype,
                "billing_year": byear, "billing_month": bmonth,
                "receivable_amount": receivable, "paid_amount": paid,
                "payment_status": pstatus,
            }
            if existing:
                for k, v in data.items():
                    setattr(existing, k, v)
                updated += 1
            else:
                db.add(Bill(tenant_id=user.tenant_id, **data))
                created += 1
            success += 1
        except Exception as e:
            errors.append({"row": idx, "reason": str(e)})
    db.commit()
    return {"code": 200, "data": {"success_count": success, "updated_count": updated,
            "created_count": created, "errors": errors}}
