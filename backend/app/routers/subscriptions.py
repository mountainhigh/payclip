"""长期业务管理"""
from decimal import Decimal
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from io import BytesIO
from ..database import get_db
from ..models import (User, Company, Supplier, Subscription, FeeHistory, Bill,
                      CustomerPrepayment, PaymentBillAllocation, PrepaymentLog)
from ..core.auth import (get_current_user, check_permission, require_tenant_user,
                         require_write_access)
from ..utils import parse_date, export_rows, parse_import_file, build_template

router = APIRouter(prefix="/api/subscriptions", tags=["长期业务"])


SUBSCRIPTION_FIELDS = [
    ("客户名称", "customer_name"), ("业务类型", "service_type"),
    ("计费周期", "billing_period"), ("费用", "monthly_fee"),
    ("是否成本类型", "is_cost_type"), ("月成本", "monthly_cost"),
    ("供应商", "supplier_name"), ("服务负责人", "service_owner_name"),
    ("销售负责人", "sales_owner_name"), ("起始日期", "start_date"),
]


def _get_monthly_amount(fee, period):
    """根据计费周期计算每月应收金额。
    费用是指一个计费周期多少钱，每月应收=费用/周期月数
    """
    period_months = {
        "monthly": 1,
        "quarterly": 3,
        "half_year": 6,
        "yearly": 12,
    }
    months = period_months.get(period, 1)
    return fee / months


def _generate_yearly_bills(db, sub: Subscription, tenant_id: int):
    """为长期业务自动生成从起始月开始的一年（12 个月）账单。
    - 已存在的月份会跳过（按 subscription_id + 年 + 月 唯一）
    - 优先使用客户的 business_owner_id 作为 follow_up_user_id，否则用 sub.service_owner_id
    - 优先抵扣该客户的预付款余额
    - 费用是指一个计费周期多少钱，每月应收=费用/周期月数
    """
    if not sub.start_date:
        return 0
    start = sub.start_date
    customer = db.query(Company).filter(Company.id == sub.company_id).first()
    follow_up_uid = None
    if customer and customer.business_owner_id:
        follow_up_uid = customer.business_owner_id
    else:
        follow_up_uid = sub.service_owner_id

    monthly_amount = _get_monthly_amount(sub.monthly_fee, sub.billing_period)

    count = 0
    for i in range(12):
        total_month = (start.year * 12 + (start.month - 1)) + i
        y, m = total_month // 12, (total_month % 12) + 1
        eq = db.query(Bill).filter(
            Bill.subscription_id == sub.id,
            Bill.billing_year == y, Bill.billing_month == m)
        if tenant_id:
            eq = eq.filter(Bill.tenant_id == tenant_id)
        if eq.first():
            continue
        bill = Bill(tenant_id=tenant_id or sub.tenant_id, company_id=sub.company_id,
                    subscription_id=sub.id, bill_type="subscription",
                    billing_year=y, billing_month=m,
                    receivable_amount=monthly_amount, follow_up_user_id=follow_up_uid)
        db.add(bill)
        db.flush()
        pq = db.query(CustomerPrepayment).filter(
            CustomerPrepayment.company_id == sub.company_id,
            CustomerPrepayment.balance > 0)
        if tenant_id:
            pq = pq.filter(CustomerPrepayment.tenant_id == tenant_id)
        prepay = pq.first()
        if prepay:
            use = min(prepay.balance, bill.receivable_amount)
            bill.paid_amount = use
            bill.payment_status = "paid" if use >= bill.receivable_amount else "partial"
            prepay.balance -= use
            db.add(PaymentBillAllocation(tenant_id=tenant_id or sub.tenant_id,
                                         payment_record_id=None, bill_id=bill.id,
                                         allocation_amount=use, source="prepayment"))
            db.add(PrepaymentLog(tenant_id=tenant_id or sub.tenant_id,
                                 company_id=sub.company_id, change_type="out",
                                 amount=use, balance_after=prepay.balance,
                                 source="prepayment_use", bill_id=bill.id,
                                 remark=f"账单自动抵扣（{y}-{m:02d}）"))
        count += 1
    return count


