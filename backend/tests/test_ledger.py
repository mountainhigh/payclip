"""月结计算引擎完整测试（需求1）

覆盖场景：
1. 基础月结：长期业务服务提成 + 一次性业务提成 + 底薪
2. 未付账单扣款 5%
3. 已付账单不扣款
4. 服务负责人离职跳过服务提成
5. 一次性业务负责人离职跳过提成
6. 幂等锁定（重复调用返回 409）
7. 撤销后重算结果一致
8. 已付补回：历史扣款在本月已付时补回
9. 销售提成（新客销售窗口内 + 已审核公款分配）
10. 销售负责人离职跳过销售提成
"""
import pytest
from decimal import Decimal
from app.database import SessionLocal
from app.models import (User, Bill, Subscription, OneTimeProject, Company,
                        CommissionDetail, MonthlySalary, LedgerValidation,
                        PaymentRecord, PaymentBillAllocation)


# ==================== 辅助函数 ====================

def _create_employee(client, tenant_headers, name="员工A", base_salary=3000):
    """创建员工并返回 (id, username)"""
    import uuid
    username = f"emp_{uuid.uuid4().hex[:8]}"
    r = client.post("/api/users", json={
        "username": username, "name": name, "password": "123456",
        "base_salary": base_salary,
        "permissions": ["payment:submit", "salary:view"],
        "data_scope": "SELF"
    }, headers=tenant_headers)
    assert r.status_code == 200, r.text
    return r.json()["data"]["id"], username


def _generate_bills(client, tenant_headers, year, month):
    """生成长期业务账单"""
    r = client.post("/api/bills/generate", json={"year": year, "month": month},
                    headers=tenant_headers)
    assert r.status_code == 200, r.text
    return r.json()["data"]["generated"]


def _mark_bill_paid(db, tenant_id, sub_id, year, month):
    """直接把指定 subscription 的某月账单标记为 paid（绕过付款流程，简化测试）"""
    bill = db.query(Bill).filter(
        Bill.tenant_id == tenant_id, Bill.subscription_id == sub_id,
        Bill.billing_year == year, Bill.billing_month == month
    ).first()
    if bill:
        bill.payment_status = "paid"
        bill.paid_amount = bill.receivable_amount
    db.commit()
    return bill


def _set_user_active(db, user_id, is_active):
    """直接修改用户 is_active 状态"""
    u = db.query(User).filter(User.id == user_id).first()
    if u:
        u.is_active = is_active
        db.commit()
    return u


def _run_ledger(client, tenant_headers, year, month):
    """触发月结计算并返回响应"""
    r = client.post("/api/ledger/validate-and-calculate",
                    json={"year": year, "month": month}, headers=tenant_headers)
    return r


def _get_salary(db, tenant_id, user_id, year, month):
    """取员工的月结薪资记录"""
    return db.query(MonthlySalary).filter(
        MonthlySalary.tenant_id == tenant_id, MonthlySalary.user_id == user_id,
        MonthlySalary.salary_year == year, MonthlySalary.salary_month == month
    ).first()


def _get_commissions(db, tenant_id, user_id, year, month, only_non_supplement=True):
    """取员工的提成明细"""
    q = db.query(CommissionDetail).filter(
        CommissionDetail.tenant_id == tenant_id, CommissionDetail.user_id == user_id,
        CommissionDetail.billing_year == year, CommissionDetail.billing_month == month)
    if only_non_supplement:
        q = q.filter(CommissionDetail.is_supplement == False)
    return q.all()


# ==================== 测试用例 ====================

