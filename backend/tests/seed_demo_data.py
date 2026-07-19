"""完整清理测试数据 + 在一个租户下重建演示数据

策略：
1. 按外键依赖顺序清空所有业务表
2. 保留 super_admin（id=1）
3. 创建/重置一个"演示工作室"租户（id 由数据库自增）
4. 在该租户下构造完整业务数据，覆盖所有页面：
   - 用户：1 个租户管理员 + 3 个员工（不同角色和权限）
   - 供应商：3 个
   - 客户：6 个（含新客户、老客户、不同业务负责人）
   - 长期业务：5 个（覆盖月/季/半年/年 4 种计费周期）
   - 一次性业务：3 个（含已收款和未收款）
   - 账单：2025-05/06/07 三个月，不同状态
   - 收款：3 条已通过 + 2 条待核对
   - 月结：2025-05 已锁定
   - 薪资：2025-05 已生成
   - 成本预设、阶梯奖金
"""
import sys
import json
from datetime import date, datetime, timedelta
from decimal import Decimal

sys.path.insert(0, "e:/code/ai_code/payclip/backend")

from app.database import engine, SessionLocal, Base
from app.models import (User, Tenant, Company, Supplier, Subscription, OneTimeProject,
                       Bill, PaymentRecord, PaymentBillAllocation, PaymentScreenshot,
                       CustomerPrepayment, CommissionDetail, MonthlySalary, LedgerValidation,
                       FeeHistory, CostPreset, BonusTier, RegistrationCode, InvitationLink,
                       SubscriptionOwnerHistory, OnetimeOwnerHistory, BillFollowUpHistory)
from app.core.auth import hash_password
from sqlalchemy import text


def clean_all(db):
    """按外键顺序清空所有业务表，保留 super_admin"""
    print("=== 清理所有业务数据 ===")
    # 业务表（按依赖倒序）
    for tbl in [
        "bill_follow_up_histories", "onetime_owner_histories", "subscription_owner_histories",
        "monthly_salaries", "commission_details", "ledger_validations",
        "payment_screenshots", "payment_bill_allocations", "payment_records",
        "prepayment_logs", "customer_prepayments", "fee_histories", "bills",
        "onetime_projects", "subscriptions",
        "cost_presets", "bonus_tiers",
        "payment_channels", "service_types",
        "companies", "suppliers",
        "invitation_links", "registration_codes",
    ]:
        cnt = db.execute(text(f"DELETE FROM `{tbl}`")).rowcount
        if cnt > 0:
            print(f"  清空 {tbl}: {cnt} 条")

    # 删除非 super_admin 用户
    cnt = db.execute(text("DELETE FROM users WHERE role != 'super_admin'")).rowcount
    print(f"  清空非 super_admin 用户: {cnt} 条")

    # 删除所有租户
    cnt = db.execute(text("DELETE FROM tenants")).rowcount
    print(f"  清空租户: {cnt} 条")

    # 重置 super_admin 的 tenant_id
    db.execute(text("UPDATE users SET tenant_id = NULL WHERE role = 'super_admin'"))
    db.commit()
    print("  已重置 super_admin")


def create_tenant_and_users(db):
    """创建演示工作室租户和用户"""
    print("\n=== 创建租户和用户 ===")
    tenant = Tenant(name="演示工作室", plan="yearly", status="active",
                   max_employees=20, contact_phone="13800000000",
                   trial_expires=datetime.utcnow() + timedelta(days=365),
                   plan_expires=datetime.utcnow() + timedelta(days=365))
    db.add(tenant)
    db.flush()
    tid = tenant.id
    print(f"  租户：演示工作室 (id={tid})")

    # 租户管理员
    admin = User(tenant_id=tid, username="demo_admin", phone="13800000001",
                password_hash=hash_password("123456"), name="演示管理员",
                role="tenant_admin", base_salary=Decimal("8000"),
                permissions=json.dumps(["admin:config", "payment:submit", "payment:verify",
                                       "salary:view", "salary:manage", "report:view", "tenant:admin"]),
                data_scope="ALL", is_admin=False)
    db.add(admin)

    # 3 个员工
    emp1 = User(tenant_id=tid, username="demo_emp1", phone="13800000002",
               password_hash=hash_password("123456"), name="张三",
               role="employee", base_salary=Decimal("5000"),
               permissions=json.dumps(["payment:submit", "salary:view"]),
               data_scope="ALL")
    db.add(emp1)

    emp2 = User(tenant_id=tid, username="demo_emp2", phone="13800000003",
               password_hash=hash_password("123456"), name="李四",
               role="employee", base_salary=Decimal("5500"),
               permissions=json.dumps(["payment:submit", "payment:verify", "salary:view"]),
               data_scope="ALL")
    db.add(emp2)

    emp3 = User(tenant_id=tid, username="demo_emp3", phone="13800000004",
               password_hash=hash_password("123456"), name="王五",
               role="employee", base_salary=Decimal("4800"),
               permissions=json.dumps(["payment:submit", "salary:view", "report:view"]),
               data_scope="SELF")
    db.add(emp3)

    db.flush()
    print(f"  用户：演示管理员(tenant_admin)、张三/李四/王五(employee)")
    return tid, admin.id, emp1.id, emp2.id, emp3.id


