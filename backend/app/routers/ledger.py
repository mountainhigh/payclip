"""月结与提成计算引擎：校验计算/状态查询/撤销/核对明细"""
from datetime import datetime, date
from decimal import Decimal
from io import BytesIO
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import (LedgerValidation, User, Bill, Subscription, OneTimeProject,
                      CommissionDetail, MonthlySalary, PaymentRecord, Company,
                      PaymentBillAllocation)
from ..core.auth import get_current_user, check_permission, require_tenant_user
from ..utils import get_effective_fee, calc_supplement, in_sales_window, get_approved_allocations, export_rows

router = APIRouter(prefix="/api/ledger", tags=["月结计算"])


# ==================== 收款明细核对（计算前） ====================

PAYMENT_DETAIL_FIELDS = [
    ("客户名称", "company_name"), ("收款金额", "amount"),
    ("收款日期", "payment_date"), ("收款渠道", "channel_text"),
    ("填报人", "submitter_name"), ("核对人", "verifier_name"),
    ("核对状态", "verify_status_text"), ("驳回原因", "reject_reason"),
    ("备注", "remark"),
]

CHANNEL_MAP = {"bank": "银行转账", "alipay": "支付宝", "wechat": "微信", "cash": "现金"}
STATUS_MAP = {"approved": "已通过", "rejected": "已驳回", "pending": "待核对", "void": "已作废"}


# ==================== 账单明细核对（计算前，需求15：核对内容改为当月账期账单） ====================

BILL_DETAIL_FIELDS = [
    ("客户名称", "company_name"), ("账单类型", "bill_type_text"),
    ("账单年份", "billing_year"), ("账单月份", "billing_month"),
    ("应收金额", "receivable_amount"), ("已收金额", "paid_amount"),
    ("剩余应收", "remaining"), ("付款状态", "payment_status_text"),
    ("服务负责人", "service_owner_name"), ("销售负责人", "sales_owner_name"),
    ("跟进人", "follow_up_user_name"),
]

BILL_TYPE_MAP = {"subscription": "长期业务", "onetime": "一次性业务"}
PAYMENT_STATUS_MAP = {"unpaid": "未付", "partial": "部分付款", "paid": "已付", "overdue": "逾期"}


def _query_month_bills(db, tenant_id, year, month):
    """查询当月所有账单"""
    q = db.query(Bill).filter(Bill.billing_year == year, Bill.billing_month == month)
    if tenant_id:
        q = q.filter(Bill.tenant_id == tenant_id)
    return q.order_by(Bill.company_id, Bill.bill_type).all()


def _serialize_bill_detail(b, db, user_map, company_map, sub_map):
    """序列化账单详情（含服务负责人、销售负责人、跟进人）"""
    service_owner_name = ""
    sales_owner_name = ""
    if b.bill_type == "subscription" and b.subscription_id:
        sub = sub_map.get(b.subscription_id)
        if sub:
            service_owner_name = user_map.get(sub.service_owner_id, "")
            sales_owner_name = user_map.get(sub.sales_owner_id, "") if sub.sales_owner_id else ""
    elif b.bill_type == "onetime" and b.onetime_project_id:
        proj = db.query(OneTimeProject).filter(OneTimeProject.id == b.onetime_project_id).first()
        if proj:
            service_owner_name = user_map.get(proj.owner_id, "")
    follow_up_name = user_map.get(b.follow_up_user_id, "") if b.follow_up_user_id else ""
    return {
        "id": b.id, "company_id": b.company_id,
        "company_name": company_map.get(b.company_id, ""),
        "bill_type": b.bill_type, "bill_type_text": BILL_TYPE_MAP.get(b.bill_type, b.bill_type),
        "billing_year": b.billing_year, "billing_month": b.billing_month,
        "receivable_amount": float(b.receivable_amount), "paid_amount": float(b.paid_amount),
        "remaining": float(b.receivable_amount - b.paid_amount),
        "payment_status": b.payment_status,
        "payment_status_text": PAYMENT_STATUS_MAP.get(b.payment_status, b.payment_status),
        "subscription_id": b.subscription_id, "onetime_project_id": b.onetime_project_id,
        "follow_up_user_id": b.follow_up_user_id,
        "follow_up_user_name": follow_up_name,
        "service_owner_name": service_owner_name,
        "sales_owner_name": sales_owner_name,
    }