def test_ledger_basic_calc(client, tenant_setup):
    """基础月结：长期业务服务提成(15%) + 一次性业务提成(20%) + 底薪"""
    tenant_headers = tenant_setup["tenant_headers"]
    tenant_id = tenant_setup["tenant_id"]
    emp_id = tenant_setup["emp_id"]
    customer_id = tenant_setup["customer_id"]
    sub_id = tenant_setup["sub_id"]

    # 1. 生成 2025-01 长期业务账单（月费 2000，未付）
    _generate_bills(client, tenant_headers, 2025, 1)

    # 2. 创建一次性业务（已收，毛利 = 10000 - 2000 = 8000）
    r = client.post("/api/onetime-projects", json={
        "company_id": customer_id, "project_type": "审计",
        "revenue": 10000, "cost": 2000, "owner_id": emp_id,
        "completion_date": "2025-01-15"
    }, headers=tenant_headers)
    assert r.status_code == 200, r.text
    onetime_id = r.json()["data"]["id"]
    # 标记一次性业务收款（账单变 paid）
    r = client.put(f"/api/onetime-projects/{onetime_id}/receive",
                   json={"receive_date": "2025-01-20"}, headers=tenant_headers)
    assert r.status_code == 200, r.text

    # 3. 触发月结
    r = _run_ledger(client, tenant_headers, 2025, 1)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["status"] == "locked"
    assert data["salary_count"] >= 1

    # 4. 校验员工薪资
    db = SessionLocal()
    try:
        sal = _get_salary(db, tenant_id, emp_id, 2025, 1)
        assert sal is not None, "员工薪资记录不存在"
        # 服务提成 = 2000 × 15% = 300，未付扣款 = 2000 × 5% = 100
        # 一次性提成 = 8000 × 20% = 1600，已收不扣
        # 总薪资 = 3000(底薪) + 300(服务) + 1600(一次性) - 100(扣款) = 4800
        assert float(sal.service_commission) == 300.0, f"服务提成错误: {sal.service_commission}"
        assert float(sal.onetime_commission) == 1600.0, f"一次性提成错误: {sal.onetime_commission}"
        assert float(sal.total_deduction) == 100.0, f"扣款错误: {sal.total_deduction}"
        assert float(sal.gross_payable) == 4800.0, f"总薪资错误: {sal.gross_payable}"
    finally:
        db.close()


def test_ledger_unpaid_deduction(client, tenant_setup):
    """未付账单扣款 5%：长期业务月费 2000 未付，扣款 = 100"""
    tenant_headers = tenant_setup["tenant_headers"]
    tenant_id = tenant_setup["tenant_id"]
    emp_id = tenant_setup["emp_id"]
    sub_id = tenant_setup["sub_id"]

    _generate_bills(client, tenant_headers, 2025, 1)
    r = _run_ledger(client, tenant_headers, 2025, 1)
    assert r.status_code == 200, r.text

    db = SessionLocal()
    try:
        cds = _get_commissions(db, tenant_id, emp_id, 2025, 1)
        svc_cds = [c for c in cds if c.commission_type == "service"]
        assert len(svc_cds) >= 1
        # 未付扣款 = 2000 × 5% = 100
        assert float(svc_cds[0].deduction_amount) == 100.0
        # 净额 = 300 - 100 = 200
        assert float(svc_cds[0].net_amount) == 200.0
    finally:
        db.close()


def test_ledger_paid_no_deduction(client, tenant_setup):
    """已付账单不扣款：长期业务月费 2000 已付，扣款 = 0"""
    tenant_headers = tenant_setup["tenant_headers"]
    tenant_id = tenant_setup["tenant_id"]
    emp_id = tenant_setup["emp_id"]
    sub_id = tenant_setup["sub_id"]

    _generate_bills(client, tenant_headers, 2025, 1)
    # 标记已付
    db = SessionLocal()
    try:
        _mark_bill_paid(db, tenant_id, sub_id, 2025, 1)
    finally:
        db.close()

    r = _run_ledger(client, tenant_headers, 2025, 1)
    assert r.status_code == 200, r.text

    db = SessionLocal()
    try:
        cds = _get_commissions(db, tenant_id, emp_id, 2025, 1)
        svc_cds = [c for c in cds if c.commission_type == "service"]
        assert len(svc_cds) >= 1
        assert float(svc_cds[0].deduction_amount) == 0.0
        assert float(svc_cds[0].net_amount) == 300.0
    finally:
        db.close()