def create_suppliers(db, tid):
    """创建供应商"""
    print("\n=== 创建供应商 ===")
    suppliers_data = [
        ("广州财税服务有限公司", "service", "张经理 13800001111"),
        ("深圳代理记账公司", "service", "李经理 13800002222"),
        ("上海人力资源外包", "hr", "王经理 13800003333"),
    ]
    ids = []
    for name, type_, contact in suppliers_data:
        s = Supplier(tenant_id=tid, name=name, type=type_, contact=contact)
        db.add(s)
        ids.append(s)
    db.flush()
    for s in ids:
        print(f"  供应商 id={s.id}: {s.name}")
    return [s.id for s in ids]


def create_customers(db, tid, emp1_id, emp2_id, emp3_id):
    """创建客户：覆盖新客户/老客户/不同业务负责人"""
    print("\n=== 创建客户 ===")
    today = date.today()
    # (name, service_start_date, sales_person_id, business_owner_id, region_tags, introducer_type, introducer_name)
    customers_data = [
        ("广州明科技有限公司", today - timedelta(days=90), emp1_id, emp1_id, ["广州", "天河区"], "external", "陈总"),
        ("深圳海贸易公司", today - timedelta(days=30), emp2_id, emp2_id, ["深圳", "南山区"], "internal", None),
        ("北京云科技有限公司", today - timedelta(days=400), emp1_id, emp2_id, ["北京", "海淀区"], "external", "刘总"),
        ("上海优网络公司", today - timedelta(days=60), emp3_id, emp3_id, ["上海", "浦东新区"], "external", "赵总"),
        ("杭州智造厂", today - timedelta(days=200), emp2_id, emp1_id, ["杭州", "余杭区"], "external", "钱总"),
        ("成都信科技公司", today - timedelta(days=500), emp3_id, emp3_id, ["成都", "高新区"], "internal", None),
    ]
    ids = []
    for name, sd, sales_id, biz_id, tags, itype, iname in customers_data:
        c = Company(tenant_id=tid, name=name,
                   region_tags=json.dumps(tags),
                   is_new_customer=False,  # 后端会自动计算
                   service_start_date=sd,
                   status="active",
                   introducer_type=itype,
                   introducer_name=iname if itype == "external" else None,
                   introducer_user_id=emp1_id if itype == "internal" else None,
                   sales_person_id=sales_id,
                   business_owner_id=biz_id,
                   contact_phone=f"138{(hash(name) % 100000000):08d}",
                   contact_email=f"contact{(hash(name) % 1000):03d}@example.com")
        db.add(c)
        ids.append(c)
    db.flush()
    for c in ids:
        print(f"  客户 id={c.id}: {c.name} (起始 {c.service_start_date})")
    return [c.id for c in ids]


