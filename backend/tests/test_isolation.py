"""测试多租户数据隔离（v3 核心安全测试）"""
import uuid


def test_tenant_isolation_customers(client, tenant_setup, second_tenant_setup):
    """租户A看不到租户B的客户"""
    # 租户1创建客户
    r = client.post("/api/customers", json={"name": "租户1客户"},
                    headers=tenant_setup["tenant_headers"])
    assert r.status_code == 200

    # 租户2创建客户
    r = client.post("/api/customers", json={"name": "租户2客户"},
                    headers=second_tenant_setup["tenant_headers"])
    assert r.status_code == 200

    # 租户1只能看到自己的客户
    r = client.get("/api/customers", headers=tenant_setup["tenant_headers"])
    names = [c["name"] for c in r.json()["data"]["items"]]
    assert "租户1客户" in names
    assert "租户2客户" not in names

    # 租户2只能看到自己的客户
    r = client.get("/api/customers", headers=second_tenant_setup["tenant_headers"])
    names = [c["name"] for c in r.json()["data"]["items"]]
    assert "租户2客户" in names
    assert "租户1客户" not in names


def test_tenant_isolation_suppliers(client, tenant_setup, second_tenant_setup):
    """租户间供应商隔离"""
    client.post("/api/suppliers", json={"name": "供应商A", "type": "刻章"},
                headers=tenant_setup["tenant_headers"])
    client.post("/api/suppliers", json={"name": "供应商B", "type": "审计"},
                headers=second_tenant_setup["tenant_headers"])

    r1 = client.get("/api/suppliers", headers=tenant_setup["tenant_headers"])
    r2 = client.get("/api/suppliers", headers=second_tenant_setup["tenant_headers"])
    names1 = [s["name"] for s in r1.json()["data"]["items"]]
    names2 = [s["name"] for s in r2.json()["data"]["items"]]
    assert "供应商A" in names1 and "供应商B" not in names1
    assert "供应商B" in names2 and "供应商A" not in names2


def test_tenant_isolation_bills(client, tenant_setup, second_tenant_setup):
    """租户间账单隔离"""
    # 租户1生成账单
    client.post("/api/bills/generate", json={"year": 2025, "month": 7},
                headers=tenant_setup["tenant_headers"])

    # 租户2看不到租户1的账单
    r = client.get("/api/bills?year=2025&month=7", headers=second_tenant_setup["tenant_headers"])
    assert r.json()["data"]["total"] == 0


def test_tenant_isolation_salaries(client, tenant_setup, second_tenant_setup):
    """租户间薪资隔离"""
    # 租户1做月度计算
    client.post("/api/bills/generate", json={"year": 2025, "month": 7},
                headers=tenant_setup["tenant_headers"])
    client.post("/api/ledger/validate-and-calculate", json={"year": 2025, "month": 7},
                headers=tenant_setup["tenant_headers"])

    # 租户2看不到租户1的薪资
    r = client.get("/api/salaries?year=2025&month=7", headers=second_tenant_setup["tenant_headers"])
    assert r.json()["data"]["total"] == 0


def test_readonly_blocks_write(client, tenant_setup, admin_headers):
    """套餐只读降级时写操作被拦截"""
    # super_admin 设为只读
    tenant_id = tenant_setup["tenant_id"]
    client.put(f"/api/admin/tenants/{tenant_id}/status", json={"status": "expired_readonly"},
               headers=admin_headers)

    # 尝试创建客户 → 403
    r = client.post("/api/customers", json={"name": "只读测试"},
                    headers=tenant_setup["tenant_headers"])
    assert r.status_code == 403

    # 恢复
    client.put(f"/api/admin/tenants/{tenant_id}/status",
               json={"status": "active", "plan": "monthly", "max_employees": 20},
               headers=admin_headers)
