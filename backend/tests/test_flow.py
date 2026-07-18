"""测试端到端业务流（v3 多租户版）"""
from decimal import Decimal


def test_full_business_flow(client, tenant_setup):
    """完整业务流：客户→业务→账单→收款→核对→提成→薪资"""
    H = tenant_setup["tenant_headers"]
    emp_id = tenant_setup["emp_id"]
    customer_id = tenant_setup["customer_id"]
    sub_id = tenant_setup["sub_id"]

    # 生成账单
    r = client.post("/api/bills/generate", json={"year": 2025, "month": 7}, headers=H)
    assert r.status_code == 200
    assert r.json()["data"]["generated"] >= 1

    # 查看账单
    r = client.get("/api/bills?year=2025&month=7", headers=H)
    bills = r.json()["data"]["items"]
    assert len(bills) >= 1
    bill = bills[0]
    assert float(bill["receivable_amount"]) == 2000.0
    bill_id = bill["id"]

    # 提交收款
    r = client.post("/api/payments", json={
        "company_id": customer_id, "amount": 2000,
        "payment_date": "2025-07-15", "channel": "bank",
        "assigned_verifier_id": tenant_setup["emp_id"],
        "bill_allocations": [{"bill_id": bill_id, "allocation_amount": 2000}]
    }, headers=H)
    assert r.status_code == 200
    pay_id = r.json()["data"]["id"]

    # 核对通过
    r = client.post(f"/api/payments/{pay_id}/verify", json={"action": "approve"}, headers=H)
    assert r.status_code == 200

    # 检查账单已付清
    r = client.get(f"/api/bills/{bill_id}", headers=H)
    assert r.json()["data"]["payment_status"] == "paid"

    # 月度计算
    r = client.post("/api/ledger/validate-and-calculate", json={"year": 2025, "month": 7}, headers=H)
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["status"] == "locked"
    assert data["salary_count"] >= 1

    # 检查薪资
    r = client.get("/api/salaries?year=2025&month=7", headers=H)
    salaries = r.json()["data"]["items"]
    assert len(salaries) >= 1
    emp_salary = [s for s in salaries if s["user_id"] == emp_id][0]
    # 底薪3000 + 服务提成300（2000×15%）= 3300
    assert float(emp_salary["base_salary"]) == 3000.0
    assert float(emp_salary["service_commission"]) == 300.0
    assert float(emp_salary["gross_payable"]) == 3300.0


def test_deduction_and_supplement(client, tenant_setup):
    """欠费扣款与补回逻辑"""
    H = tenant_setup["tenant_headers"]
    emp_id = tenant_setup["emp_id"]

    # 第一个月不收款 → 欠费扣款
    client.post("/api/bills/generate", json={"year": 2025, "month": 6}, headers=H)
    r = client.post("/api/ledger/validate-and-calculate", json={"year": 2025, "month": 6}, headers=H)
    assert r.status_code == 200

    # 查看扣款
    r = client.get(f"/api/salaries/{emp_id}/2025/6", headers=H)
    assert r.status_code == 200
    detail = r.json()["data"]
    # 欠费扣款 = 月费 × 5% = 100
    assert float(detail["total_deduction"]) == 100.0
    # 服务提成 = 300，扣款 100，应发 = 底薪 + 300 - 100 = 3200
    assert float(detail["gross_payable"]) == 3200.0

    # 第二个月收款并计算 → 补回
    client.post("/api/bills/generate", json={"year": 2025, "month": 7}, headers=H)
    r = client.get("/api/bills?year=2025&month=7", headers=H)
    bill_id = r.json()["data"]["items"][0]["id"]

    client.post("/api/payments", json={
        "company_id": tenant_setup["customer_id"], "amount": 2000,
        "payment_date": "2025-07-15", "channel": "bank",
        "assigned_verifier_id": emp_id,
        "bill_allocations": [{"bill_id": bill_id, "allocation_amount": 2000}]
    }, headers=H)
    pay_id = client.get("/api/payments?verify_status=pending", headers=H).json()["data"]["items"][0]["id"]
    client.post(f"/api/payments/{pay_id}/verify", json={"action": "approve"}, headers=H)

    r = client.post("/api/ledger/validate-and-calculate", json={"year": 2025, "month": 7}, headers=H)
    assert r.status_code == 200

    # 检查补回
    r = client.get(f"/api/salaries/{emp_id}/2025/7", headers=H)
    detail = r.json()["data"]
    # 补回 = 100
    assert float(detail["total_supplement"]) == 100.0
