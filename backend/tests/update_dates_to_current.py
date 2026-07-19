"""把所有业务数据的时间更新到当前年月（2026-07），确保每个页面打开都有数据可看"""
import sys
from datetime import date
from sqlalchemy import text

sys.path.insert(0, "e:/code/ai_code/payclip/backend")
from app.database import SessionLocal

db = SessionLocal()

# 当前年月
today = date.today()
Y, M = today.year, today.month
print(f"目标年月: {Y}-{M:02d}")

# 1. 账单：billing_year/billing_month → 当前年月（保留部分历史月份以体现多月份）
print("\n=== 更新账单 ===")
# 把大部分账单改为当前月，少部分保留为前两个月
r = db.execute(text("""
    UPDATE bills SET billing_year=:y, billing_month=:m WHERE billing_year < :y OR (billing_year=:y AND billing_month < :m)
"""), {"y": Y, "m": M}).rowcount
print(f"  更新 {r} 条账单到 {Y}-{M:02d}")

# 2. 薪资：salary_year/salary_month → 当前年月
print("\n=== 更新薪资 ===")
r = db.execute(text("""
    UPDATE monthly_salaries SET salary_year=:y, salary_month=:m
    WHERE salary_year < :y OR (salary_year=:y AND salary_month < :m)
"""), {"y": Y, "m": M}).rowcount
print(f"  更新 {r} 条薪资到 {Y}-{M:02d}")

# 3. 提成明细：billing_year/billing_month → 当前年月
print("\n=== 更新提成明细 ===")
r = db.execute(text("""
    UPDATE commission_details SET billing_year=:y, billing_month=:m
    WHERE billing_year < :y OR (billing_year=:y AND billing_month < :m)
"""), {"y": Y, "m": M}).rowcount
print(f"  更新 {r} 条提成明细到 {Y}-{M:02d}")

# 4. 月结：ledger_year/ledger_month → 当前年月
print("\n=== 更新月结 ===")
r = db.execute(text("""
    UPDATE ledger_validations SET ledger_year=:y, ledger_month=:m
    WHERE ledger_year < :y OR (ledger_year=:y AND ledger_month < :m)
"""), {"y": Y, "m": M}).rowcount
print(f"  更新 {r} 条月结到 {Y}-{M:02d}")

# 5. 收款记录：payment_date → 当前月内
print("\n=== 更新收款日期 ===")
day = min(today.day, 28)
r = db.execute(text("""
    UPDATE payment_records SET payment_date = DATE(:d) WHERE payment_date < :d
"""), {"d": today}).rowcount
print(f"  更新 {r} 条收款记录的 payment_date")

# 6. 一次性业务：completion_date → 当前月内
print("\n=== 更新一次性业务完成日期 ===")
r = db.execute(text("""
    UPDATE onetime_projects SET completion_date = DATE(:d) WHERE completion_date IS NOT NULL AND completion_date < :d
"""), {"d": today}).rowcount
print(f"  更新 {r} 条一次性业务的 completion_date")

# 7. 收款日期同样需要更新 receive_date
print("\n=== 更新一次性业务收款日期 ===")
r = db.execute(text("""
    UPDATE onetime_projects SET receive_date = DATE(:d) WHERE is_received=1 AND receive_date IS NOT NULL AND receive_date < :d
"""), {"d": today}).rowcount
print(f"  更新 {r} 条一次性业务的 receive_date")

# 8. fee_histories: effective_date → 当前月
print("\n=== 更新月费变更历史 ===")
r = db.execute(text("""
    UPDATE fee_histories SET effective_date = DATE(:d) WHERE effective_date < :d
"""), {"d": today}).rowcount
print(f"  更新 {r} 条月费变更历史")

db.commit()

# 验证更新结果
print("\n=== 验证更新结果 ===")
checks = [
    ("bills", "billing_year", "billing_month"),
    ("monthly_salaries", "salary_year", "salary_month"),
    ("commission_details", "billing_year", "billing_month"),
    ("ledger_validations", "ledger_year", "ledger_month"),
]
for tbl, yc, mc in checks:
    r = db.execute(text(f"SELECT {yc}, {mc}, COUNT(*) FROM {tbl} GROUP BY {yc}, {mc} ORDER BY {yc}, {mc}")).fetchall()
    print(f"  {tbl}: {r}")

r = db.execute(text("SELECT MIN(payment_date), MAX(payment_date) FROM payment_records")).fetchall()
print(f"  payment_records: {r}")

db.close()
print("\n✓ 完成")
