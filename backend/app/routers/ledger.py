"""月结与提成计算引擎：校验计算/状态查询/撤销"""
from datetime import datetime
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import (LedgerValidation, User, Bill, Subscription, OneTimeProject,
                      CommissionDetail, MonthlySalary)
from ..core.auth import get_current_user, check_permission, require_tenant_user
from ..utils import get_effective_fee, calc_supplement, in_sales_window, get_approved_allocations

router = APIRouter(prefix="/api/ledger", tags=["月结计算"])


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
                supplement_deduction = None
                if bill.payment_status == "paid":
                    supplement_deduction = calc_supplement(db, bill.id, sub.id, bill.company_id, year, month, tenant_id=user.tenant_id)
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
                if supplement_deduction:
                    cd2 = CommissionDetail(tenant_id=user.tenant_id, user_id=supplement_deduction.user_id,
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
                if sub.sales_owner_id and in_sales_window(bill.company_id, year, month, db, user.tenant_id):
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
