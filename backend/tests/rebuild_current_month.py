"""重新生成当前月的账单/薪资/月结数据，确保每个页面打开都有数据"""
import sys
from datetime import date
from decimal import Decimal
from sqlalchemy import text

sys.path.insert(0, "e:/code/ai_code/payclip/backend")
from app.database import SessionLocal
from app.models import (User, Company, Subscription, OneTimeProject, Bill,
                       MonthlySalary, LedgerValidation, CommissionDetail)

db = SessionLocal()

today = date.today()
Y, M = today.year, today.month
print(f"目标年月: {Y}-{M:02d}")

# 找出演示租户
r = db.execute(text("SELECT id FROM tenants WHERE name='演示工作室'")).fetchone()
TID = r[0]
print(f"演示租户 ID: {TID}")

# ========== 1. 清空时间相关数据（按外键依赖顺序） ==========
print("\n=== 清空旧的时间相关数据 ===")
for tbl in ["payment_bill_allocations", "commission_details", "monthly_salaries", "ledger_validations", "bills"]:
    cnt = db.execute(text(f"DELETE FROM {tbl} WHERE tenant_id={TID}")).rowcount
    print(f"  删除 {tbl}: {cnt} 条")

# ========== 2. 重新生成当前月账单 ==========
print(f"\n=== 生成 {Y}-{M:02d} 账单 ===")
subs = db.query(Subscription).filter(
    Subscription.tenant_id == TID, Subscription.is_active == True, Subscription.is_archived == False
).all()
print(f"  活跃订阅数: {len(subs)}")

bill_count = 0
for sub in subs:
    cust = db.query(Company).filter(Company.id == sub.company_id).first()
    follow_up = cust.business_owner_id or sub.service_owner_id
    b = Bill(
        tenant_id=TID, company_id=sub.company_id, subscription_id=sub.id,
        bill_type="subscription", billing_year=Y, billing_month=M,
        receivable_amount=sub.monthly_fee, paid_amount=0,
        payment_status="unpaid", is_overdue=False,
        follow_up_user_id=follow_up
    )
    db.add(b)
    bill_count += 1
print(f"  创建 {bill_count} 条长期业务账单")

onetimes = db.query(OneTimeProject).filter(
    OneTimeProject.tenant_id == TID, OneTimeProject.is_archived == False
).all()
ot_count = 0
for ot in onetimes:
    cust = db.query(Company).filter(Company.id == ot.company_id).first()
    follow_up = cust.business_owner_id or ot.owner_id
    b = Bill(
        tenant_id=TID, company_id=ot.company_id, onetime_project_id=ot.id,
        bill_type="onetime", billing_year=Y, billing_month=M,
        receivable_amount=ot.revenue, paid_amount=ot.revenue if ot.is_received else 0,
        payment_status="paid" if ot.is_received else "unpaid",
        is_overdue=False, follow_up_user_id=follow_up
    )
    db.add(b)
    ot_count += 1
print(f"  创建 {ot_count} 条一次性业务账单")

# 上月部分账单（体现多月份）
prev_month = M - 1 if M > 1 else 12
prev_year = Y if M > 1 else Y - 1
prev_count = 0
for sub in subs[:3]:
    cust = db.query(Company).filter(Company.id == sub.company_id).first()
    follow_up = cust.business_owner_id or sub.service_owner_id
    b = Bill(
        tenant_id=TID, company_id=sub.company_id, subscription_id=sub.id,
        bill_type="subscription", billing_year=prev_year, billing_month=prev_month,
        receivable_amount=sub.monthly_fee, paid_amount=sub.monthly_fee,
        payment_status="paid", is_overdue=False,
        follow_up_user_id=follow_up
    )
    db.add(b)
    prev_count += 1
print(f"  创建 {prev_count} 条上月已结清账单")

db.commit()
print(f"  账单总计: {bill_count + ot_count + prev_count} 条")

# ========== 3. 更新收款记录日期到当前月 ==========
print(f"\n=== 更新收款记录到当前月 ===")
cnt = db.execute(text(
    "UPDATE payment_records SET payment_date = DATE(:d) WHERE tenant_id=:tid AND payment_date < :d"
), {"d": today, "tid": TID}).rowcount
print(f"  更新 {cnt} 条收款记录的日期")

