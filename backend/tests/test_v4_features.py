"""v4 功能完整测试脚本：验证 16 项需求改造

执行流程：
1. 登录获取 token（demo_admin / 123456）
2. 逐项验证 16 项需求
3. 输出测试报告
"""
import requests
import json
from datetime import date, datetime

BASE = "http://127.0.0.1:8000"
TODAY = date.today()
Y, M = TODAY.year, TODAY.month

# 测试结果记录
results = []  # [(需求编号, 测试项, 通过, 详情)]


def record(req_id, name, ok, detail=""):
    results.append((req_id, name, ok, detail))
    mark = "✓" if ok else "✗"
    print(f"  {mark} [{req_id}] {name}" + (f" - {detail}" if detail else ""))


def login(username="demo_admin", password="123456"):
    r = requests.post(f"{BASE}/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, f"登录失败: {r.status_code} {r.text}"
    return r.json()["data"]["token"]


def main():
    print(f"=== v4 功能测试开始（当前年月: {Y}-{M:02d}）===\n")
    token = login()
    h = {"Authorization": f"Bearer {token}"}
    user_info = requests.get(f"{BASE}/api/auth/me", headers=h).json()["data"]
    print(f"登录用户: {user_info['name']} (role={user_info['role']}, tenant_id={user_info['tenant_id']})\n")

    # ========== 需求 4: 收款渠道配置 ==========
    print("【需求 4】收款渠道配置")
    r = requests.get(f"{BASE}/api/payment-channels", headers=h)
    record(4, "查询收款渠道列表", r.status_code == 200, f"HTTP {r.status_code}")

    # 新增渠道
    r = requests.post(f"{BASE}/api/payment-channels", headers=h, json={
        "name": "测试银行", "code": "test_bank", "payee_name": "张三",
        "account_number": "6222001234567890", "account_type": "对公",
        "sort_order": 99, "is_active": True, "remark": "测试渠道"
    })
    ok_create_ch = r.status_code == 200
    record(4, "新增收款渠道", ok_create_ch, f"HTTP {r.status_code}")
    new_ch_id = r.json().get("data", {}).get("id") if ok_create_ch else None

    if new_ch_id:
        # 修改
        r = requests.put(f"{BASE}/api/payment-channels/{new_ch_id}", headers=h,
                         json={"name": "测试银行改", "is_active": False})
        record(4, "修改收款渠道", r.status_code == 200, f"HTTP {r.status_code}")
        # 删除
        r = requests.delete(f"{BASE}/api/payment-channels/{new_ch_id}", headers=h)
        record(4, "删除收款渠道", r.status_code == 200, f"HTTP {r.status_code}")

    # ========== 需求 5: 服务类型配置 ==========
    print("\n【需求 5】服务类型配置")
    r = requests.get(f"{BASE}/api/service-types", headers=h)
    record(5, "查询服务类型列表", r.status_code == 200, f"HTTP {r.status_code}")

    r = requests.post(f"{BASE}/api/service-types", headers=h, json={
        "name": "测试服务类型", "sort_order": 99, "is_active": True, "remark": "测试"
    })
    ok_create_st = r.status_code == 200
    record(5, "新增服务类型", ok_create_st, f"HTTP {r.status_code}")
    new_st_id = r.json().get("data", {}).get("id") if ok_create_st else None
    if new_st_id:
        r = requests.delete(f"{BASE}/api/service-types/{new_st_id}", headers=h)
        record(5, "删除服务类型", r.status_code == 200, f"HTTP {r.status_code}")

    # ========== 需求 3: 客户字段调整 ==========
    print("\n【需求 3】客户字段（contact_name/service_start_date）")
    r = requests.get(f"{BASE}/api/customers?page=1&page_size=1", headers=h)
    cust_data = r.json()["data"]["items"]
    if cust_data:
        c = cust_data[0]
        record(3, "返回 contact_name 字段", "contact_name" in c, f"contact_name={c.get('contact_name')}")
        record(3, "返回 service_start_date 字段", "service_start_date" in c, f"service_start_date={c.get('service_start_date')}")
    else:
        record(3, "客户列表不为空", False, "无客户数据")

    # ========== 需求 1 & 3: 新增客户（含 contact_name） ==========
    print("\n【需求 1 & 3】新增客户（含 contact_name）")
    new_cust = {
        "name": "测试客户_v4_001",
        "status": "active",
        "service_start_date": str(TODAY),
        "contact_name": "李测试",
        "contact_phone": "13900000001",
        "contact_email": "test001@example.com",
        "region_tags": ["测试区域"],
        "introducer_type": "external",
        "introducer_name": "外部介绍人"
    }
    r = requests.post(f"{BASE}/api/customers", headers=h, json=new_cust)
    ok_new_cust = r.status_code == 200
    record(1, "新增客户（含 contact_name）", ok_new_cust, f"HTTP {r.status_code}")
    new_cust_id = r.json().get("data", {}).get("id") if ok_new_cust else None

    # ========== 需求 2: 导出客户清单（两种模式） ==========
    print("\n【需求 2】导出客户清单（两种模式）")
    # 模式1：纯客户清单
    r = requests.get(f"{BASE}/api/customers/export", headers=h, params={"mode": "simple"}, stream=True)
    ok_simple = r.status_code == 200 and "spreadsheet" in r.headers.get("content-type", "")
    record(2, "模式1：纯客户清单导出", ok_simple, f"HTTP {r.status_code}, size={len(r.content)}")

    # 模式2：含业务清单
    r = requests.get(f"{BASE}/api/customers/export", headers=h, params={"mode": "with_business"}, stream=True)
    ok_with_biz = r.status_code == 200 and "spreadsheet" in r.headers.get("content-type", "")
    record(2, "模式2：含业务清单导出（多 sheet）", ok_with_biz, f"HTTP {r.status_code}, size={len(r.content)}")

    # ========== 需求 6 & 9: 长期业务（费用字段、无成本类型不选供应商、自动生成账单） ==========
    print("\n【需求 6 & 9】长期业务（费用/无成本类型/自动生账单）")
    if new_cust_id:
        # 获取一个员工 id 作为服务负责人
        r = requests.get(f"{BASE}/api/users?page=1&page_size=10", headers=h)
        emp_id = r.json()["data"]["items"][0]["id"]

        # 创建无成本类型的长期业务（不应选供应商）
        new_sub = {
            "company_id": new_cust_id,
            "service_type": "测试服务",
            "billing_period": "monthly",
            "monthly_fee": 5000,
            "is_cost_type": False,
            "monthly_cost": 0,
            "supplier_id": None,
            "service_owner_id": emp_id,
            "sales_owner_id": None,
            "start_date": str(TODAY)
        }
        r = requests.post(f"{BASE}/api/subscriptions", headers=h, json=new_sub)
        ok_new_sub = r.status_code == 200
        record(6, "新增长期业务（无成本类型不选供应商）", ok_new_sub, f"HTTP {r.status_code}")
        if ok_new_sub:
            resp_data = r.json().get("data", {})
            bills_gen = resp_data.get("bills_generated", 0)
            record(9, "自动生成一年账单", bills_gen > 0, f"生成 {bills_gen} 张账单")
            new_sub_id = resp_data.get("id")

            # 验证创建的长期业务没有 supplier_id
            r = requests.get(f"{BASE}/api/subscriptions?page=1&page_size=200", headers=h)
            sub_items = r.json()["data"]["items"]
            created_sub = next((s for s in sub_items if s["id"] == new_sub_id), None)
            if created_sub:
                record(6, "无成本类型时 supplier_id 为空", created_sub.get("supplier_id") is None,
                       f"supplier_id={created_sub.get('supplier_id')}")

            # ========== 需求 7: 变更费用、查看变更记录、停止服务 ==========
            print("\n【需求 7】变更费用 / 变更记录 / 停止服务")
            # 变更费用
            r = requests.post(f"{BASE}/api/subscriptions/{new_sub_id}/fee-change", headers=h,
                              json={"new_fee": 6000, "effective_date": str(TODAY)})
            record(7, "变更费用", r.status_code == 200, f"HTTP {r.status_code}")

            # 查看变更记录
            r = requests.get(f"{BASE}/api/subscriptions/{new_sub_id}/fee-history", headers=h)
            ok_history = r.status_code == 200 and len(r.json().get("data", [])) > 0
            record(7, "查看变更记录", ok_history, f"HTTP {r.status_code}, records={len(r.json().get('data', []))}")

            # 停止服务（PUT 方法）
            r = requests.put(f"{BASE}/api/subscriptions/{new_sub_id}/toggle", headers=h)
            ok_toggle = r.status_code == 200
            record(7, "停止服务（toggle）", ok_toggle, f"HTTP {r.status_code}, resp={r.json().get('data', {})}")

    # ========== 需求 8: 一次性业务自动产生账单 ==========
    print("\n【需求 8】一次性业务自动产生账单")
    if new_cust_id:
        r = requests.get(f"{BASE}/api/users?page=1&page_size=10", headers=h)
        emp_id = r.json()["data"]["items"][0]["id"]
        new_ot = {
            "company_id": new_cust_id,
            "project_type": "测试一次性业务",
            "revenue": 10000,
            "cost": 2000,
            "supplier_id": None,
            "owner_id": emp_id,
            "completion_date": str(TODAY)
        }
        r = requests.post(f"{BASE}/api/onetime-projects", headers=h, json=new_ot)
        ok_new_ot = r.status_code == 200
        record(8, "新增一次性业务", ok_new_ot, f"HTTP {r.status_code}")
        new_ot_id = r.json().get("data", {}).get("id") if ok_new_ot else None

        if new_ot_id:
            # 验证自动生成账单
            r = requests.get(f"{BASE}/api/bills?page=1&page_size=200&company_id={new_cust_id}", headers=h)
            bills = r.json()["data"]["items"]
            ot_bill = next((b for b in bills if b.get("onetime_project_id") == new_ot_id), None)
            record(8, "一次性业务自动生成账单", ot_bill is not None,
                   f"应收={ot_bill.get('receivable_amount') if ot_bill else '无'}")

    # ========== 需求 10: 收款填报（必选账单/无账单按周期生成） ==========
    print("\n【需求 10】收款填报（必选账单/按周期生成）")
    if new_cust_id:
        # 先测试不传账单会失败
        r = requests.get(f"{BASE}/api/users?page=1&page_size=10", headers=h)
        emp_id = r.json()["data"]["items"][0]["id"]
        bad_payment = {
            "company_id": new_cust_id, "amount": 1000, "payment_date": str(TODAY),
            "channel": "bank", "assigned_verifier_id": emp_id, "remark": "测试不传账单"
        }
        r = requests.post(f"{BASE}/api/payments", headers=h, json=bad_payment)
        record(10, "不传账单时拒绝创建", r.status_code == 400, f"HTTP {r.status_code}")

        # 测试按周期生成账单
        r = requests.post(f"{BASE}/api/bills/generate-for-company", headers=h, json={
            "company_id": new_cust_id,
            "start_year": Y, "start_month": M, "months": 3
        })
        ok_gen = r.status_code == 200
        record(10, "按周期生成账单（弹窗生成）", ok_gen, f"HTTP {r.status_code}, 生成={r.json().get('data', {}).get('generated')}")

        # 正常填报（含账单）
        r = requests.get(f"{BASE}/api/bills?page=1&page_size=200&company_id={new_cust_id}", headers=h)
        bills = r.json()["data"]["items"]
        unpaid_bill = next((b for b in bills if b["payment_status"] != "paid"), None)
        if unpaid_bill:
            good_payment = {
                "company_id": new_cust_id, "amount": 1000, "payment_date": str(TODAY),
                "channel": "bank", "assigned_verifier_id": emp_id, "remark": "测试正常填报",
                "bill_allocations": [{"bill_id": unpaid_bill["id"], "allocation_amount": 1000}]
            }
            r = requests.post(f"{BASE}/api/payments", headers=h, json=good_payment)
            ok_pay = r.status_code == 200
            record(10, "正常填报（含账单）", ok_pay, f"HTTP {r.status_code}")
            new_pay_id = r.json().get("data", {}).get("id") if ok_pay else None

            # ========== 需求 12 & 14 & 16: 收款核对（查看详情/驳回处理/租户管理员） ==========
            print("\n【需求 12 & 14 & 16】收款核对（查看详情/驳回处理/租户管理员）")
            # 查看收款详情（应包含 bill_info）
            r = requests.get(f"{BASE}/api/payments/{new_pay_id}", headers=h)
            ok_detail = r.status_code == 200
            pay_detail = r.json().get("data", {}) if ok_detail else {}
            record(12, "查看收款详情", ok_detail, f"HTTP {r.status_code}")
            if ok_detail and pay_detail.get("bill_allocations"):
                has_bill_info = any(a.get("bill_info") for a in pay_detail["bill_allocations"])
                record(12, "详情包含账单信息（bill_info）", has_bill_info,
                       f"bill_info={pay_detail['bill_allocations'][0].get('bill_info')}")

            # 驳回
            r = requests.post(f"{BASE}/api/payments/{new_pay_id}/verify", headers=h,
                              json={"action": "reject", "reject_reason": "测试驳回"})
            record(14, "驳回收款", r.status_code == 200, f"HTTP {r.status_code}")

            # 重新提交
            r = requests.post(f"{BASE}/api/payments/{new_pay_id}/resubmit", headers=h,
                              json={"remark": "重新提交测试", "bill_allocations": [{"bill_id": unpaid_bill["id"], "allocation_amount": 1000}]})
            record(14, "驳回后重新提交", r.status_code == 200, f"HTTP {r.status_code}")

            # 再次驳回然后作废
            r = requests.post(f"{BASE}/api/payments/{new_pay_id}/verify", headers=h,
                              json={"action": "reject", "reject_reason": "测试作废"})
            r = requests.post(f"{BASE}/api/payments/{new_pay_id}/void", headers=h)
            record(14, "驳回后作废", r.status_code == 200, f"HTTP {r.status_code}")

            # 验证租户管理员可以查看所有收款
            r = requests.get(f"{BASE}/api/payments?verify_status=pending&page=1&page_size=200", headers=h)
            record(16, "租户管理员查看所有收款", r.status_code == 200,
                   f"HTTP {r.status_code}, count={len(r.json().get('data', {}).get('items', []))}")

    # ========== 需求 13: 预付款明细界面 ==========
    print("\n【需求 13】预付款明细")
    r = requests.get(f"{BASE}/api/prepayments?page=1&page_size=200", headers=h)
    ok_prepay = r.status_code == 200
    record(13, "查询预付款列表", ok_prepay, f"HTTP {r.status_code}, count={len(r.json().get('data', {}).get('items', []))}")

    prepay_items = r.json().get("data", {}).get("items", []) if ok_prepay else []
    if prepay_items:
        first_prepay = prepay_items[0]
        prepay_id = first_prepay["id"]
        # 查看流水
        r = requests.get(f"{BASE}/api/prepayments/{prepay_id}/logs", headers=h)
        record(13, "查看预付款流水", r.status_code == 200, f"HTTP {r.status_code}")

    # ========== 需求 15: 薪资结算核对界面（账单/服务负责人） ==========
    print("\n【需求 15】薪资结算核对界面（账单/服务负责人）")
    r = requests.get(f"{BASE}/api/ledger/pre-calc-bills?year={Y}&month={M}", headers=h)
    ok_bills = r.status_code == 200
    record(15, "查询当月账单明细", ok_bills, f"HTTP {r.status_code}")
    if ok_bills:
        data = r.json()["data"]
        items = data.get("items", [])
        summary = data.get("summary", {})
        record(15, "返回账单汇总信息", "total" in summary and "total_receivable" in summary,
               f"total={summary.get('total')}, receivable={summary.get('total_receivable')}")
        if items:
            first = items[0]
            record(15, "账单包含服务负责人字段", "service_owner_name" in first,
                   f"service_owner_name={first.get('service_owner_name')}")
            record(15, "账单包含销售负责人字段", "sales_owner_name" in first,
                   f"sales_owner_name={first.get('sales_owner_name')}")

    # 导出账单明细
    r = requests.get(f"{BASE}/api/ledger/pre-calc-bills-export?year={Y}&month={M}", headers=h, stream=True)
    record(15, "导出账单明细 Excel", r.status_code == 200 and "spreadsheet" in r.headers.get("content-type", ""),
           f"HTTP {r.status_code}, size={len(r.content)}")

    # ========== 输出测试报告 ==========
    print("\n" + "=" * 60)
    print("=== 测试报告 ===")
    print("=" * 60)
    total = len(results)
    passed = sum(1 for r in results if r[2])
    failed = total - passed
    print(f"总测试项: {total}")
    print(f"通过: {passed}")
    print(f"失败: {failed}")
    print(f"通过率: {passed/total*100:.1f}%\n")

    if failed > 0:
        print("=== 失败项 ===")
        for req_id, name, ok, detail in results:
            if not ok:
                print(f"  ✗ [{req_id}] {name} - {detail}")

    return failed == 0


if __name__ == "__main__":
    ok = main()
    exit(0 if ok else 1)