def test_ledger_owner_resigned(client, tenant_setup):
    """服务负责人离职：跳过服务提成（不生成 service CommissionDetail）"""
    tenant_headers = tenant_setup["tenant_headers"]
    tenant_id = tenant_setup["tenant_id"]
    emp_id = tenant_setup["emp_id"]
    sub_id = tenant_setup["sub_id"]

    _generate_bills(client, tenant_headers, 2025, 1)
    # 标记员工离职
    db = SessionLocal()
    try:
        _set_user_active(db, emp_id, False)
    finally:
        db.close()

    r = _run_ledger(client, tenant_headers, 2025, 1)
    assert r.status_code == 200, r.text

    db = SessionLocal()
    try:
        # 员工离职后不应生成服务提成
        cds = _get_commissions(db, tenant_id, emp_id, 2025, 1)
        svc_cds = [c for c in cds if c.commission_type == "service"]
        assert len(svc_cds) == 0, f"离职员工不应有服务提成: {svc_cds}"
        # 也不应有薪资记录（active_users 不含离职员工）
        sal = _get_salary(db, tenant_id, emp_id, 2025, 1)
        assert sal is None, "离职员工不应有薪资记录"
    finally:
        db.close()


def test_ledger_onetime_owner_resigned(client, tenant_setup):
    """一次性业务负责人离职：跳过一次性提成"""
    tenant_headers = tenant_setup["tenant_headers"]
    tenant_id = tenant_setup["tenant_id"]
    emp_id = tenant_setup["emp_id"]
    customer_id = tenant_setup["customer_id"]

    # 创建一次性业务
    r = client.post("/api/onetime-projects", json={
        "company_id": customer_id, "project_type": "审计",
        "revenue": 10000, "cost": 2000, "owner_id": emp_id,
        "completion_date": "2025-01-15"
    }, headers=tenant_headers)
    assert r.status_code == 200, r.text

    # 标记员工离职
    db = SessionLocal()
    try:
        _set_user_active(db, emp_id, False)
    finally:
        db.close()

    r = _run_ledger(client, tenant_headers, 2025, 1)
    assert r.status_code == 200, r.text

    db = SessionLocal()
    try:
        cds = _get_commissions(db, tenant_id, emp_id, 2025, 1)
        ot_cds = [c for c in cds if c.commission_type == "onetime"]
        assert len(ot_cds) == 0, f"离职员工不应有一次提成: {ot_cds}"
    finally:
        db.close()


def test_ledger_idempotent_lock(client, tenant_setup):
    """幂等锁定：重复调用返回 409"""
    tenant_headers = tenant_setup["tenant_headers"]
    _generate_bills(client, tenant_headers, 2025, 1)

    r = _run_ledger(client, tenant_headers, 2025, 1)
    assert r.status_code == 200, r.text

    # 再次调用应返回 409
    r2 = _run_ledger(client, tenant_headers, 2025, 1)
    assert r2.status_code == 409, f"重复锁定应返回 409，实际: {r2.status_code} {r2.text}"


def test_ledger_unlock_recalc(client, tenant_setup):
    """撤销后重算结果一致"""
    tenant_headers = tenant_setup["tenant_headers"]
    tenant_id = tenant_setup["tenant_id"]
    emp_id = tenant_setup["emp_id"]
    sub_id = tenant_setup["sub_id"]

    _generate_bills(client, tenant_headers, 2025, 1)
    r = _run_ledger(client, tenant_headers, 2025, 1)
    assert r.status_code == 200, r.text
    ledger_id = r.json()["data"]["ledger_id"]

    # 记录第一次结果
    db = SessionLocal()
    try:
        sal1 = _get_salary(db, tenant_id, emp_id, 2025, 1)
        assert sal1 is not None
        gross1 = float(sal1.gross_payable)
        svc1 = float(sal1.service_commission)
    finally:
        db.close()

    # 撤销锁定
    r = client.post(f"/api/ledger/{ledger_id}/unlock", headers=tenant_headers)
    assert r.status_code == 200, r.text

    # 重新计算
    r = _run_ledger(client, tenant_headers, 2025, 1)
    assert r.status_code == 200, r.text

    # 校验结果一致
    db = SessionLocal()
    try:
        sal2 = _get_salary(db, tenant_id, emp_id, 2025, 1)
        assert sal2 is not None
        assert float(sal2.gross_payable) == gross1
        assert float(sal2.service_commission) == svc1
    finally:
        db.close()


