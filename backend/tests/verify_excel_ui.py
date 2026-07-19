"""端到端验证：批量导入导出 + 收款核对补账单
完整流程：
1. super_admin 登录 → 生成注册码
2. 注册新租户 → 创建员工、客户、长期业务、账单
3. 注入 token 到浏览器 → 验证 UI 按钮
4. 通过 API 验证导出/导入/模板接口
5. 验证收款核对页 UI
"""
import sys
import time
import uuid
from playwright.sync_api import sync_playwright

API = "http://127.0.0.1:8000"
BASE = "http://127.0.0.1:5173"


def api_call(page, method, url, token=None, data=None):
    headers = {}
    if token:
        headers["Authorization"] = "Bearer " + token
    if method == "GET":
        return page.request.get(API + url, headers=headers)
    elif method == "POST":
        return page.request.post(API + url, headers=headers, data=data)
    elif method == "PUT":
        return page.request.put(API + url, headers=headers, data=data)


def setup_tenant(page):
    """创建测试租户：super_admin 登录 → 注册码 → 注册 → 创建数据"""
    # super_admin 登录
    r = api_call(page, "POST", "/api/auth/login", data={"username": "admin", "password": "admin123"})
    if r.status != 200:
        print(f"[FAIL] super_admin 登录失败：{r.text()}")
        return None
    admin_token = r.json()["data"]["token"]
    print("[OK] super_admin 登录")

    # 生成注册码
    r = api_call(page, "POST", "/api/admin/registration-codes",
                 token=admin_token,
                 data={"plan": "monthly", "duration_days": 30, "remark": "e2e验证"})
    if r.status != 200:
        print(f"[FAIL] 生成注册码失败：{r.text()}")
        return None
    reg_code = r.json()["data"]["code"]
    print(f"[OK] 注册码：{reg_code}")

    # 注册租户
    username = f"e2e_{uuid.uuid4().hex[:8]}"
    r = api_call(page, "POST", "/api/auth/register", data={
        "code": reg_code, "company_name": "E2E验证工作室", "name": "E2E管理员",
        "username": username, "phone": "13800001234", "password": "123456"
    })
    if r.status != 200:
        print(f"[FAIL] 注册失败：{r.text()}")
        return None
    data = r.json()["data"]
    tenant_token = data["token"]
    user = data["user"]
    print(f"[OK] 租户注册成功 username={username}")

    # 创建员工
    r = api_call(page, "POST", "/api/users", token=tenant_token, data={
        "username": f"emp_{uuid.uuid4().hex[:8]}", "name": "E2E员工",
        "password": "123456", "base_salary": 3000,
        "permissions": ["payment:submit", "payment:verify", "salary:view"],
        "data_scope": "SELF"
    })
    emp_id = r.json()["data"]["id"]
    print(f"[OK] 员工 id={emp_id}")

    # 创建客户
    r = api_call(page, "POST", "/api/customers", token=tenant_token, data={
        "name": "E2E测试客户", "region_tags": ["广州"], "is_new_customer": True,
        "service_start_date": "2025-06-01"
    })
    cust_id = r.json()["data"]["id"]
    print(f"[OK] 客户 id={cust_id}")

    # 创建长期业务
    r = api_call(page, "POST", "/api/subscriptions", token=tenant_token, data={
        "company_id": cust_id, "service_type": "代理记账", "billing_period": "monthly",
        "monthly_fee": 2000, "service_owner_id": emp_id, "start_date": "2025-06-01"
    })
    print(f"[OK] 长期业务")

    # 生成账单
    r = api_call(page, "POST", "/api/bills/generate", token=tenant_token, data={"year": 2025, "month": 7})
    print(f"[OK] 生成账单 {r.json()['data']['generated']} 笔")

    # 创建一笔无账单的收款（用于核对补充测试）
    r = api_call(page, "POST", "/api/payments", token=tenant_token, data={
        "company_id": cust_id, "amount": 2000, "payment_date": "2025-07-15",
        "channel": "bank", "assigned_verifier_id": emp_id, "bill_allocations": []
    })
    payment_id = r.json()["data"]["id"]
    print(f"[OK] 创建无账单收款 id={payment_id}（用于核对补充）")

    return {"token": tenant_token, "user": user, "payment_id": payment_id,
            "cust_id": cust_id, "username": username}


def inject_token(page, token, user):
    page.goto(BASE + "/login")
    page.wait_for_load_state("networkidle")
    page.evaluate("""([t, u]) => {
        localStorage.setItem('token', t);
        localStorage.setItem('user', JSON.stringify(u));
    }""", [token, user])
    print("[OK] token 已注入")


def verify_ui_buttons(page):
    pages = [
        ("/customers", "客户管理"),
        ("/suppliers", "供应商管理"),
        ("/subscriptions", "长期业务"),
        ("/onetime", "一次性业务"),
        ("/bills", "账单管理"),
    ]
    ok = True
    for path, name in pages:
        page.goto(BASE + path)
        page.wait_for_load_state("networkidle")
        time.sleep(1)
        ex = page.locator('button:has-text("导出 Excel")').count() > 0
        im = page.locator('button:has-text("导入 Excel")').count() > 0
        tp = page.locator('button:has-text("下载模板")').count() > 0
        if ex and im and tp:
            print(f"[OK] {name} 三按钮齐全")
        else:
            print(f"[FAIL] {name} ex={ex} im={im} tp={tp}")
            ok = False
    return ok


