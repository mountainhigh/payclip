"""逐页面 API 验证脚本：用 demo_admin 登录后访问所有页面接口"""
import requests
from datetime import date

BASE = "http://127.0.0.1:8000"
TODAY = date.today()
Y, M = TODAY.year, TODAY.month

def main():
    # 登录
    r = requests.post(f"{BASE}/api/auth/login", json={"username": "demo_admin", "password": "123456"})
    assert r.status_code == 200, f"登录失败: {r.status_code} {r.text}"
    token = r.json()["data"]["token"]
    h = {"Authorization": f"Bearer {token}"}
    print(f"✓ 登录成功: demo_admin (tenant_id={r.json()['data']['user']['tenant_id']})")
    print(f"  当前年月: {Y}-{M:02d}")

    pages = [
        ("工作台", "/api/customers?page=1&page_size=1", None),
        ("客户管理", "/api/customers?page=1&page_size=200", None),
        ("供应商管理", "/api/suppliers?page=1&page_size=200", None),
        ("长期业务", "/api/subscriptions?page=1&page_size=200", None),
        ("一次性业务", "/api/onetime-projects?page=1&page_size=200", None),
        ("账单管理", f"/api/bills?page=1&page_size=200&year={Y}&month={M}", None),
        ("收款填报(客户下拉)", "/api/customers?page=1&page_size=500", None),
        ("收款核对", "/api/payments?verify_status=pending&page=1&page_size=200", None),
        ("薪资管理", f"/api/salaries?year={Y}&month={M}&page=1&page_size=200", None),
        ("报表-区域", f"/api/reports/region?year={Y}&month={M}", None),
        ("报表-成本", f"/api/reports/cost?year={Y}&month={M}", None),
        ("报表-趋势", f"/api/reports/trend?end_year={Y}&end_month={M}", None),
        ("系统-用户管理", "/api/users?page=1&page_size=200", None),
        ("系统-成本预设", "/api/cost-presets", None),
        ("系统-阶梯奖金", "/api/bonus-tiers", None),
        ("系统-月结状态", "/api/ledger/status?page=1&page_size=50", None),
    ]

    print("\n=== 逐页面验证 ===")
    all_pass = True
    for name, url, _ in pages:
        try:
            r = requests.get(f"{BASE}{url}", headers=h)
            if r.status_code == 200:
                data = r.json().get("data", {})
                if isinstance(data, dict) and "items" in data:
                    cnt = len(data["items"])
                    total = data.get("total", cnt)
                    print(f"✓ {name}: {cnt} 条 (total={total})")
                elif isinstance(data, list):
                    print(f"✓ {name}: {len(data)} 条")
                else:
                    print(f"✓ {name}: OK")
            else:
                print(f"✗ {name}: HTTP {r.status_code} - {r.text[:100]}")
                all_pass = False
        except Exception as e:
            print(f"✗ {name}: 异常 {e}")
            all_pass = False

    # 平台管理员专属页面
    print("\n=== 平台管理员页面（用 admin 登录）===")
    r = requests.post(f"{BASE}/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200
    admin_token = r.json()["data"]["token"]
    ah = {"Authorization": f"Bearer {admin_token}"}

    admin_pages = [
        ("租户管理", "/api/admin/tenants?page=1&page_size=100"),
        ("注册码管理", "/api/admin/registration-codes?page=1&page_size=100"),
    ]
    for name, url in admin_pages:
        try:
            r = requests.get(f"{BASE}{url}", headers=ah)
            if r.status_code == 200:
                data = r.json().get("data", {})
                cnt = len(data.get("items", [])) if isinstance(data, dict) else 0
                print(f"✓ {name}: {cnt} 条")
            else:
                print(f"✗ {name}: HTTP {r.status_code}")
                all_pass = False
        except Exception as e:
            print(f"✗ {name}: 异常 {e}")
            all_pass = False

    print(f"\n=== 结果: {'全部通过' if all_pass else '存在失败'} ===")
    return all_pass


if __name__ == "__main__":
    main()