def test_ledger_paid_supplement(client, tenant_setup):
    """已付补回：第一月未付扣款，第二月已付时补回"""
    tenant_headers = tenant_setup["tenant_headers"]
    tenant_id = tenant_setup["tenant_id"]
    emp_id = tenant_setup["emp_id"]
    sub_id = tenant_setup["sub_id"]

    # 第一月（2025-01）：生成未付账单 → 月结 → 扣款 100
    _generate_bills(client, tenant_headers, 2025, 1)
    r = _run_ledger(client, tenant_headers, 2025, 1)
    assert r.status_code == 200, r.text

    db = SessionLocal()
    try:
        cds1 = _get_commissions(db, tenant_id, emp_id, 2025, 1)
        svc1 = [c for c in cds1 if c.commission_type == "service"]
        assert len(svc1) >= 1
        assert float(svc1[0].deduction_amount) == 100.0
    finally:
        db.close()

    # 第二月（2025-02）：生成账单 → 标记为 paid → 月结 → 应补回 100
    _generate_bills(client, tenant_headers, 2025, 2)
    db = SessionLocal()
    try:
        _mark_bill_paid(db, tenant_id, sub_id, 2025, 2)
    finally:
        db.close()

    r = _run_ledger(client, tenant_headers, 2025, 2)
    assert r.status_code == 200, r.text

    db = SessionLocal()
    try:
        # 2 月应有补回记录（is_supplement=True, supplement_amount=100）
        sups = db.query(CommissionDetail).filter(
            CommissionDetail.tenant_id == tenant_id, CommissionDetail.user_id == emp_id,
            CommissionDetail.billing_year == 2025, CommissionDetail.billing_month == 2,
            CommissionDetail.is_supplement == True
        ).all()
        assert len(sups) >= 1, "应有补回记录"
        assert float(sups[0].supplement_amount) == 100.0, f"补回金额错误: {sups[0].supplement_amount}"
    finally:
        db.close()


def test_ledger_sales_commission_in_window(client, tenant_setup):
    """销售提成：新客户首月 + 已审核公款分配 → 销售提成 15%"""
    tenant_headers = tenant_setup["tenant_headers"]
    tenant_id = tenant_setup["tenant_id"]
    customer_id = tenant_setup["customer_id"]
    sub_id = tenant_setup["sub_id"]
    # tenant_setup 创建的 customer 是新客户（is_new_customer=True, service_start_date=2025-01-01）

    # 1. 创建销售员工
    sales_id, _ = _create_employee(client, tenant_headers, name="销售员", base_salary=0)

    # 2. 给长期业务设置 sales_owner_id
    db = SessionLocal()
    try:
        sub = db.query(Subscription).filter(Subscription.id == sub_id).first()
        sub.sales_owner_id = sales_id
        db.commit()
    finally:
        db.close()

    # 3. 生成 2025-01 账单
    _generate_bills(client, tenant_headers, 2025, 1)
    # 获取 2025-01 账单 id
    db = SessionLocal()
    try:
        bill = db.query(Bill).filter(
            Bill.tenant_id == tenant_id, Bill.subscription_id == sub_id,
            Bill.billing_year == 2025, Bill.billing_month == 1
        ).first()
        bill_id = bill.id
        # 取租户管理员 id（作为 assigned_verifier_id）
        admin = db.query(User).filter(User.tenant_id == tenant_id, User.role == "tenant_admin").first()
        verifier_id = admin.id
    finally:
        db.close()

    # 4. 创建一笔 1000 元的公款收款（分配到该账单 1000 元）
    r = client.post("/api/payments", json={
        "company_id": customer_id, "amount": 1000, "payment_date": "2025-01-10",
        "channel": "wechat", "assigned_verifier_id": verifier_id,
        "bill_allocations": [{"bill_id": bill_id, "allocation_amount": 1000}]
    }, headers=tenant_headers)
    assert r.status_code == 200, r.text
    payment_id = r.json()["data"]["id"]

    # 5. 核对通过（账单变 paid）
    r = client.post(f"/api/payments/{payment_id}/verify",
                    json={"action": "approve"}, headers=tenant_headers)
    assert r.status_code == 200, r.text

    # 6. 月结
    r = _run_ledger(client, tenant_headers, 2025, 1)
    assert r.status_code == 200, r.text

    # 7. 校验销售提成 = 1000 × 15% = 150
    db = SessionLocal()
    try:
        sal = _get_salary(db, tenant_id, sales_id, 2025, 1)
        assert sal is not None, "销售员薪资记录不存在"
        assert float(sal.sales_commission) == 150.0, f"销售提成错误: {sal.sales_commission}"
        assert float(sal.gross_payable) == 150.0
    finally:
        db.close()