def _find_user_by_name(db, tenant_id, name):
    if not name:
        return None
    q = db.query(User).filter(User.name == name, User.is_active == True)
    if tenant_id:
        q = q.filter(User.tenant_id == tenant_id)
    u = q.first()
    return u.id if u else None


def _find_company_by_name(db, tenant_id, name):
    if not name:
        return None
    q = db.query(Company).filter(Company.name == name, Company.is_archived == False)
    if tenant_id:
        q = q.filter(Company.tenant_id == tenant_id)
    c = q.first()
    return c.id if c else None


def _find_supplier_by_name(db, tenant_id, name):
    if not name:
        return None
    q = db.query(Supplier).filter(Supplier.name == name, Supplier.is_archived == False)
    if tenant_id:
        q = q.filter(Supplier.tenant_id == tenant_id)
    s = q.first()
    return s.id if s else None


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
            "is_active": s.is_active,
            "status_label": "启用" if s.is_active else "停止服务"}


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
    # 成本类型未选时不强制要求 supplier_id
    is_cost_type = body.get("is_cost_type", False)
    supplier_id = body.get("supplier_id") if is_cost_type else None
    s = Subscription(tenant_id=user.tenant_id, company_id=body["company_id"],
                     service_type=body["service_type"], billing_period=body["billing_period"],
                     monthly_fee=Decimal(str(body["monthly_fee"])),
                     is_cost_type=is_cost_type,
                     monthly_cost=Decimal(str(body.get("monthly_cost", 0))),
                     supplier_id=supplier_id,
                     service_owner_id=body["service_owner_id"],
                     sales_owner_id=body.get("sales_owner_id"),
                     start_date=parse_date(body.get("start_date")) or date.today())
    db.add(s)
    db.flush()
    fh = FeeHistory(tenant_id=user.tenant_id, subscription_id=s.id,
                    old_fee=Decimal("0"), new_fee=Decimal(str(body["monthly_fee"])),
                    effective_date=s.start_date, changed_by=user.id)
    db.add(fh)
    # 自动按月生成一年账单
    bills_count = _generate_yearly_bills(db, s, user.tenant_id)
    db.commit()
    return {"code": 200, "data": {"id": s.id, "bills_generated": bills_count}}


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
    for f in ["service_type","billing_period"]:
        if f in body: setattr(s, f, body[f])
    # 成本类型联动 supplier_id：is_cost_type=False 时清空 supplier_id
    if "is_cost_type" in body:
        s.is_cost_type = body["is_cost_type"]
        if not body["is_cost_type"]:
            s.supplier_id = None
    if "is_cost_type" in body and body["is_cost_type"] and "supplier_id" in body:
        s.supplier_id = body["supplier_id"]
    elif "supplier_id" in body and s.is_cost_type:
        s.supplier_id = body["supplier_id"]
    for f_dec in ["monthly_fee","monthly_cost"]:
        if f_dec in body: setattr(s, f_dec, Decimal(str(body[f_dec])))
    for f_int in ["company_id","service_owner_id","sales_owner_id"]:
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
    return {"code": 200, "data": {"is_active": s.is_active,
            "status_label": "启用" if s.is_active else "停止服务"}}


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
                    old_fee=old_fee, new_fee=new_fee, effective_date=eff_date,
                    changed_by=user.id)
    db.add(fh)
    # 同步更新生效日及之后未结清账单的应收金额
    if eff_date:
        bq = db.query(Bill).filter(
            Bill.subscription_id == sid,
            Bill.payment_status.in_(["unpaid", "partial", "overdue"]))
        if user.tenant_id:
            bq = bq.filter(Bill.tenant_id == user.tenant_id)
        for b in bq.all():
            bill_seq = b.billing_year * 12 + b.billing_month
            eff_seq = eff_date.year * 12 + eff_date.month
            if bill_seq >= eff_seq and b.paid_amount < b.receivable_amount:
                b.receivable_amount = new_fee
                # 重新计算状态
                if b.paid_amount >= new_fee:
                    b.payment_status = "paid"
                elif b.paid_amount > 0:
                    b.payment_status = "partial"
                else:
                    b.payment_status = "unpaid"
    db.commit()
    return {"code": 200, "message": "费用已变更"}