@router.get("/pre-calc-bills")
def pre_calc_bills(year: int, month: int,
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """计算前：查看当月所有账单明细 + 付款状态汇总（需求15：核对内容改为当月账期账单）"""
    bills = _query_month_bills(db, user.tenant_id, year, month)
    # 预加载用户名、公司名、订阅信息
    follow_up_ids = {b.follow_up_user_id for b in bills if b.follow_up_user_id}
    company_ids = {b.company_id for b in bills}
    sub_ids = {b.subscription_id for b in bills if b.subscription_id}
    user_map = {u.id: u.name for u in db.query(User).filter(User.id.in_(follow_up_ids)).all()} if follow_up_ids else {}
    company_map = {c.id: c.name for c in db.query(Company).filter(Company.id.in_(company_ids)).all()} if company_ids else {}
    sub_map = {s.id: s for s in db.query(Subscription).filter(Subscription.id.in_(sub_ids)).all()} if sub_ids else {}
    # 补充订阅的 service_owner_id / sales_owner_id 到 user_map
    extra_user_ids = set()
    for s in sub_map.values():
        if s.service_owner_id: extra_user_ids.add(s.service_owner_id)
        if s.sales_owner_id: extra_user_ids.add(s.sales_owner_id)
    if extra_user_ids:
        for u in db.query(User).filter(User.id.in_(extra_user_ids)).all():
            user_map[u.id] = u.name
    items = [_serialize_bill_detail(b, db, user_map, company_map, sub_map) for b in bills]
    summary = {
        "total": len(items),
        "unpaid": sum(1 for i in items if i["payment_status"] == "unpaid"),
        "partial": sum(1 for i in items if i["payment_status"] == "partial"),
        "paid": sum(1 for i in items if i["payment_status"] == "paid"),
        "total_receivable": sum(i["receivable_amount"] for i in items),
        "total_paid": sum(i["paid_amount"] for i in items),
        "total_remaining": sum(i["remaining"] for i in items),
    }
    lv = db.query(LedgerValidation).filter(
        LedgerValidation.ledger_year == year, LedgerValidation.ledger_month == month)
    if user.tenant_id:
        lv = lv.filter(LedgerValidation.tenant_id == user.tenant_id)
    lv = lv.first()
    summary["is_locked"] = bool(lv and lv.status == "locked")
    summary["calculation_status"] = lv.calculation_status if lv else "idle"
    return {"code": 200, "data": {"items": items, "summary": summary}}


@router.get("/pre-calc-bills-export")
def pre_calc_bills_export(year: int, month: int,
                          user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """计算前：导出当月账单明细 Excel"""
    bills = _query_month_bills(db, user.tenant_id, year, month)
    follow_up_ids = {b.follow_up_user_id for b in bills if b.follow_up_user_id}
    company_ids = {b.company_id for b in bills}
    sub_ids = {b.subscription_id for b in bills if b.subscription_id}
    user_map = {u.id: u.name for u in db.query(User).filter(User.id.in_(follow_up_ids)).all()} if follow_up_ids else {}
    company_map = {c.id: c.name for c in db.query(Company).filter(Company.id.in_(company_ids)).all()} if company_ids else {}
    sub_map = {s.id: s for s in db.query(Subscription).filter(Subscription.id.in_(sub_ids)).all()} if sub_ids else {}
    extra_user_ids = set()
    for s in sub_map.values():
        if s.service_owner_id: extra_user_ids.add(s.service_owner_id)
        if s.sales_owner_id: extra_user_ids.add(s.sales_owner_id)
    if extra_user_ids:
        for u in db.query(User).filter(User.id.in_(extra_user_ids)).all():
            user_map[u.id] = u.name
    rows = [_serialize_bill_detail(b, db, user_map, company_map, sub_map) for b in bills]
    xlsx_bytes = export_rows(rows, BILL_DETAIL_FIELDS, f"{year}年{month}月账单明细")
    fname = f"bills_{year}{month:02d}.xlsx"
    return StreamingResponse(BytesIO(xlsx_bytes),
                             media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f"attachment; filename={fname}"})


def _query_month_payments(db, tenant_id, year, month):
    """查询当月所有收款记录（payment_date 在指定年月内）"""
    q = db.query(PaymentRecord).filter(
        PaymentRecord.payment_date >= date(year, month, 1),
        PaymentRecord.payment_date < date(year + 1 if month == 12 else year, 1 if month == 12 else month + 1, 1)
    )
    if tenant_id:
        q = q.filter(PaymentRecord.tenant_id == tenant_id)
    return q.order_by(PaymentRecord.payment_date.desc(), PaymentRecord.id.desc()).all()


def _serialize_payment_detail(p, db):
    company = db.query(Company).filter(Company.id == p.company_id).first()
    submitter = db.query(User).filter(User.id == p.submitter_id).first()
    verifier = db.query(User).filter(User.id == p.assigned_verifier_id).first() if p.assigned_verifier_id else None
    return {
        "id": p.id, "company_id": p.company_id,
        "company_name": company.name if company else "",
        "amount": float(p.amount), "payment_date": str(p.payment_date) if p.payment_date else "",
        "channel": p.channel, "channel_text": CHANNEL_MAP.get(p.channel, p.channel),
        "submitter_id": p.submitter_id, "submitter_name": submitter.name if submitter else "",
        "assigned_verifier_id": p.assigned_verifier_id,
        "verifier_name": verifier.name if verifier else "",
        "verify_status": p.verify_status,
        "verify_status_text": STATUS_MAP.get(p.verify_status, p.verify_status),
        "reject_reason": p.reject_reason or "", "remark": p.remark or "",
    }


@router.get("/pre-calc-detail")
def pre_calc_detail(year: int, month: int,
                    user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """计算前：查看当月所有收款明细 + 核对状态汇总"""
    payments = _query_month_payments(db, user.tenant_id, year, month)
    items = [_serialize_payment_detail(p, db) for p in payments]
    # 核对状态汇总
    summary = {
        "total": len(items),
        "approved": sum(1 for p in items if p["verify_status"] == "approved"),
        "pending": sum(1 for p in items if p["verify_status"] == "pending"),
        "rejected": sum(1 for p in items if p["verify_status"] == "rejected"),
        "total_amount": sum(p["amount"] for p in items),
        "approved_amount": sum(p["amount"] for p in items if p["verify_status"] == "approved"),
    }
    # 查询当月是否已锁定
    lv = db.query(LedgerValidation).filter(
        LedgerValidation.ledger_year == year, LedgerValidation.ledger_month == month)
    if user.tenant_id:
        lv = lv.filter(LedgerValidation.tenant_id == user.tenant_id)
    lv = lv.first()
    summary["is_locked"] = bool(lv and lv.status == "locked")
    summary["calculation_status"] = lv.calculation_status if lv else "idle"
    return {"code": 200, "data": {"items": items, "summary": summary}}


@router.get("/pre-calc-export")
def pre_calc_export(year: int, month: int,
                    user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """计算前：导出当月收款明细 Excel"""
    payments = _query_month_payments(db, user.tenant_id, year, month)
    rows = [_serialize_payment_detail(p, db) for p in payments]
    xlsx_bytes = export_rows(rows, PAYMENT_DETAIL_FIELDS, f"{year}年{month}月收款明细")
    fname = f"payments_{year}{month:02d}.xlsx"
    return StreamingResponse(BytesIO(xlsx_bytes),
                             media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f"attachment; filename={fname}"})


# ==================== 提成明细（计算后） ====================

COMMISSION_DETAIL_FIELDS = [
    ("员工姓名", "user_name"), ("客户名称", "company_name"),
    ("提成类型", "commission_type_text"), ("是否补回", "is_supplement_text"),
    ("计算基数", "base_amount"), ("提成比例", "rate_text"),
    ("提成金额", "commission_amount"), ("扣款", "deduction_amount"),
    ("补回", "supplement_amount"), ("实发", "net_amount"),
]

COMMISSION_TYPE_MAP = {"service": "服务提成", "sales": "销售提成", "onetime": "一次性提成"}


def _query_month_commissions(db, tenant_id, year, month):
    """查询当月所有提成明细"""
    q = db.query(CommissionDetail).filter(
        CommissionDetail.billing_year == year, CommissionDetail.billing_month == month)
    if tenant_id:
        q = q.filter(CommissionDetail.tenant_id == tenant_id)
    return q.order_by(CommissionDetail.user_id, CommissionDetail.commission_type).all()


def _serialize_commission_detail(d, db, user_map, company_map):
    return {
        "user_name": user_map.get(d.user_id, ""),
        "company_name": company_map.get(d.company_id, "") if d.company_id else "",
        "commission_type_text": COMMISSION_TYPE_MAP.get(d.commission_type, d.commission_type),
        "is_supplement_text": "是" if d.is_supplement else "否",
        "base_amount": float(d.base_amount),
        "rate_text": f"{float(d.rate) * 100:.2f}%",
        "commission_amount": float(d.commission_amount),
        "deduction_amount": float(d.deduction_amount),
        "supplement_amount": float(d.supplement_amount),
        "net_amount": float(d.net_amount),
    }


@router.get("/post-calc-detail")
def post_calc_detail(year: int, month: int,
                     user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """计算后：查看当月所有提成明细"""
    details = _query_month_commissions(db, user.tenant_id, year, month)
    # 预加载用户名和公司名
    user_ids = {d.user_id for d in details if d.user_id}
    company_ids = {d.company_id for d in details if d.company_id}
    user_map = {u.id: u.name for u in db.query(User).filter(User.id.in_(user_ids)).all()} if user_ids else {}
    company_map = {c.id: c.name for c in db.query(Company).filter(Company.id.in_(company_ids)).all()} if company_ids else {}
    items = [_serialize_commission_detail(d, db, user_map, company_map) for d in details]
    summary = {
        "total": len(items),
        "total_commission": sum(i["commission_amount"] for i in items),
        "total_deduction": sum(i["deduction_amount"] for i in items),
        "total_supplement": sum(i["supplement_amount"] for i in items),
        "total_net": sum(i["net_amount"] for i in items),
    }
    return {"code": 200, "data": {"items": items, "summary": summary}}


@router.get("/post-calc-export")
def post_calc_export(year: int, month: int,
                     user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """计算后：导出当月提成明细 Excel"""
    details = _query_month_commissions(db, user.tenant_id, year, month)
    user_ids = {d.user_id for d in details if d.user_id}
    company_ids = {d.company_id for d in details if d.company_id}
    user_map = {u.id: u.name for u in db.query(User).filter(User.id.in_(user_ids)).all()} if user_ids else {}
    company_map = {c.id: c.name for c in db.query(Company).filter(Company.id.in_(company_ids)).all()} if company_ids else {}
    rows = [_serialize_commission_detail(d, db, user_map, company_map) for d in details]
    xlsx_bytes = export_rows(rows, COMMISSION_DETAIL_FIELDS, f"{year}年{month}月提成明细")
    fname = f"commissions_{year}{month:02d}.xlsx"
    return StreamingResponse(BytesIO(xlsx_bytes),
                             media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f"attachment; filename={fname}"})


@router.post("/validate-and-calculate")
def validate_and_calculate(body: dict, user: User = Depends(require_tenant_user), db: Session = Depends(get_db)):
    if not check_permission(user, "salary:manage") and user.role != "tenant_admin":
        raise HTTPException(403, "权限不足")
    year, month = body["year"], body["month"]

    lq = db.query(LedgerValidation).filter(LedgerValidation.ledger_year == year, LedgerValidation.ledger_month == month)
    if user.tenant_id:
        lq = lq.filter(LedgerValidation.tenant_id == user.tenant_id)
    existing = lq.first()
    if existing and existing.status == "locked":
        raise HTTPException(409, "该月已锁定")
    if existing and existing.calculation_status == "running":
        raise HTTPException(409, "正在计算中，请稍候")

    if not existing:
        existing = LedgerValidation(tenant_id=user.tenant_id, ledger_year=year,
                                    ledger_month=month, status="calculating",
                                    calculation_status="running", locked_by=user.id, locked_at=datetime.utcnow())
        db.add(existing)
    else:
        existing.status = "calculating"
        existing.calculation_status = "running"
        existing.locked_by = user.id
        existing.locked_at = datetime.utcnow()
    db.flush()

    try:
        uq = db.query(User).filter(User.is_active == True)
        if user.tenant_id:
            uq = uq.filter(User.tenant_id == user.tenant_id)
        active_users = uq.all()
        active_user_ids = {u.id for u in active_users}  # v3: 离职即停校验用（§4.9）

        bq = db.query(Bill).filter(Bill.billing_year == year, Bill.billing_month == month)
        if user.tenant_id:
            bq = bq.filter(Bill.tenant_id == user.tenant_id)
        bills = bq.all()

        commission_count = 0
        for bill in bills:
            if bill.bill_type == "subscription" and bill.subscription_id:
                sub = db.query(Subscription).filter(Subscription.id == bill.subscription_id).first()
                if not sub:
                    continue
                fee = get_effective_fee(db, sub.id, year, month)
                commission = fee * Decimal("0.15")
                deduction = Decimal("0")
                if bill.payment_status in ("unpaid", "overdue"):
                    deduction = fee * Decimal("0.05")
                # v3: 服务负责人离职则跳过服务提成（业务未转交时不计提，§4.9）
                owner_active = sub.service_owner_id in active_user_ids
                # v3: 补回仅当当前负责人在职才计算（离职后不补，归当前负责人，§4.3/§4.9）
                supplement_deduction = None
                if bill.payment_status == "paid" and owner_active:
                    supplement_deduction = calc_supplement(db, bill.id, sub.id, bill.company_id, year, month, tenant_id=user.tenant_id)
                if owner_active:
                    cd = CommissionDetail(tenant_id=user.tenant_id, user_id=sub.service_owner_id,
                                          commission_type="service", bill_id=bill.id,
                                          company_id=bill.company_id, subscription_id=sub.id,
                                          billing_year=year, billing_month=month, base_amount=fee,
                                          rate=Decimal("0.15"), commission_amount=commission,
                                          deduction_amount=deduction, supplement_amount=Decimal("0"),
                                          net_amount=commission - deduction, is_supplement=False,
                                          ledger_validation_id=existing.id)
                    db.add(cd)
                    commission_count += 1
                # v3: 补回归当前业务负责人（sub.service_owner_id），supplement_for_user_id 保留原被扣人供追溯与幂等校验（§4.3）
                if supplement_deduction:
                    cd2 = CommissionDetail(tenant_id=user.tenant_id, user_id=sub.service_owner_id,
                                           commission_type="service", bill_id=bill.id,
                                           company_id=bill.company_id, subscription_id=sub.id,
                                           billing_year=year, billing_month=month, base_amount=Decimal("0"),
                                           rate=Decimal("0"), commission_amount=Decimal("0"),
                                           deduction_amount=Decimal("0"),
                                           supplement_amount=supplement_deduction.deduction_amount,
                                           net_amount=supplement_deduction.deduction_amount,
                                           is_supplement=True,
                                           supplement_for_user_id=supplement_deduction.user_id,
                                           ledger_validation_id=existing.id)
                    db.add(cd2)
                    commission_count += 1
                # v3: 销售提成 — 销售离职即停，窗口内剩余月份不再计提（§4.4/§4.9）
                if (sub.sales_owner_id and sub.sales_owner_id in active_user_ids
                        and in_sales_window(bill.company_id, year, month, db, user.tenant_id)):
                    approved_alloc = get_approved_allocations(db, bill.id, year, month, user.tenant_id)
                    for alloc_amt in approved_alloc:
                        sc = CommissionDetail(tenant_id=user.tenant_id, user_id=sub.sales_owner_id,
                                              commission_type="sales", bill_id=bill.id,
                                              company_id=bill.company_id, subscription_id=sub.id,
                                              billing_year=year, billing_month=month, base_amount=alloc_amt,
                                              rate=Decimal("0.15"),
                                              commission_amount=alloc_amt * Decimal("0.15"),
                                              deduction_amount=Decimal("0"), supplement_amount=Decimal("0"),
                                              net_amount=alloc_amt * Decimal("0.15"),
                                              is_supplement=False, ledger_validation_id=existing.id)
                        db.add(sc)
                        commission_count += 1

            elif bill.bill_type == "onetime" and bill.onetime_project_id:
                proj = db.query(OneTimeProject).filter(OneTimeProject.id == bill.onetime_project_id).first()
                if not proj:
                    continue
                # v3: 一次性业务负责人离职则跳过（§4.9）
                if proj.owner_id not in active_user_ids:
                    continue
                gp = proj.revenue - proj.cost
                commission = gp * Decimal("0.20")
                deduction = Decimal("0") if proj.is_received else gp * Decimal("0.05")
                cd = CommissionDetail(tenant_id=user.tenant_id, user_id=proj.owner_id,
                                      commission_type="onetime", bill_id=bill.id,
                                      company_id=bill.company_id, onetime_project_id=proj.id,
                                      billing_year=year, billing_month=month, base_amount=gp,
                                      rate=Decimal("0.20"), commission_amount=commission,
                                      deduction_amount=deduction, supplement_amount=Decimal("0"),
                                      net_amount=commission - deduction, is_supplement=False,
                                      ledger_validation_id=existing.id)
                db.add(cd)
                commission_count += 1

        db.flush()

        salary_count = 0
        for u in active_users:
            dq = db.query(CommissionDetail).filter(
                CommissionDetail.user_id == u.id,
                CommissionDetail.ledger_validation_id == existing.id)
            if user.tenant_id:
                dq = dq.filter(CommissionDetail.tenant_id == user.tenant_id)
            details = dq.all()
            svc = sum(d.commission_amount for d in details if d.commission_type == "service" and not d.is_supplement)
            sls = sum(d.commission_amount for d in details if d.commission_type == "sales")
            ot = sum(d.commission_amount for d in details if d.commission_type == "onetime")
            ded = sum(d.deduction_amount for d in details)
            sup = sum(d.supplement_amount for d in details)
            gross = u.base_salary + svc + sls + ot + sup - ded
            ms = MonthlySalary(tenant_id=user.tenant_id, user_id=u.id,
                               salary_year=year, salary_month=month, base_salary=u.base_salary,
                               service_commission=svc, sales_commission=sls, onetime_commission=ot,
                               total_deduction=ded, total_supplement=sup, gross_payable=gross,
                               ledger_validation_id=existing.id)
            db.add(ms)
            salary_count += 1

        existing.status = "locked"
        existing.calculation_status = "completed"
        db.commit()
        return {"code": 200, "data": {"ledger_id": existing.id, "status": "locked",
                "salary_count": salary_count, "commission_count": commission_count}}

    except Exception as e:
        db.rollback()
        if existing:
            existing.calculation_status = "failed"
            existing.status = "unlocked"
            db.commit()
        raise HTTPException(500, f"计算失败: {str(e)}")


@router.get("/status")
def get_ledger_status(year: int = None, month: int = None,
                      user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(LedgerValidation)
    if user.tenant_id:
        q = q.filter(LedgerValidation.tenant_id == user.tenant_id)
    if year:
        q = q.filter(LedgerValidation.ledger_year == year)
    if month:
        q = q.filter(LedgerValidation.ledger_month == month)
    items = q.order_by(LedgerValidation.ledger_year.desc(), LedgerValidation.ledger_month.desc()).limit(24).all()
    return {"code": 200, "data": {"items": [{"id": l.id, "ledger_year": l.ledger_year,
            "ledger_month": l.ledger_month, "status": l.status,
            "calculation_status": l.calculation_status,
            "locked_at": str(l.locked_at) if l.locked_at else None} for l in items],
            "total": len(items)}}


@router.post("/{lid}/unlock")
def unlock_ledger(lid: int, user: User = Depends(require_tenant_user), db: Session = Depends(get_db)):
    if not check_permission(user, "salary:manage") and user.role != "tenant_admin":
        raise HTTPException(403, "权限不足")
    q = db.query(LedgerValidation).filter(LedgerValidation.id == lid)
    if user.tenant_id:
        q = q.filter(LedgerValidation.tenant_id == user.tenant_id)
    ledger = q.first()
    if not ledger:
        raise HTTPException(404, "锁定记录不存在")
    if ledger.status != "locked":
        raise HTTPException(422, "仅锁定状态可撤销")
    lq = db.query(LedgerValidation).filter(LedgerValidation.status == "locked")
    if user.tenant_id:
        lq = lq.filter(LedgerValidation.tenant_id == user.tenant_id)
    latest = lq.order_by(LedgerValidation.ledger_year.desc(), LedgerValidation.ledger_month.desc()).first()
    if latest and latest.id != ledger.id:
        raise HTTPException(422, "仅最近一个锁定月可撤销")

    mq = db.query(MonthlySalary).filter(MonthlySalary.ledger_validation_id == ledger.id)
    if user.tenant_id:
        mq = mq.filter(MonthlySalary.tenant_id == user.tenant_id)
    mq.delete()

    pq = db.query(CommissionDetail).filter(
        CommissionDetail.ledger_validation_id == ledger.id,
        CommissionDetail.is_supplement == False,
        CommissionDetail.deduction_amount > 0)
    if user.tenant_id:
        pq = pq.filter(CommissionDetail.tenant_id == user.tenant_id)
    preserved = pq.all()
    for d in preserved:
        d.commission_amount = Decimal("0")
        d.base_amount = Decimal("0")
        d.rate = Decimal("0")
        d.net_amount = d.deduction_amount
        # 脱离当月锁定（置 NULL），避免重算时被 MonthlySalary 重复计入；
        # 但保留记录本身供 calc_supplement 按 subscription_id 查询补回追溯
        d.ledger_validation_id = None
    dq = db.query(CommissionDetail).filter(
        CommissionDetail.ledger_validation_id == ledger.id,
        CommissionDetail.is_supplement == False,
        CommissionDetail.deduction_amount == 0)
    if user.tenant_id:
        dq = dq.filter(CommissionDetail.tenant_id == user.tenant_id)
    dq.delete()

    ledger.status = "unlocked"
    ledger.calculation_status = "idle"
    ledger.unlocked_by = user.id
    ledger.unlocked_at = datetime.utcnow()
    db.commit()
    return {"code": 200, "message": "已撤销"}
