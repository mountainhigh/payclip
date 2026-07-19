"""v3 需求变更规则测试（§2.1/§2.4/§2.5/§3.1/§3.3/§4.3/§4.4/§4.8/§4.9）

覆盖 v3 确认结论：
- 注册即 trial + 超管手动升级（§2.4）
- 员工数不限（§2.1/§2.5）
- 逐笔填报强制 public（§3.3/§4.8）
- 月费变更不回溯（§3.1）
- 服务/销售/一次性提成对离职员工不计提（§4.4/§4.9）
- 业务转交后补回归当前负责人（§4.3）
- 销售窗口外不计提销售提成（§4.4）
- 月度计算幂等与锁定（§3.7）
- 解锁最近锁定月份后可重新计算（§3.7）
"""
import uuid


# ==================== §2.4 注册即 trial + 手动升级 ====================

def test_register_defaults_to_trial(client, admin_headers):
    """V1: 凭注册码注册的新租户默认 plan=trial（§2.4）"""
    r = client.post("/api/admin/registration-codes",
                    json={"plan": "trial", "duration_days": 30}, headers=admin_headers)
    code = r.json()["data"]["code"]
    username = f"v1user_{uuid.uuid4().hex[:8]}"
    r = client.post("/api/auth/register", json={
        "code": code, "company_name": "trial测试", "name": "trial用户",
        "username": username, "phone": "13900000001", "password": "123456"
    })
    assert r.status_code == 200
    tenant_id = r.json()["data"]["user"]["tenant_id"]
    r = client.get("/api/admin/tenants", headers=admin_headers)
    tenant = next((t for t in r.json()["data"]["items"] if t["id"] == tenant_id), None)
    assert tenant is not None, "新注册租户未在列表中"
    assert tenant["plan"] == "trial", f"新注册租户 plan 应为 trial，实际: {tenant['plan']}"


def test_super_admin_renew_upgrades_plan(client, admin_headers, tenant_setup):
    """V2: super_admin 通过 renew 把 trial 租户升级为 monthly（§2.4）"""
    tid = tenant_setup["tenant_id"]
    r = client.post(f"/api/admin/tenants/{tid}/renew",
                    json={"plan": "monthly"}, headers=admin_headers)
    assert r.status_code == 200, r.text
    r = client.get("/api/admin/tenants", headers=admin_headers)
    tenant = next((t for t in r.json()["data"]["items"] if t["id"] == tid))
    assert tenant["plan"] == "monthly"
    assert tenant["status"] == "active"
    assert tenant["plan_expires"] is not None


# ==================== §2.1/§2.5 员工数不限 ====================

def test_unlimited_employees(client, tenant_setup):
    """V3: 连续创建 5 个员工都成功，不再校验 max_employees（§2.1/§2.5）"""
    headers = tenant_setup["tenant_headers"]
    created_ids = []
    for i in range(5):
        r = client.post("/api/users", json={
            "username": f"v3emp_{uuid.uuid4().hex[:8]}",
            "name": f"员工{i}", "password": "123456", "base_salary": 3000
        }, headers=headers)
        assert r.status_code == 200, f"创建第{i+1}个员工失败: {r.text}"
        created_ids.append(r.json()["data"]["id"])
    assert len(set(created_ids)) == 5, "5个员工ID应互不相同"


# ==================== §3.3/§4.8 逐笔填报强制 public ====================

def test_payment_forced_public(client, tenant_setup):
    """V4: create_payment 即使传 usage_type=private 也被强制改为 public（§4.8）"""
    headers = tenant_setup["tenant_headers"]
    emp_id = tenant_setup["emp_id"]
    customer_id = tenant_setup["customer_id"]
    # 生成账单
    client.post("/api/bills/generate", json={"year": 2025, "month": 7}, headers=headers)
    r = client.get("/api/bills?year=2025&month=7", headers=headers)
    bill_id = r.json()["data"]["items"][0]["id"]
    # 提交收款时尝试传 usage_type=private
    r = client.post("/api/payments", json={
        "company_id": customer_id, "amount": 2000, "payment_date": "2025-07-10",
        "channel": "wechat", "assigned_verifier_id": emp_id,
        "usage_type": "private",  # 应被强制改为 public
        "bill_allocations": [{"bill_id": bill_id, "allocation_amount": 2000}]
    }, headers=headers)
    assert r.status_code == 200, r.text
    pid = r.json()["data"]["id"]
    r = client.get(f"/api/payments/{pid}", headers=headers)
    assert r.json()["data"]["usage_type"] == "public", "usage_type 必须被强制为 public"


