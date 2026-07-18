"""测试认证与注册机制（v3 多租户）"""
import uuid


def test_super_admin_login(client):
    """super_admin 可以登录，角色正确"""
    r = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["user"]["role"] == "super_admin"
    assert data["user"]["tenant_id"] is None


def test_login_wrong_password(client):
    """错误密码登录失败"""
    r = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert r.status_code == 401


def test_register_with_code(client, admin_headers):
    """凭注册码注册新租户，首注册者成为 tenant_admin"""
    # 生成注册码
    r = client.post("/api/admin/registration-codes",
                    json={"plan": "trial", "duration_days": 30},
                    headers=admin_headers)
    code = r.json()["data"]["code"]

    # 注册
    username = f"newuser_{uuid.uuid4().hex[:8]}"
    r = client.post("/api/auth/register", json={
        "code": code, "company_name": "新工作室", "name": "新用户",
        "username": username, "phone": "13900000000", "password": "123456"
    })
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["user"]["role"] == "tenant_admin"
    assert data["user"]["tenant_id"] is not None


def test_register_invalid_code(client):
    """无效注册码注册失败"""
    r = client.post("/api/auth/register", json={
        "code": "INVALID", "company_name": "test", "name": "test",
        "username": "testuser", "phone": "13800000000", "password": "123456"
    })
    assert r.status_code == 400


def test_register_used_code(client, admin_headers):
    """已使用的注册码不能再次注册"""
    r = client.post("/api/admin/registration-codes",
                    json={"plan": "trial", "duration_days": 30},
                    headers=admin_headers)
    code = r.json()["data"]["code"]

    username1 = f"user1_{uuid.uuid4().hex[:8]}"
    client.post("/api/auth/register", json={
        "code": code, "company_name": "工作室1", "name": "用户1",
        "username": username1, "phone": "13800000001", "password": "123456"
    })

    username2 = f"user2_{uuid.uuid4().hex[:8]}"
    r = client.post("/api/auth/register", json={
        "code": code, "company_name": "工作室2", "name": "用户2",
        "username": username2, "phone": "13800000002", "password": "123456"
    })
    assert r.status_code == 400


def test_employee_register_via_invitation(client, tenant_setup):
    """租户管理员生成邀请链接，员工凭链接注册"""
    # 生成邀请
    r = client.post("/api/tenant/invitations", json={}, headers=tenant_setup["tenant_headers"])
    assert r.status_code == 200
    token = r.json()["data"]["token"]

    # 员工注册
    emp_username = f"emp_{uuid.uuid4().hex[:8]}"
    r = client.post("/api/auth/register-employee", json={
        "token": token, "name": "新员工",
        "username": emp_username, "phone": "13800000003", "password": "123456"
    })
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["user"]["role"] == "employee"
    assert data["user"]["tenant_id"] == tenant_setup["tenant_id"]


def test_employee_register_invalid_token(client):
    """无效邀请token注册失败"""
    r = client.post("/api/auth/register-employee", json={
        "token": "invalid", "name": "test", "username": "test", "password": "123456"
    })
    assert r.status_code == 400