def create_subscriptions(db, tid, cust_ids, emp_ids, supplier_ids):
    """创建长期业务：覆盖 4 种计费周期"""
    print("\n=== 创建长期业务 ===")
    emp1_id, emp2_id, emp3_id = emp_ids
    s1, s2, s3 = supplier_ids
    # (company_id, service_type, billing_period, monthly_fee, is_cost_type, monthly_cost, supplier_id, service_owner_id, sales_owner_id, start_date)
    subs_data = [
        (cust_ids[0], "代账服务", "month", Decimal("3000"), True, Decimal("800"), s1, emp1_id, emp2_id, date(2024, 6, 1)),
        (cust_ids[1], "代账服务", "month", Decimal("2500"), True, Decimal("600"), s1, emp2_id, emp1_id, date(2024, 8, 15)),
        (cust_ids[2], "税务咨询", "quarter", Decimal("8000"), False, Decimal("0"), None, emp1_id, None, date(2024, 3, 1)),
        (cust_ids[3], "代账服务", "month", Decimal("3500"), True, Decimal("900"), s2, emp3_id, emp3_id, date(2024, 9, 1)),
        (cust_ids[4], "社保代理", "half_year", Decimal("12000"), True, Decimal("3000"), s3, emp2_id, emp1_id, date(2024, 5, 1)),
        (cust_ids[5], "年度审计", "year", Decimal("50000"), False, Decimal("0"), None, emp3_id, emp3_id, date(2024, 1, 1)),
    ]
    ids = []
    for cid, stype, bp, fee, is_cost, cost, sid, sowner, sales_owner, sd in subs_data:
        sub = Subscription(tenant_id=tid, company_id=cid, service_type=stype,
                          billing_period=bp, monthly_fee=fee,
                          is_cost_type=is_cost, monthly_cost=cost,
                          supplier_id=sid, service_owner_id=sowner,
                          sales_owner_id=sales_owner, start_date=sd, is_active=True)
        db.add(sub)
        ids.append(sub)
    db.flush()
    for s in ids:
        print(f"  长期业务 id={s.id}: company_id={s.company_id} {s.service_type} 周期={s.billing_period} 月费={s.monthly_fee}")
    return [s.id for s in ids]