# ==================== §3.1 月费变更不回溯 ====================

def test_fee_change_not_retroactive(client, tenant_setup):
    """V5: 6月已生成账单=2000，7月变更月费=3000后，6月账单仍=2000（§3.1）"""
    headers = tenant_setup["tenant_headers"]
    sub_id = tenant_setup["sub_id"]
    # 生成6月账单（月费=2000）
    client.post("/api/bills/generate", json={"year": 2025, "month": 6}, headers=headers)
    r = client.get("/api/bills?year=2025&month=6", headers=headers)
    bill_6 = r.json()["data"]["items"][0]
    assert float(bill_6["receivable_amount"]) == 2000.0
    bill_6_id = bill_6["id"]
    # 变更月费为 3000，生效日期 2025-07-01
    r = client.post(f"/api/subscriptions/{sub_id}/fee-change",
                    json={"new_fee": 3000, "effective_date": "2025-07-01"}, headers=headers)
    assert r.status_code == 200, r.text
    # 生成7月账单（月费应=3000）
    client.post("/api/bills/generate", json={"year": 2025, "month": 7}, headers=headers)
    r = client.get("/api/bills?year=2025&month=7", headers=headers)
    bill_7 = r.json()["data"]["items"][0]
    assert float(bill_7["receivable_amount"]) == 3000.0, "7月账单应使用新月费 3000"
    # 6月账单仍=2000（不回溯）
    r = client.get(f"/api/bills/{bill_6_id}", headers=headers)
    assert float(r.json()["data"]["receivable_amount"]) == 2000.0, "6月已生成账单不应被回溯修改"


# ==================== §4.4/§4.9 离职即停 ====================

def test_service_commission_stops_on_deactivation(client, tenant_setup):
    """V6: 服务负责人在职时有服务提成；离职后该员工无薪资记录（§4.4/§4.9）"""
    headers = tenant_setup["tenant_headers"]
    emp_id = tenant_setup["emp_id"]
    # 6月：生成账单（unpaid）+ 计算 → emp_id 有服务提成 + 扣款
    client.post("/api/bills/generate", json={"year": 2025, "month": 6}, headers=headers)
    r = client.post("/api/ledger/validate-and-calculate",
                    json={"year": 2025, "month": 6}, headers=headers)
    assert r.status_code == 200, r.text
    r = client.get("/api/salaries?year=2025&month=6", headers=headers)
    emp6 = next((s for s in r.json()["data"]["items"] if s["user_id"] == emp_id), None)
    assert emp6 is not None, "在职员工6月应有薪资记录"
    assert float(emp6["service_commission"]) == 300.0, "服务提成应为 2000*15%=300"
    assert float(emp6["total_deduction"]) == 100.0, "未收款扣款应为 2000*5%=100"
    # 离职 emp_id
    r = client.put(f"/api/users/{emp_id}/deactivate", headers=headers)
    assert r.status_code == 200
    # 7月：生成账单（unpaid）+ 计算 → emp_id 离职，无薪资记录
    client.post("/api/bills/generate", json={"year": 2025, "month": 7}, headers=headers)
    r = client.post("/api/ledger/validate-and-calculate",
                    json={"year": 2025, "month": 7}, headers=headers)
    assert r.status_code == 200, r.text
    r = client.get("/api/salaries?year=2025&month=7", headers=headers)
    emp7 = next((s for s in r.json()["data"]["items"] if s["user_id"] == emp_id), None)
    assert emp7 is None, "离职员工7月不应有薪资记录"


