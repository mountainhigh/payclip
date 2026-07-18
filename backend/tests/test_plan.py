"""测试套餐状态机与权限控制（v3）"""


def test_plan_status_machine(client, tenant_setup, admin_headers):
    """套餐状态机：active → expired_readonly → soft_deleted → 恢复"""
    tid = tenant_setup["tenant_id"]
    H = tenant_setup["tenant_headers"]
    AH = admin_headers

    # active → expired_readonly
    r = client.put(f"/api/admin/tenants/{tid}/status", json={"status": "expired_readonly"}, headers=AH)
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "expired_readonly"

    # 只读状态下写操作被拒
    r = client.post("/api/customers", json={"name": "只读测试"}, headers=H)
    assert r.status_code == 403

    # expired_readonly → soft_deleted
    r = client.put(f"/api/admin/tenants/{tid}/status", json={"status": "soft_deleted"}, headers=AH)
    assert r.status_code == 200

    # soft_deleted 状态登录被拒
    r = client.post("/api/auth/login", json={
        "username": tenant_setup["username"], "password": "123456"
    })
    assert r.status_code == 403

    # soft_deleted → active（恢复）
    r = client.put(f"/api/admin/tenants/{tid}/status",
                   json={"status": "active", "plan": "monthly", "max_employees": 20}, headers=AH)
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "active"

    # 恢复后可以正常写操作
    r = client.post("/api/customers", json={"name": "恢复后测试"}, headers=H)
    assert r.status_code == 200


def test_renew_tenant(client, tenant_setup, admin_headers):
    """续费功能"""
    tid = tenant_setup["tenant_id"]
    r = client.post(f"/api/admin/tenants/{tid}/renew", json={"plan": "yearly", "max_employees": 50},
                    headers=admin_headers)
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["plan"] == "yearly"
    assert data["max_employees"] == 50
    assert data["status"] == "active"


def test_employee_limit(client, tenant_setup):
    """员工数上限检查"""
    H = tenant_setup["tenant_headers"]
    # 当前已有 2 个用户（管理员 + 测试员工），max_employees=3
    # 尝试创建第 3 个（应该成功）
    r = client.post("/api/users", json={
        "username": "emp2_test", "name": "员工2", "password": "123456",
        "permissions": ["payment:submit"], "data_scope": "SELF"
    }, headers=H)
    assert r.status_code == 200

    # 尝试创建第 4 个（应该失败，超限）
    r = client.post("/api/users", json={
        "username": "emp3_test", "name": "员工3", "password": "123456",
        "permissions": ["payment:submit"], "data_scope": "SELF"
    }, headers=H)
    assert r.status_code == 403
    assert "上限" in r.json().get("detail", "")


def test_super_admin_access(client, admin_headers):
    """super_admin 可以访问租户管理接口"""
    r = client.get("/api/admin/tenants", headers=admin_headers)
    assert r.status_code == 200

    r = client.get("/api/admin/registration-codes", headers=admin_headers)
    assert r.status_code == 200


def test_tenant_admin_cannot_access_super_admin_api(client, tenant_setup):
    """租户管理员不能访问平台管理接口"""
    H = tenant_setup["tenant_headers"]
    r = client.get("/api/admin/tenants", headers=H)
    assert r.status_code == 403

    r = client.post("/api/admin/registration-codes", json={"plan": "trial"}, headers=H)
    assert r.status_code == 403