def test_ledger_sales_resigned(client, tenant_setup):
    """销售负责人离职：跳过销售提成"""
    tenant_headers = tenant_setup["tenant_headers"]
    tenant_id = tenant_setup["tenant_id"]
    sub_id = tenant_setup["sub_id"]
    customer_id = tenant_setup["customer_id"]

    # 1. 创建销售员工
    sales_id, _ = _create_employee(client, tenant_headers, name="销售员", base_salary=0)

    # 2. 设置 sales_owner_id
    db = SessionLocal()
    try:
        sub = db.query(Subscription).filter(Subscription.id == sub_id).first()
        sub.sales_owner_id = sales_id
        db.commit()
    finally:
        db.close()

    # 3. 生成账单 + 创建公款 + 审核通过
    _generate_bills(client, tenant_headers, 2025, 1)
    db = SessionLocal()
    try:
        bill = db.query(Bill).filter(
            Bill.tenant_id == tenant_id, Bill.subscription_id == sub_id,
            Bill.billing_year == 2025, Bill.billing_month == 1
        ).first()
        bill_id = bill.id
        admin = db.query(User).filter(User.tenant_id == tenant_id, User.role == "tenant_admin").first()
        verifier_id = admin.id
    finally:
        db.close()

    r = client.post("/api/payments", json={
        "company_id": customer_id, "amount": 1000, "payment_date": "2025-01-10",
        "channel": "wechat", "assigned_verifier_id": verifier_id,
        "bill_allocations": [{"bill_id": bill_id, "allocation_amount": 1000}]
    }, headers=tenant_headers)
    payment_id = r.json()["data"]["id"]
    client.post(f"/api/payments/{payment_id}/verify",
                json={"action": "approve"}, headers=tenant_headers)

    # 4. 标记销售员工离职
    db = SessionLocal()
    try:
        _set_user_active(db, sales_id, False)
    finally:
        db.close()

    # 5. 月结
    r = _run_ledger(client, tenant_headers, 2025, 1)
    assert r.status_code == 200, r.text

    # 6. 校验无销售提成
    db = SessionLocal()
    try:
        # 离职销售员不应有薪资记录
        sal = _get_salary(db, tenant_id, sales_id, 2025, 1)
        assert sal is None, "离职销售员不应有薪资记录"
        # 也不应有 sales 类型的 CommissionDetail
        sales_cds = db.query(CommissionDetail).filter(
            CommissionDetail.tenant_id == tenant_id, CommissionDetail.user_id == sales_id,
            CommissionDetail.billing_year == 2025, CommissionDetail.billing_month == 1,
            CommissionDetail.commission_type == "sales"
        ).all()
        assert len(sales_cds) == 0, f"离职销售员不应有销售提成: {sales_cds}"
    finally:
        db.close()