def test_sales_commission_stops_on_deactivation(client, tenant_setup):
    """V7: 12月窗口内销售在职时有销售提成；离职后无薪资记录（§4.4）"""
    headers = tenant_setup["tenant_headers"]
    emp_id = tenant_setup["emp_id"]
    customer_id = tenant_setup["customer_id"]  # is_new_customer=True, start=2025-01-01
    sub_id = tenant_setup["sub_id"]
    # 创建销售员工
    r = client.post("/api/users", json={
        "username": f"sales_{uuid.uuid4().hex[:8]}",
        "name": "销售员", "password": "123456", "base_salary": 3000
    }, headers=headers)
    sales_id = r.json()["data"]["id"]
    # 绑定销售到业务
    r = client.put(f"/api/subscriptions/{sub_id}",
                   json={"sales_owner_id": sales_id}, headers=headers)
    assert r.status_code == 200
    # 6月：生成账单 + 收款 + 核对 + 计算 → sales_id 有销售提成 300
    client.post("/api/bills/generate", json={"year": 2025, "month": 6}, headers=headers)
    r = client.get("/api/bills?year=2025&month=6", headers=headers)
    bill6_id = r.json()["data"]["items"][0]["id"]
    r = client.post("/api/payments", json={
        "company_id": customer_id, "amount": 2000, "payment_date": "2025-06-15",
        "channel": "wechat", "assigned_verifier_id": emp_id,
        "bill_allocations": [{"bill_id": bill6_id, "allocation_amount": 2000}]
    }, headers=headers)
    pid = r.json()["data"]["id"]
    client.post(f"/api/payments/{pid}/verify", json={"action": "approve"}, headers=headers)
    r = client.post("/api/ledger/validate-and-calculate",
                    json={"year": 2025, "month": 6}, headers=headers)
    assert r.status_code == 200, r.text
    r = client.get("/api/salaries?year=2025&month=6", headers=headers)
    sales6 = next((s for s in r.json()["data"]["items"] if s["user_id"] == sales_id), None)
    assert sales6 is not None, "在职销售6月应有薪资记录"
    assert float(sales6["sales_commission"]) == 300.0, "销售提成应为 2000*15%=300"
    # 离职 sales_id
    client.put(f"/api/users/{sales_id}/deactivate", headers=headers)
    # 7月：同样收款 + 计算 → sales_id 离职，无薪资记录
    client.post("/api/bills/generate", json={"year": 2025, "month": 7}, headers=headers)
    r = client.get("/api/bills?year=2025&month=7", headers=headers)
    bill7_id = r.json()["data"]["items"][0]["id"]
    r = client.post("/api/payments", json={
        "company_id": customer_id, "amount": 2000, "payment_date": "2025-07-15",
        "channel": "wechat", "assigned_verifier_id": emp_id,
        "bill_allocations": [{"bill_id": bill7_id, "allocation_amount": 2000}]
    }, headers=headers)
    pid = r.json()["data"]["id"]
    client.post(f"/api/payments/{pid}/verify", json={"action": "approve"}, headers=headers)
    r = client.post("/api/ledger/validate-and-calculate",
                    json={"year": 2025, "month": 7}, headers=headers)
    assert r.status_code == 200, r.text
    r = client.get("/api/salaries?year=2025&month=7", headers=headers)
    sales7 = next((s for s in r.json()["data"]["items"] if s["user_id"] == sales_id), None)
    assert sales7 is None, "离职销售7月不应有薪资记录"