def create_onetime_projects(db, tid, cust_ids, emp_ids, supplier_ids):
    """创建一次性业务：含已收款和未收款（基于当前年月）"""
    print("\n=== 创建一次性业务 ===")
    emp1_id, emp2_id, emp3_id = emp_ids
    s1 = supplier_ids[0]
    today = date.today()
    y, m = today.year, today.month
    # 前一月、前二月、当月
    def pm(n):
        total = y * 12 + (m - 1) - n
        return date(total // 12, (total % 12) + 1, 15)
    # (company_id, project_type, revenue, cost, supplier_id, owner_id, completion_date, is_received, receive_date)
    projects_data = [
        (cust_ids[0], "年报审计", Decimal("20000"), Decimal("5000"), s1, emp1_id, pm(2), True, pm(1)),
        (cust_ids[2], "专项审计", Decimal("35000"), Decimal("8000"), s1, emp1_id, pm(1), True, today.replace(day=min(today.day, 28))),
        (cust_ids[4], "注销服务", Decimal("15000"), Decimal("3000"), None, emp2_id, today.replace(day=min(today.day, 28)), False, None),
    ]
    ids = []
    for cid, ptype, rev, cost, sid, oid, cd, recv, rd in projects_data:
        p = OneTimeProject(tenant_id=tid, company_id=cid, project_type=ptype,
                          revenue=rev, cost=cost, supplier_id=sid, owner_id=oid,
                          completion_date=cd, is_received=recv, receive_date=rd)
        db.add(p)
        ids.append(p)
    db.flush()
    for p in ids:
        print(f"  一次性业务 id={p.id}: {p.project_type} 收入={p.revenue} 已收={p.is_received}")
    return [p.id for p in ids]


def create_bills(db, tid, sub_ids, onetime_ids, emp_ids):
    """创建账单：覆盖多月份多状态（基于当前年月）"""
    print("\n=== 创建账单 ===")
    emp1_id, emp2_id, emp3_id = emp_ids
    today = date.today()
    y, m = today.year, today.month
    # 计算前 N 个月
    def pm(n):
        total = y * 12 + (m - 1) - n
        return total // 12, (total % 12) + 1
    ym0, ym1, ym2, ym3 = pm(0), pm(1), pm(2), pm(3)
    # 先生成 subscription 类型的账单
    subs_with_bills = [
        # (sub_id, company_id, monthly_fee, follow_up_uid, [(year, month, paid_amount, status)])
        (sub_ids[0], None, Decimal("3000"), emp1_id, [(ym2[0], ym2[1], Decimal("3000"), "paid"), (ym1[0], ym1[1], Decimal("3000"), "paid"), (ym0[0], ym0[1], Decimal("0"), "unpaid")]),
        (sub_ids[1], None, Decimal("2500"), emp2_id, [(ym2[0], ym2[1], Decimal("2500"), "paid"), (ym1[0], ym1[1], Decimal("0"), "unpaid"), (ym0[0], ym0[1], Decimal("0"), "unpaid")]),
        (sub_ids[2], None, Decimal("8000"), emp1_id, [(ym2[0], ym2[1], Decimal("4000"), "partial"), (ym1[0], ym1[1], Decimal("0"), "unpaid")]),
        (sub_ids[3], None, Decimal("3500"), emp3_id, [(ym1[0], ym1[1], Decimal("3500"), "paid"), (ym0[0], ym0[1], Decimal("0"), "unpaid")]),
        (sub_ids[4], None, Decimal("12000"), emp2_id, [(ym3[0], ym3[1], Decimal("12000"), "paid")]),
        (sub_ids[5], None, Decimal("50000"), emp3_id, [(ym3[0], ym3[1], Decimal("20000"), "partial")]),
    ]
    bill_ids = []
    for sub_id, _, fee, fuid, months in subs_with_bills:
        sub = db.query(Subscription).filter(Subscription.id == sub_id).first()
        if not sub:
            continue
        for year, month, paid, status in months:
            b = Bill(tenant_id=tid, company_id=sub.company_id,
                    subscription_id=sub.id, bill_type="subscription",
                    billing_year=year, billing_month=month,
                    receivable_amount=fee, paid_amount=paid,
                    payment_status=status, is_overdue=(status == "unpaid" and (year, month) < (y, m)),
                    follow_up_user_id=fuid)
            db.add(b)
            bill_ids.append(b)

    # onetime 类型账单
    for op_id in onetime_ids:
        op = db.query(OneTimeProject).filter(OneTimeProject.id == op_id).first()
        if not op:
            continue
        if op.is_received:
            b = Bill(tenant_id=tid, company_id=op.company_id,
                    onetime_project_id=op.id, bill_type="onetime",
                    billing_year=op.receive_date.year, billing_month=op.receive_date.month,
                    receivable_amount=op.revenue, paid_amount=op.revenue,
                    payment_status="paid", is_overdue=False,
                    follow_up_user_id=op.owner_id)
        else:
            b = Bill(tenant_id=tid, company_id=op.company_id,
                    onetime_project_id=op.id, bill_type="onetime",
                    billing_year=op.completion_date.year, billing_month=op.completion_date.month,
                    receivable_amount=op.revenue, paid_amount=Decimal("0"),
                    payment_status="unpaid", is_overdue=True,
                    follow_up_user_id=op.owner_id)
        db.add(b)
        bill_ids.append(b)

    db.flush()
    print(f"  共创建 {len(bill_ids)} 条账单")
    for b in bill_ids[:5]:
        print(f"  账单 id={b.id}: company_id={b.company_id} {b.bill_type} {b.billing_year}-{b.billing_month} 应收={b.receivable_amount} 已收={b.paid_amount} 状态={b.payment_status}")
    if len(bill_ids) > 5:
        print(f"  ... (共 {len(bill_ids)} 条)")
    return [b.id for b in bill_ids]


def create_payments(db, tid, cust_ids, emp_ids, bill_ids):
    """创建收款记录：3 条已通过 + 2 条待核对（基于当前年月）"""
    print("\n=== 创建收款记录 ===")
    emp1_id, emp2_id, emp3_id = emp_ids
    today = date.today()
    y, m = today.year, today.month
    def pm(n, d=10):
        total = y * 12 + (m - 1) - n
        return date(total // 12, (total % 12) + 1, d)
    # (company_id, amount, payment_date, channel, submitter_id, verifier_id, status, bill_allocations)
    payments_data = [
        (cust_ids[0], Decimal("3000"), pm(2), "bank", emp1_id, emp2_id, "approved", [(bill_ids[0], Decimal("3000"))]),
        (cust_ids[1], Decimal("2500"), pm(2, 15), "alipay", emp2_id, emp1_id, "approved", [(bill_ids[3], Decimal("2500"))]),
        (cust_ids[3], Decimal("3500"), pm(1, 8), "wechat", emp3_id, emp2_id, "approved", [(bill_ids[6], Decimal("3500"))]),
        (cust_ids[0], Decimal("3000"), today.replace(day=min(today.day, 5) or 5), "bank", emp1_id, emp2_id, "pending", [(bill_ids[2], Decimal("3000"))]),
        (cust_ids[2], Decimal("4000"), today.replace(day=min(today.day, 8) or 8), "cash", emp1_id, emp2_id, "pending", []),
    ]
    pay_ids = []
    for cid, amt, pd, channel, sub_id, ver_id, status, allocs in payments_data:
        pr = PaymentRecord(tenant_id=tid, company_id=cid, amount=amt,
                          payment_date=pd, channel=channel, submitter_id=sub_id,
                          assigned_verifier_id=ver_id, verify_status=status,
                          usage_type="public",
                          reject_reason=None if status != "rejected" else "信息不全")
        db.add(pr)
        pay_ids.append(pr)
    db.flush()

    # 创建账单分配
    for pr, (_, _, _, _, _, _, _, allocs) in zip(pay_ids, payments_data):
        for bill_id, alloc_amt in allocs:
            db.add(PaymentBillAllocation(tenant_id=tid, payment_record_id=pr.id,
                                        bill_id=bill_id, allocation_amount=alloc_amt,
                                        source="payment"))
    db.flush()
    for p in pay_ids:
        print(f"  收款 id={p.id}: company_id={p.company_id} 金额={p.amount} 日期={p.payment_date} 状态={p.verify_status}")
    return pay_ids


def create_prepayment(db, tid, cust_ids):
    """创建客户预付款"""
    print("\n=== 创建客户预付款 ===")
    p = CustomerPrepayment(tenant_id=tid, company_id=cust_ids[2],
                          balance=Decimal("1500"), source="overpayment",
                          remark="2025年5月超额付款结转")
    db.add(p)
    db.flush()
    print(f"  预付款 id={p.id}: company_id={p.company_id} 余额={p.balance}")
    return p.id


def create_ledger_and_salary(db, tid, emp_ids, admin_id, cust_ids):
    """创建月结和薪资记录：前2月已锁定（基于当前年月）"""
    print("\n=== 创建月结和薪资 ===")
    today = date.today()
    y, m = today.year, today.month
    # 前2个月
    total = y * 12 + (m - 1) - 2
    lock_y, lock_m = total // 12, (total % 12) + 1
    # 月结记录
    ledger = LedgerValidation(tenant_id=tid, ledger_year=lock_y, ledger_month=lock_m,
                             status="locked", locked_by=admin_id,
                             locked_at=datetime.utcnow(),
                             calculation_status="completed")
    db.add(ledger)
    db.flush()
    print(f"  月结 id={ledger.id}: {lock_y}-{lock_m:02d} 已锁定")

    # 薪资记录（每个员工不同金额，更真实）
    salary_data = [
        (emp_ids[0], Decimal("5000"), Decimal("1500"), Decimal("800"), Decimal("500"), Decimal("200"), Decimal("100"), Decimal("7700")),
        (emp_ids[1], Decimal("5500"), Decimal("1200"), Decimal("600"), Decimal("300"), Decimal("150"), Decimal("80"), Decimal("7430")),
        (emp_ids[2], Decimal("4800"), Decimal("900"), Decimal("400"), Decimal("200"), Decimal("100"), Decimal("50"), Decimal("6250")),
    ]
    for uid, base, svc, sales, one, deduct, suppl, gross in salary_data:
        ms = MonthlySalary(tenant_id=tid, user_id=uid,
                          salary_year=lock_y, salary_month=lock_m,
                          base_salary=base, service_commission=svc,
                          sales_commission=sales, onetime_commission=one,
                          total_deduction=deduct, total_supplement=suppl,
                          bonus_amount=Decimal("0"), gross_payable=gross,
                          ledger_validation_id=ledger.id)
        db.add(ms)
    db.flush()
    print(f"  薪资：{lock_y}-{lock_m:02d} 共 {len(emp_ids)} 条")

    # 提成明细（用真实 company_id）
    commission_data = [
        (emp_ids[0], "service", cust_ids[0], Decimal("10000"), Decimal("0.1500"), Decimal("1500")),
        (emp_ids[0], "sales", cust_ids[1], Decimal("5000"), Decimal("0.1500"), Decimal("750")),
        (emp_ids[1], "service", cust_ids[1], Decimal("8000"), Decimal("0.1500"), Decimal("1200")),
        (emp_ids[2], "service", cust_ids[3], Decimal("6000"), Decimal("0.1500"), Decimal("900")),
    ]
    for uid, ctype, cid, base_amt, rate, amt in commission_data:
        cd = CommissionDetail(tenant_id=tid, user_id=uid,
                             commission_type=ctype,
                             company_id=cid,
                             billing_year=lock_y, billing_month=lock_m,
                             base_amount=base_amt, rate=rate,
                             commission_amount=amt,
                             net_amount=amt,
                             ledger_validation_id=ledger.id)
        db.add(cd)
    db.flush()
    print(f"  提成明细：{lock_y}-{lock_m:02d} 共 {len(commission_data)} 条")
    return ledger.id


def create_fee_history(db, tid, sub_ids):
    """创建月费变更历史（基于当前年月）"""
    print("\n=== 创建月费变更历史 ===")
    today = date.today()
    total = today.year * 12 + (today.month - 1) - 3
    eff_y, eff_m = total // 12, (total % 12) + 1
    fh = FeeHistory(tenant_id=tid, subscription_id=sub_ids[0],
                   old_fee=Decimal("2500"), new_fee=Decimal("3000"),
                   effective_date=date(eff_y, eff_m, 1), changed_by=1)
    db.add(fh)
    db.flush()
    print(f"  月费历史 id={fh.id}: sub_id={sub_ids[0]} {fh.old_fee} → {fh.new_fee} 生效日 {eff_y}-{eff_m:02d}")
    return fh.id


def create_cost_presets_and_bonus(db, tid):
    """创建成本预设和阶梯奖金"""
    print("\n=== 创建成本预设和阶梯奖金 ===")
    cost_data = [
        ("代账服务", Decimal("800")),
        ("税务咨询", Decimal("0")),
        ("社保代理", Decimal("3000")),
    ]
    for biz_type, cost in cost_data:
        db.add(CostPreset(tenant_id=tid, business_type=biz_type, default_cost=cost))

    bonus_data = [
        ("第一阶梯", Decimal("0"), Decimal("10000"), Decimal("0.01"), 1),
        ("第二阶梯", Decimal("10000"), Decimal("30000"), Decimal("0.015"), 2),
        ("第三阶梯", Decimal("30000"), None, Decimal("0.02"), 3),
    ]
    for name, mn, mx, rate, order in bonus_data:
        db.add(BonusTier(tenant_id=tid, tier_name=name, min_amount=mn,
                        max_amount=mx, bonus_rate=rate, sort_order=order))
    db.flush()
    print(f"  成本预设 {len(cost_data)} 条")
    print(f"  阶梯奖金 {len(bonus_data)} 条")


def main():
    db = SessionLocal()
    try:
        clean_all(db)
        tid, admin_id, emp1_id, emp2_id, emp3_id = create_tenant_and_users(db)
        emp_ids = [emp1_id, emp2_id, emp3_id]
        supplier_ids = create_suppliers(db, tid)
        cust_ids = create_customers(db, tid, emp1_id, emp2_id, emp3_id)
        sub_ids = create_subscriptions(db, tid, cust_ids, emp_ids, supplier_ids)
        onetime_ids = create_onetime_projects(db, tid, cust_ids, emp_ids, supplier_ids)
        bill_ids = create_bills(db, tid, sub_ids, onetime_ids, emp_ids)
        pay_ids = create_payments(db, tid, cust_ids, emp_ids, bill_ids)
        create_prepayment(db, tid, cust_ids)
        create_ledger_and_salary(db, tid, emp_ids, admin_id, cust_ids)
        create_fee_history(db, tid, sub_ids)
        create_cost_presets_and_bonus(db, tid)
        db.commit()
        print("\n=== 完成 ===")
        print(f"租户 ID: {tid}")
        print(f"管理员账号: demo_admin / 123456")
        print(f"员工账号: demo_emp1 / demo_emp2 / demo_emp3 (密码 123456)")
        print(f"平台管理员: admin / admin123")
    except Exception as e:
        db.rollback()
        print(f"错误: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