def verify_api_export(page, token):
    endpoints = [
        "/api/customers/export", "/api/suppliers/export",
        "/api/subscriptions/export", "/api/onetime-projects/export",
        "/api/bills/export",
    ]
    ok = True
    for ep in endpoints:
        r = page.request.get(API + ep, headers={"Authorization": "Bearer " + token})
        ct = r.headers.get("content-type", "")
        body = r.body()
        if r.status != 200 or "spreadsheetml" not in ct or len(body) < 50:
            print(f"[FAIL] {ep} status={r.status} ct={ct} size={len(body)}")
            ok = False
        else:
            print(f"[OK] {ep} ({len(body)} bytes)")
    return ok


def verify_api_template(page, token):
    endpoints = [
        "/api/customers/template", "/api/suppliers/template",
        "/api/subscriptions/template", "/api/onetime-projects/template",
        "/api/bills/template",
    ]
    ok = True
    for ep in endpoints:
        r = page.request.get(API + ep, headers={"Authorization": "Bearer " + token})
        if r.status != 200:
            print(f"[FAIL] {ep} status={r.status}")
            ok = False
        else:
            print(f"[OK] {ep} ({len(r.body())} bytes)")
    return ok


def verify_payment_verify_ui(page):
    page.goto(BASE + "/payment-verify")
    page.wait_for_load_state("networkidle")
    time.sleep(1.5)
    alloc_col = page.locator('th:has-text("账单分配")')
    if alloc_col.count() == 0:
        print("[FAIL] 缺少「账单分配」列")
        return False
    print("[OK] 「账单分配」列存在")
    btn = page.locator('button:has-text("补充账单")')
    print(f"[INFO] 「补充账单」按钮数量：{btn.count()}")
    return True


def verify_api_import(page, token):
    """验证导入：用 requests 库上传 xlsx"""
    import requests
    # 导出客户
    r = requests.get(API + "/api/customers/export",
                     headers={"Authorization": "Bearer " + token})
    xlsx_bytes = r.content
    # 上传到 import 接口
    files = {"file": ("customers.xlsx", xlsx_bytes,
                      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    r = requests.post(API + "/api/customers/import",
                      headers={"Authorization": "Bearer " + token},
                      files=files)
    if r.status_code != 200:
        print(f"[FAIL] import status={r.status_code} body={r.text}")
        return False
    data = r.json()["data"]
    print(f"[OK] 导入客户 success={data['success_count']} updated={data['updated_count']} created={data['created_count']} errors={len(data['errors'])}")
    return True


def verify_allocation_api(page, token, payment_id):
    """验证 PUT /api/payments/{pid}/allocations 接口"""
    import requests
    r = requests.get(API + "/api/bills?status=unpaid&page=1&page_size=200",
                     headers={"Authorization": "Bearer " + token})
    bills = r.json()["data"]["items"]
    if not bills:
        print("[FAIL] 无未付账单可测试")
        return False
    bill_id = bills[0]["id"]
    amt = float(bills[0]["receivable_amount"]) - float(bills[0]["paid_amount"])
    r = requests.put(API + f"/api/payments/{payment_id}/allocations",
                     headers={"Authorization": "Bearer " + token},
                     json={"bill_allocations": [{"bill_id": bill_id, "allocation_amount": amt}]})
    if r.status_code != 200:
        print(f"[FAIL] PUT allocations status={r.status_code} body={r.text}")
        return False
    r = requests.get(API + f"/api/payments/{payment_id}",
                     headers={"Authorization": "Bearer " + token})
    allocs = r.json()["data"]["bill_allocations"]
    if len(allocs) != 1 or allocs[0]["bill_id"] != bill_id:
        print(f"[FAIL] 分配记录未正确写入：{allocs}")
        return False
    print(f"[OK] 收款 {payment_id} 已补充账单 {bill_id}（分配 ¥{amt}）")
    return True


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context()
        page = ctx.new_page()
        ok = True
        try:
            setup = setup_tenant(page)
            if not setup:
                ok = False
            else:
                token = setup["token"]
                user = setup["user"]
                payment_id = setup["payment_id"]
                inject_token(page, token, user)
                print("\n--- UI 按钮验证 ---")
                ok &= verify_ui_buttons(page)
                print("\n--- API 导出验证 ---")
                ok &= verify_api_export(page, token)
                print("\n--- API 模板验证 ---")
                ok &= verify_api_template(page, token)
                print("\n--- API 导入验证 ---")
                ok &= verify_api_import(page, token)
                print("\n--- 收款核对 UI 验证 ---")
                ok &= verify_payment_verify_ui(page)
                print("\n--- 补充账单 API 验证 ---")
                ok &= verify_allocation_api(page, token, payment_id)
        except Exception as e:
            print(f"[ERROR] {e}")
            import traceback
            traceback.print_exc()
            ok = False
        finally:
            browser.close()
        print("\n========== 结果 ==========")
        print("全部通过" if ok else "有失败项")
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