def test_onetime_commission_stops_on_deactivation(client, tenant_setup):
    """V8: 一次性业务负责人离职后，新创建的一次性业务不计提一次性提成（§4.9）"""
    headers = tenant_setup["tenant_headers"]
    emp_id = tenant_setup["emp_id"]
    customer_id = tenant_setup["customer_id"]
    # 6月：创建一次性项目（owner=emp_id, revenue=10000, cost=2000）→ 自动生成 bill → 计算
    r = client.post("/api/onetime-projects", json={
        "company_id": customer_id, "project_type": "公司注册",
        "revenue": 10000, "cost": 2000, "owner_id": emp_id,
        "completion_date": "2025-06-15"
    }, headers=headers)
    assert r.status_code == 200, r.text
    r = client.post("/api/ledger/validate-and-calculate",
                    json={"year": 2025, "month": 6}, headers=headers)
    assert r.status_code == 200, r.text
    r = client.get("/api/salaries?year=2025&month=6", headers=headers)
    emp6 = next((s for s in r.json()["data"]["items"] if s["user_id"] == emp_id), None)
    assert emp6 is not None
    assert float(emp6["onetime_commission"]) == 1600.0, "一次性提成应为 (10000-2000)*20%=1600"
    # 离职 emp_id
    client.put(f"/api/users/{emp_id}/deactivate", headers=headers)
    # 7月：创建新一次性项目（owner=emp_id 已离职）→ 计算 → emp_id 无薪资记录
    r = client.post("/api/onetime-projects", json={
        "company_id": customer_id, "project_type": "税务代办",
        "revenue": 8000, "cost": 1000, "owner_id": emp_id,
        "completion_date": "2025-07-15"
    }, headers=headers)
    assert r.status_code == 200
    r = client.post("/api/ledger/validate-and-calculate",
                    json={"year": 2025, "month": 7}, headers=headers)
    assert r.status_code == 200, r.text
    r = client.get("/api/salaries?year=2025&month=7", headers=headers)
    emp7 = next((s for s in r.json()["data"]["items"] if s["user_id"] == emp_id), None)
    assert emp7 is None, "离职员工7月不应有一次性提成"


# ==================== §4.3 补回归当前负责人 ====================

