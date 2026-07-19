"""共享辅助函数"""
from datetime import date
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..models import (Company, Subscription, FeeHistory, CommissionDetail,
                      PaymentBillAllocation, PaymentRecord)


def parse_date(val):
    """把字符串/None/date 转成 date，None/空返回 None"""
    if not val:
        return None
    if isinstance(val, date):
        return val
    return date.fromisoformat(str(val))


def get_effective_fee(db: Session, sub_id: int, year: int, month: int) -> Decimal:
    """获取订阅在 year-month 月的有效月费（按 FeeHistory 取最新生效记录，否则用当前 monthly_fee）"""
    target = date(year, month, 1)
    fh = db.query(FeeHistory).filter(
        FeeHistory.subscription_id == sub_id,
        FeeHistory.effective_date <= target
    ).order_by(FeeHistory.effective_date.desc()).first()
    if fh:
        return fh.new_fee
    sub = db.query(Subscription).filter(Subscription.id == sub_id).first()
    return sub.monthly_fee if sub else Decimal("0")


def calc_supplement(db: Session, bill_id: int, sub_id: int, company_id: int,
                    year: int, month: int, tenant_id: int = None):
    """计算补回：找上一笔未补回的扣款记录，返回该 CommissionDetail 或 None"""
    current_month_seq = year * 12 + month
    dq = db.query(CommissionDetail).filter(
        CommissionDetail.subscription_id == sub_id,
        CommissionDetail.commission_type == "service",
        CommissionDetail.deduction_amount > 0,
        CommissionDetail.is_supplement == False
    )
    if tenant_id:
        dq = dq.filter(CommissionDetail.tenant_id == tenant_id)
    deductions = dq.all()
    valid_deductions = [d for d in deductions
                        if (d.billing_year * 12 + d.billing_month) < current_month_seq]
    if not valid_deductions:
        return None
    deduction = valid_deductions[0]
    already_supp = db.query(CommissionDetail).filter(
        CommissionDetail.subscription_id == sub_id,
        CommissionDetail.is_supplement == True,
        CommissionDetail.supplement_for_user_id == deduction.user_id,
        CommissionDetail.billing_year == deduction.billing_year,
        CommissionDetail.billing_month == deduction.billing_month
    ).first()
    if already_supp:
        return None
    return deduction


def in_sales_window(company_id: int, year: int, month: int,
                    db: Session, tenant_id: int = None) -> bool:
    """判断 year-month 是否在客户的新客销售窗口内（合作起始 12 个月内）"""
    cq = db.query(Company).filter(Company.id == company_id)
    if tenant_id:
        cq = cq.filter(Company.tenant_id == tenant_id)
    c = cq.first()
    if not c or not c.is_new_customer or not c.service_start_date:
        return False
    start = c.service_start_date
    s_months = start.year * 12 + start.month
    t_months = year * 12 + month
    return 0 <= (t_months - s_months) <= 11


def get_approved_allocations(db: Session, bill_id: int, year: int, month: int,
                             tenant_id: int = None):
    """取 bill_id 在 year-month 的所有已审核公款分配金额列表"""
    q = db.query(PaymentBillAllocation).join(PaymentRecord).filter(
        PaymentBillAllocation.bill_id == bill_id,
        PaymentRecord.verify_status == "approved",
        PaymentRecord.usage_type == "public",
        func.year(PaymentRecord.payment_date) == year,
        func.month(PaymentRecord.payment_date) == month
    )
    if tenant_id:
        q = q.filter(PaymentBillAllocation.tenant_id == tenant_id)
    return [a.allocation_amount for a in q.all()]