# ========== 4. 更新一次性业务完成日期 ==========
print(f"\n=== 更新一次性业务完成日期 ===")
cnt = db.execute(text(
    "UPDATE onetime_projects SET completion_date = DATE(:d) WHERE tenant_id=:tid AND completion_date IS NOT NULL AND completion_date < :d"
), {"d": today, "tid": TID}).rowcount
print(f"  更新 {cnt} 条一次性业务完成日期")
cnt = db.execute(text(
    "UPDATE onetime_projects SET receive_date = DATE(:d) WHERE tenant_id=:tid AND is_received=1 AND receive_date IS NOT NULL AND receive_date < :d"
), {"d": today, "tid": TID}).rowcount
print(f"  更新 {cnt} 条一次性业务收款日期")

# ========== 5. 更新月费变更历史 ==========
print(f"\n=== 更新月费变更历史 ===")
cnt = db.execute(text(
    "UPDATE fee_histories SET effective_date = DATE(:d) WHERE tenant_id=:tid AND effective_date < :d"
), {"d": today, "tid": TID}).rowcount
print(f"  更新 {cnt} 条月费变更历史")

# ========== 6. 创建当前月月结记录（必须先创建，薪资和提成依赖它） ==========
print(f"\n=== 创建 {Y}-{M:02d} 月结记录 ===")
admin = db.query(User).filter(User.username == "demo_admin").first()
lv = LedgerValidation(
    tenant_id=TID, ledger_year=Y, ledger_month=M,
    status="locked", locked_by=admin.id, locked_at=date.today(),
    calculation_status="completed"
)
db.add(lv)
db.commit()
db.refresh(lv)
print(f"  创建月结记录 (locked, id={lv.id})")

# ========== 7. 创建当前月薪资记录（依赖 ledger_validation_id） ==========
print(f"\n=== 创建 {Y}-{M:02d} 薪资记录 ===")
emps = db.query(User).filter(
    User.tenant_id == TID, User.is_active == True, User.role == "employee"
).all()
print(f"  员工数: {len(emps)}")
sal_count = 0
for emp in emps:
    base = emp.base_salary or Decimal("5000")
    sal = MonthlySalary(
        tenant_id=TID, user_id=emp.id,
        salary_year=Y, salary_month=M,
        base_salary=base,
        service_commission=Decimal("1500.00"),
        sales_commission=Decimal("800.00"),
        onetime_commission=Decimal("500.00"),
        total_deduction=Decimal("0"),
        total_supplement=Decimal("0"),
        gross_payable=base + Decimal("2800.00"),
        ledger_validation_id=lv.id
    )
    db.add(sal)
    sal_count += 1
db.commit()
print(f"  创建 {sal_count} 条薪资记录")

# ========== 8. 创建当前月提成明细 ==========
print(f"\n=== 创建 {Y}-{M:02d} 提成明细 ===")
current_bills = db.query(Bill).filter(
    Bill.tenant_id == TID, Bill.billing_year == Y, Bill.billing_month == M
).all()
print(f"  当前月账单数: {len(current_bills)}")

cd_count = 0
for bill in current_bills:
    if bill.subscription_id:
        sub = db.query(Subscription).filter(Subscription.id == bill.subscription_id).first()
        if not sub:
            continue
        cust = db.query(Company).filter(Company.id == bill.company_id).first()
        owner_id = cust.business_owner_id or sub.service_owner_id
        cd = CommissionDetail(
            tenant_id=TID, user_id=owner_id,
            commission_type="service", bill_id=bill.id,
            company_id=bill.company_id, subscription_id=sub.id,
            billing_year=Y, billing_month=M,
            base_amount=bill.receivable_amount,
            rate=Decimal("0.1000"),
            commission_amount=bill.receivable_amount * Decimal("0.1000"),
            deduction_amount=Decimal("0"),
            supplement_amount=Decimal("0"),
            net_amount=bill.receivable_amount * Decimal("0.1000"),
            is_supplement=False,
            ledger_validation_id=lv.id
        )
        db.add(cd)
        cd_count += 1
db.commit()
print(f"  创建 {cd_count} 条提成明细")

# ========== 验证结果 ==========
print(f"\n=== 验证结果 ===")
checks = [
    ("bills", "billing_year", "billing_month"),
    ("monthly_salaries", "salary_year", "salary_month"),
    ("commission_details", "billing_year", "billing_month"),
    ("ledger_validations", "ledger_year", "ledger_month"),
]
for tbl, yc, mc in checks:
    r = db.execute(text(f"SELECT {yc}, {mc}, COUNT(*) FROM {tbl} WHERE tenant_id={TID} GROUP BY {yc}, {mc} ORDER BY {yc}, {mc}")).fetchall()
    print(f"  {tbl}: {r}")

r = db.execute(text(f"SELECT MIN(payment_date), MAX(payment_date), COUNT(*) FROM payment_records WHERE tenant_id={TID}")).fetchall()
print(f"  payment_records: {r}")

db.close()
print("\n✓ 完成")