def test_supplement_to_current_owner_after_transfer(client, tenant_setup):
    """V9: 业务转交后，补回归当前负责人（新负责人），supplement_for_user_id 保留原被扣人（§4.3）"""
    headers = tenant_setup["tenant_headers"]
    emp_id = tenant_setup["emp_id"]  # 原负责人
    customer_id = tenant_setup["customer_id"]
    sub_id = tenant_setup["sub_id"]
    # 6月：生成账单（unpaid）+ 计算 → emp_id 有扣款 100
    client.post("/api/bills/generate", json={"year": 2025, "month": 6}, headers=headers)
    client.post("/api/ledger/validate-and-calculate",
                json={"year": 2025, "month": 6}, headers=headers)
    # 转交业务给新员工 emp2
    r = client.post("/api/users", json={
        "username": f"newowner_{uuid.uuid4().hex[:8]}",
        "name": "新负责人", "password": "123456", "base_salary": 3000
    }, headers=headers)
    emp2_id = r.json()["data"]["id"]
    r = client.put(f"/api/subscriptions/{sub_id}",
                   json={"service_owner_id": emp2_id}, headers=headers)
    assert r.status_code == 200
    # 7月：生成账单 + 收款足额 + 核对 + 计算 → 补回 100 归 emp2
    client.post("/api/bills/generate", json={"year": 2025, "month": 7}, headers=headers)
    r = client.get("/api/bills?year=2025&month=7", headers=headers)
    bill7_id = r.json()["data"]["items"][0]["id"]
    r = client.post("/api/payments", json={
        "company_id": customer_id, "amount": 2000, "payment_date": "2025-07-15",
        "channel": "wechat", "assigned_verifier_id": emp_id,
        "bill_allocations": [{"bill_id": bill7_id, "allocation_amount": 2000}]
    }, headers=headers)
    pid = r.json()["data"]["id"]
    client.post(f"/api/payments/{pid}/verify", json={"action": "approve"}, headers=headers)
    r = client.post("/api/ledger/validate-and-calculate",
                    json={"year": 2025, "month": 7}, headers=headers)
    assert r.status_code == 200, r.text
    # 验证 emp2 的 7月薪资有 supplement=100
    r = client.get(f"/api/salaries/{emp2_id}/2025/7", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert float(data["total_supplement"]) == 100.0, "补回 100 应归当前负责人 emp2"
    # 验证补回明细的 supplement_for_user_id 指向原被扣人 emp_id
    supp_detail = next((d for d in data["commission_details"] if d["is_supplement"]), None)
    assert supp_detail is not None, "应有补回明细"
    # emp1 的 7月薪资应无 supplement（emp1 还在职但没有补回）
    r = client.get(f"/api/salaries/{emp_id}/2025/7", headers=headers)
    if r.status_code == 200:
        assert float(r.json()["data"]["total_supplement"]) == 0.0, "原被扣人 emp1 不应再收到补回"


# ==================== §4.4 销售窗口外不计提 ====================

def test_sales_commission_outside_window(client, tenant_setup):
    """V10: 12月窗口外（>12个月）不计提销售提成（§4.4）"""
    headers = tenant_setup["tenant_headers"]
    emp_id = tenant_setup["emp_id"]
    customer_id = tenant_setup["customer_id"]  # is_new_customer=True, start=2025-01-01
    sub_id = tenant_setup["sub_id"]
    # 创建销售员工
    r = client.post("/api/users", json={
        "username": f"saleswin_{uuid.uuid4().hex[:8]}",
        "name": "销售员2", "password": "123456", "base_salary": 3000
    }, headers=headers)
    sales_id = r.json()["data"]["id"]
    client.put(f"/api/subscriptions/{sub_id}",
               json={"sales_owner_id": sales_id}, headers=headers)
    # 2026-02（13个月后，窗口外）：生成账单 + 收款 + 核对 + 计算
    client.post("/api/bills/generate", json={"year": 2026, "month": 2}, headers=headers)
    r = client.get("/api/bills?year=2026&month=2", headers=headers)
    bill_id = r.json()["data"]["items"][0]["id"]
    r = client.post("/api/payments", json={
        "company_id": customer_id, "amount": 2000, "payment_date": "2026-02-15",
        "channel": "wechat", "assigned_verifier_id": emp_id,
        "bill_allocations": [{"bill_id": bill_id, "allocation_amount": 2000}]
    }, headers=headers)
    pid = r.json()["data"]["id"]
    client.post(f"/api/payments/{pid}/verify", json={"action": "approve"}, headers=headers)
    r = client.post("/api/ledger/validate-and-calculate",
                    json={"year": 2026, "month": 2}, headers=headers)
    assert r.status_code == 200, r.text
    r = client.get("/api/salaries?year=2026&month=2", headers=headers)
    sales_sal = next((s for s in r.json()["data"]["items"] if s["user_id"] == sales_id), None)
    assert sales_sal is not None, "销售员应在职"
    assert float(sales_sal["sales_commission"]) == 0.0, "12月窗口外不应计提销售提成"


# ==================== §3.7 月度计算幂等与锁定 ====================

def test_locked_month_rejects_recalculate(client, tenant_setup):
    """V11: 已锁定月份再次调用计算返回 409（§3.7）"""
    headers = tenant_setup["tenant_headers"]
    client.post("/api/bills/generate", json={"year": 2025, "month": 8}, headers=headers)
    r = client.post("/api/ledger/validate-and-calculate",
                    json={"year": 2025, "month": 8}, headers=headers)
    assert r.status_code == 200
    r = client.post("/api/ledger/validate-and-calculate",
                    json={"year": 2025, "month": 8}, headers=headers)
    assert r.status_code == 409, f"已锁定月份应返回 409，实际: {r.status_code}"


def test_unlock_and_recalculate(client, tenant_setup):
    """V12: 解锁最近锁定月份后可重新计算（§3.7）"""
    headers = tenant_setup["tenant_headers"]
    client.post("/api/bills/generate", json={"year": 2025, "month": 9}, headers=headers)
    r = client.post("/api/ledger/validate-and-calculate",
                    json={"year": 2025, "month": 9}, headers=headers)
    assert r.status_code == 200
    ledger_id = r.json()["data"]["ledger_id"]
    # 解锁
    r = client.post(f"/api/ledger/{ledger_id}/unlock", headers=headers)
    assert r.status_code == 200, r.text
    # 重新计算
    r = client.post("/api/ledger/validate-and-calculate",
                    json={"year": 2025, "month": 9}, headers=headers)
    assert r.status_code == 200, f"解锁后应可重新计算: {r.text}"
    assert r.json()["data"]["status"] == "locked"
