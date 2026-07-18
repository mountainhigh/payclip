"""端到端 API 功能测试（手动脚本）— 验证已发现的 bug 并覆盖更多业务路径"""
import uuid
import requests

BASE = "http://localhost:8000/api"
PASS = 0
FAIL = 0
RESULTS = []


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        RESULTS.append(f"  PASS  {name}")
    else:
        FAIL += 1
        RESULTS.append(f"  FAIL  {name}  {detail}")


def main():
    s = requests.Session()

    # 1) super_admin 登录
    r = s.post(f"{BASE}/auth/login", json={"username": "admin", "password": "admin123"})
    check("super_admin 登录", r.status_code == 200, r.text)
    admin_token = r.json()["data"]["token"]
    H_admin = {"Authorization": f"Bearer {admin_token}"}

    # 2) 错误密码
    r = s.post(f"{BASE}/auth/login", json={"username": "admin", "password": "wrong"})
    check("错误密码 401", r.status_code == 401, r.text)

    # 3) 生成注册码
    r = s.post(f"{BASE}/admin/registration-codes",
               json={"plan": "trial", "duration_days": 30, "remark": "e2e测试"},
               headers=H_admin)
    check("生成注册码", r.status_code == 200, r.text)
    reg_code = r.json()["data"]["code"]

    # 4) 注册租户
    uname = f"e2e_{uuid.uuid4().hex[:8]}"
    r = s.post(f"{BASE}/auth/register", json={
        "code": reg_code, "company_name": "E2E工作室", "name": "E2E管理员",
        "username": uname, "phone": "13800001111", "password": "123456"
    })
    check("注册租户", r.status_code == 200, r.text)
    tenant_token = r.json()["data"]["token"]
    tenant_id = r.json()["data"]["user"]["tenant_id"]
    H_t = {"Authorization": f"Bearer {tenant_token}"}

    # 5) 重复使用注册码（应失败）
    r = s.post(f"{BASE}/auth/register", json={
        "code": reg_code, "company_name": "X", "name": "Y",
        "username": f"dup_{uuid.uuid4().hex[:6]}", "phone": "13800002222", "password": "123456"
    })
    check("重复使用注册码 400", r.status_code == 400, r.text)

    # 6) 创建员工
    emp_uname = f"emp_{uuid.uuid4().hex[:8]}"
    r = s.post(f"{BASE}/users", json={
        "username": emp_uname, "name": "测试员工", "password": "123456",
        "base_salary": 3000, "permissions": ["payment:submit", "salary:view"],
        "data_scope": "SELF"
    }, headers=H_t)
    check("创建员工", r.status_code == 200, r.text)
    emp_id = r.json()["data"]["id"]

    # 7) 创建客户
    r = s.post(f"{BASE}/customers", json={
        "name": "E2E客户A", "region_tags": ["广州"],
        "is_new_customer": True, "service_start_date": "2025-01-01"
    }, headers=H_t)
    check("创建客户", r.status_code == 200, r.text)
    cust_id = r.json()["data"]["id"]

    # 8) 创建长期业务（注意 billing_period：前端用 month，测试用 monthly）
    r = s.post(f"{BASE}/subscriptions", json={
        "company_id": cust_id, "service_type": "代理记账",
        "billing_period": "monthly", "monthly_fee": 2000,
        "service_owner_id": emp_id, "start_date": "2025-01-01"
    }, headers=H_t)
    check("创建长期业务", r.status_code == 200, r.text)
    sub_id = r.json()["data"]["id"]

    # 9) 生成账单
    r = s.post(f"{BASE}/bills/generate", json={"year": 2025, "month": 7}, headers=H_t)
    check("生成账单", r.status_code == 200 and r.json()["data"]["generated"] >= 1, r.text)

    # 10) 查看账单
    r = s.get(f"{BASE}/bills?year=2025&month=7", headers=H_t)
    bills = r.json()["data"]["items"]
    check("查看账单", len(bills) >= 1, r.text)
    bill_id = bills[0]["id"]

    # 11) 提交收款
    r = s.post(f"{BASE}/payments", json={
        "company_id": cust_id, "amount": 2000,
        "payment_date": "2025-07-15", "channel": "bank",
        "assigned_verifier_id": emp_id,
        "bill_allocations": [{"bill_id": bill_id, "allocation_amount": 2000}]
    }, headers=H_t)
    check("提交收款", r.status_code == 200, r.text)
    pay_id = r.json()["data"]["id"]

    # 12) 上传截图（用一张 1x1 png）
    import base64
    png_1x1 = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
    )
    r = s.post(f"{BASE}/payments/{pay_id}/screenshots",
               files={"file": ("test.png", png_1x1, "image/png")},
               headers=H_t)
    check("上传截图", r.status_code == 200, r.text)

    # 13) 驳回收款（验证 reject_reason 是否保存）—— 修复后应能正确保存
    r = s.post(f"{BASE}/payments/{pay_id}/verify",
               json={"action": "reject", "reject_reason": "测试驳回原因"},
               headers=H_t)
    check("驳回收款", r.status_code == 200, r.text)

    r = s.get(f"{BASE}/payments?verify_status=rejected", headers=H_t)
    items = r.json()["data"]["items"]
    rejected = [p for p in items if p["id"] == pay_id]
    if rejected:
        actual_reason = rejected[0].get("reject_reason")
        check("驳回原因字段正确保存（reject_reason）",
              actual_reason == "测试驳回原因",
              f"actual={actual_reason!r}")
    else:
        check("驳回记录可见", False, "未找到驳回记录")

    # 14) 重新提交并审核通过
    r = s.post(f"{BASE}/payments", json={
        "company_id": cust_id, "amount": 2000,
        "payment_date": "2025-07-16", "channel": "bank",
        "assigned_verifier_id": emp_id,
        "bill_allocations": [{"bill_id": bill_id, "allocation_amount": 2000}]
    }, headers=H_t)
    pay_id2 = r.json()["data"]["id"]
    r = s.post(f"{BASE}/payments/{pay_id2}/verify", json={"action": "approve"}, headers=H_t)
    check("审核通过", r.status_code == 200, r.text)

    # 15) 月度计算
    r = s.post(f"{BASE}/ledger/validate-and-calculate", json={"year": 2025, "month": 7}, headers=H_t)
    check("月度计算", r.status_code == 200 and r.json()["data"]["status"] == "locked", r.text)

    # 16) 薪资查询
    r = s.get(f"{BASE}/salaries?year=2025&month=7", headers=H_t)
    salaries = r.json()["data"]["items"]
    emp_salary = [s for s in salaries if s["user_id"] == emp_id]
    check("薪资计算正确（底薪3000+提成300=3300）",
          len(emp_salary) == 1 and float(emp_salary[0]["gross_payable"]) == 3300.0,
          r.text)

    # 17) 跨租户隔离：super_admin 可见全部租户数据（设计如此，平台管理员视角）
    r = s.get(f"{BASE}/customers", headers=H_admin)
    check("super_admin 可见所有租户数据（设计如此）",
          r.json()["data"]["total"] >= 1, r.text)

    # 18) 注册码列表
    r = s.get(f"{BASE}/admin/registration-codes", headers=H_admin)
    check("注册码列表", r.status_code == 200 and r.json()["data"]["total"] >= 1, r.text)

    # 19) 租户列表
    r = s.get(f"{BASE}/admin/tenants", headers=H_admin)
    check("租户列表", r.status_code == 200 and r.json()["data"]["total"] >= 1, r.text)

    # 20) 邀请员工
    r = s.post(f"{BASE}/tenant/invitations", json={}, headers=H_t)
    check("生成邀请链接", r.status_code == 200, r.text)
    invite_token = r.json()["data"]["token"]

    # 21) 员工注册
    r = s.post(f"{BASE}/auth/register-employee", json={
        "token": invite_token, "name": "新员工",
        "username": f"emp2_{uuid.uuid4().hex[:8]}", "phone": "13800000003", "password": "123456"
    })
    check("员工凭邀请注册", r.status_code == 200, r.text)

    # 22) 改密
    r = s.put(f"{BASE}/auth/password", json={"old_password": "123456", "new_password": "654321"},
              headers=H_t)
    check("修改密码", r.status_code == 200, r.text)

    print("\n========== 端到端 API 测试结果 ==========")
    for line in RESULTS:
        print(line)
    print(f"\n总计：{PASS} 通过，{FAIL} 失败")


if __name__ == "__main__":
    main()