@router.get("/{sid}/fee-history")
def get_fee_history(sid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(FeeHistory).filter(FeeHistory.subscription_id == sid)
    if user.tenant_id:
        q = q.filter(FeeHistory.tenant_id == user.tenant_id)
    items = q.order_by(FeeHistory.effective_date.desc()).all()
    # 关联变更人姓名
    changer_ids = {f.changed_by for f in items if f.changed_by}
    changers = {u.id: u.name for u in db.query(User).filter(User.id.in_(changer_ids)).all()} if changer_ids else {}
    return {"code": 200, "data": [{"id": f.id, "old_fee": float(f.old_fee), "new_fee": float(f.new_fee),
            "effective_date": str(f.effective_date),
            "changed_by_name": changers.get(f.changed_by, ""),
            "created_at": f.created_at.strftime("%Y-%m-%d %H:%M:%S") if f.created_at else None}
            for f in items]}


# ==================== Excel 导入导出 ====================

def _subscription_to_row(s, db):
    company = db.query(Company).filter(Company.id == s.company_id).first()
    supplier = db.query(Supplier).filter(Supplier.id == s.supplier_id).first() if s.supplier_id else None
    owner = db.query(User).filter(User.id == s.service_owner_id).first()
    sales = db.query(User).filter(User.id == s.sales_owner_id).first() if s.sales_owner_id else None
    return {
        "customer_name": company.name if company else "",
        "service_type": s.service_type, "billing_period": s.billing_period,
        "monthly_fee": float(s.monthly_fee),
        "is_cost_type": "是" if s.is_cost_type else "否",
        "monthly_cost": float(s.monthly_cost or 0),
        "supplier_name": supplier.name if supplier else "",
        "service_owner_name": owner.name if owner else "",
        "sales_owner_name": sales.name if sales else "",
        "start_date": str(s.start_date) if s.start_date else "",
    }


@router.get("/export")
def export_subscriptions(company_id: int = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(Subscription).filter(Subscription.is_archived == False)
    if user.tenant_id:
        q = q.filter(Subscription.tenant_id == user.tenant_id)
    if company_id:
        q = q.filter(Subscription.company_id == company_id)
    items = q.order_by(Subscription.id.desc()).all()
    rows = [_subscription_to_row(s, db) for s in items]
    xlsx_bytes = export_rows(rows, SUBSCRIPTION_FIELDS, "长期业务")
    return StreamingResponse(BytesIO(xlsx_bytes),
                             media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": "attachment; filename=subscriptions.xlsx"})


@router.get("/template")
def subscription_template(user: User = Depends(get_current_user)):
    sample = {"customer_name": "示例客户", "service_type": "代理记账", "billing_period": "monthly",
              "monthly_fee": 2000, "is_cost_type": "否", "monthly_cost": 0,
              "supplier_name": "", "service_owner_name": "演示员工", "sales_owner_name": "",
              "start_date": "2026-01-01"}
    xlsx_bytes = build_template(SUBSCRIPTION_FIELDS, "长期业务", sample)
    return StreamingResponse(BytesIO(xlsx_bytes),
                             media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": "attachment; filename=subscription_template.xlsx"})


@router.post("/import")
async def import_subscriptions(file: UploadFile = File(...),
                               user: User = Depends(require_write_access),
                               db: Session = Depends(get_db)):
    if not (check_permission(user, "admin:config") or user.role == "tenant_admin"):
        raise HTTPException(403, "权限不足")
    contents = await file.read()
    try:
        rows = parse_import_file(contents, ["客户名称", "业务类型", "服务负责人"])
    except ValueError as e:
        raise HTTPException(400, str(e))

    success = updated = created = 0
    bills_generated = 0
    errors = []
    for idx, row in enumerate(rows, start=2):
        try:
            cust_name = row.get("客户名称", "").strip()
            svc_type = row.get("业务类型", "").strip()
            owner_name = row.get("服务负责人", "").strip()
            if not cust_name:
                errors.append({"row": idx, "reason": "客户名称为空"}); continue
            if not svc_type:
                errors.append({"row": idx, "reason": "业务类型为空"}); continue
            if not owner_name:
                errors.append({"row": idx, "reason": "服务负责人为空"}); continue

            company_id = _find_company_by_name(db, user.tenant_id, cust_name)
            if not company_id:
                errors.append({"row": idx, "reason": f"客户「{cust_name}」不存在"}); continue
            service_owner_id = _find_user_by_name(db, user.tenant_id, owner_name)
            if not service_owner_id:
                errors.append({"row": idx, "reason": f"服务负责人「{owner_name}」不存在"}); continue
            sales_name = row.get("销售负责人", "").strip()
            sales_owner_id = _find_user_by_name(db, user.tenant_id, sales_name)
            if sales_name and not sales_owner_id:
                errors.append({"row": idx, "reason": f"销售负责人「{sales_name}」不存在"}); continue
            # 是否成本类型：决定是否需要供应商
            is_cost_type = row.get("是否成本类型", "否").strip() in ("是", "true", "True", "1")
            supplier_name = row.get("供应商", "").strip() if is_cost_type else ""
            supplier_id = _find_supplier_by_name(db, user.tenant_id, supplier_name) if supplier_name else None
            if supplier_name and not supplier_id:
                errors.append({"row": idx, "reason": f"供应商「{supplier_name}」不存在"}); continue

            existing = db.query(Subscription).filter(
                Subscription.company_id == company_id, Subscription.service_type == svc_type,
                Subscription.is_archived == False)
            if user.tenant_id:
                existing = existing.filter(Subscription.tenant_id == user.tenant_id)
            existing = existing.first()

            # 兼容"费用"和"月费"两种表头
            fee_val = row.get("费用")
            if fee_val is None:
                fee_val = row.get("月费", 0)
            monthly_fee = Decimal(str(fee_val or 0))
            start_date = parse_date(row.get("起始日期")) or date.today()
            data = {
                "company_id": company_id, "service_type": svc_type,
                "billing_period": row.get("计费周期", "monthly").strip() or "monthly",
                "monthly_fee": monthly_fee,
                "is_cost_type": is_cost_type,
                "monthly_cost": Decimal(str(row.get("月成本", 0) or 0)),
                "supplier_id": supplier_id if is_cost_type else None,
                "service_owner_id": service_owner_id,
                "sales_owner_id": sales_owner_id,
                "start_date": start_date,
            }
            if existing:
                for k, v in data.items():
                    setattr(existing, k, v)
                updated += 1
            else:
                s = Subscription(tenant_id=user.tenant_id, **data)
                db.add(s); db.flush()
                fh = FeeHistory(tenant_id=user.tenant_id, subscription_id=s.id,
                                old_fee=Decimal("0"), new_fee=monthly_fee,
                                effective_date=start_date, changed_by=user.id)
                db.add(fh)
                # 自动按月生成一年账单
                bills_generated += _generate_yearly_bills(db, s, user.tenant_id)
                created += 1
            success += 1
        except Exception as e:
            errors.append({"row": idx, "reason": str(e)})
    db.commit()
    return {"code": 200, "data": {"success_count": success, "updated_count": updated,
            "created_count": created, "bills_generated": bills_generated, "errors": errors}}
