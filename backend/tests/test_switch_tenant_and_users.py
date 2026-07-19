"""super_admin 切换租户 + 用户管理增强测试（需求3 + 需求4）

验证：
1. super_admin 能拉到租户列表
2. super_admin 切换租户后 GET /api/users 只返回选中租户用户 + 自己
3. super_admin 切换租户后能读写该租户数据（创建客户）
4. super_admin 未切换租户时 GET /api/users 返回全部用户
5. tenant_admin 可把 employee 改成 tenant_admin
6. tenant_admin 不能把员工设为 super_admin
7. super_admin 可设任意角色
8. super_admin 不能改其他租户用户（切换租户 A 后不能改租户 B 的用户）
"""
import pytest
from app.database import SessionLocal
from app.models import User


def test_super_admin_list_tenants(client, admin_headers):
    """super_admin 能拉到租户列表"""
    r = client.get("/api/admin/tenants", headers=admin_headers)
    assert r.status_code == 200, r.text
    items = r.json()["data"]["items"]
    assert isinstance(items, list)


def test_super_admin_list_users_without_switch(client, admin_headers, tenant_setup, second_tenant_setup):
    """super_admin 未切换租户时返回全部用户"""
    r = client.get("/api/users", params={"page": 1, "page_size": 500}, headers=admin_headers)
    assert r.status_code == 200, r.text
    items = r.json()["data"]["items"]
    # 至少包含 super_admin 自己 + 两个租户的管理员
    usernames = [u["username"] for u in items]
    assert "admin" in usernames  # super_admin 自己
    assert tenant_setup["username"] in usernames
    assert second_tenant_setup["username"] in usernames


def test_super_admin_switch_tenant_sees_only_selected(client, admin_headers, tenant_setup, second_tenant_setup):
    """切换租户后只返回选中租户用户 + 自己"""
    target_tid = tenant_setup["tenant_id"]
    other_tid = second_tenant_setup["tenant_id"]

    # 切换到 tenant_setup 租户
    r = client.get("/api/users", headers={**admin_headers, "X-Tenant-Id": str(target_tid)})
    assert r.status_code == 200, r.text
    items = r.json()["data"]["items"]
    usernames = [u["username"] for u in items]

    # 应包含 super_admin 自己 + tenant_setup 的管理员
    assert "admin" in usernames
    assert tenant_setup["username"] in usernames
    # 不应包含 second_tenant_setup 的管理员
    assert second_tenant_setup["username"] not in usernames

    # 切换到 second_tenant_setup 租户
    r = client.get("/api/users", headers={**admin_headers, "X-Tenant-Id": str(other_tid)})
    assert r.status_code == 200, r.text
    items = r.json()["data"]["items"]
    usernames = [u["username"] for u in items]
    assert "admin" in usernames
    assert second_tenant_setup["username"] in usernames
    assert tenant_setup["username"] not in usernames


def test_super_admin_switch_tenant_crud(client, admin_headers, tenant_setup, second_tenant_setup):
    """切换租户后能读写该租户数据（创建客户）"""
    target_tid = tenant_setup["tenant_id"]
    headers = {**admin_headers, "X-Tenant-Id": str(target_tid)}

    # 在选中租户下创建客户
    r = client.post("/api/customers", json={
        "name": "切换租户后创建的客户", "is_new_customer": False
    }, headers=headers)
    assert r.status_code == 200, r.text
    cust_id = r.json()["data"]["id"]

    # 列表应能看到该客户
    r = client.get("/api/customers", headers=headers)
    assert r.status_code == 200, r.text
    cust_names = [c["name"] for c in r.json()["data"]["items"]]
    assert "切换租户后创建的客户" in cust_names

    # 切换到另一个租户，应看不到该客户
    headers2 = {**admin_headers, "X-Tenant-Id": str(second_tenant_setup["tenant_id"])}
    r = client.get("/api/customers", headers=headers2)
    assert r.status_code == 200, r.text
    cust_names2 = [c["name"] for c in r.json()["data"]["items"]]
    assert "切换租户后创建的客户" not in cust_names2


def test_super_admin_switch_invalid_tenant(client, admin_headers):
    """切换到不存在的租户返回 404"""
    r = client.get("/api/users", headers={**admin_headers, "X-Tenant-Id": "99999999"})
    assert r.status_code == 404, r.text


def test_tenant_admin_update_user_role_to_tenant_admin(client, tenant_setup):
    """tenant_admin 可把 employee 改成 tenant_admin"""
    tenant_headers = tenant_setup["tenant_headers"]
    emp_id = tenant_setup["emp_id"]

    # 先创建一个员工（tenant_setup 已创建，emp_id 即为员工）
    r = client.put(f"/api/users/{emp_id}", json={"role": "tenant_admin"}, headers=tenant_headers)
    assert r.status_code == 200, r.text

    # 校验已更新
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.id == emp_id).first()
        assert u.role == "tenant_admin"
    finally:
        db.close()


def test_tenant_admin_cannot_set_super_admin(client, tenant_setup):
    """tenant_admin 不能把员工设为 super_admin"""
    tenant_headers = tenant_setup["tenant_headers"]
    emp_id = tenant_setup["emp_id"]

    r = client.put(f"/api/users/{emp_id}", json={"role": "super_admin"}, headers=tenant_headers)
    assert r.status_code == 403, r.text
    assert "租户管理员" in r.json()["detail"] or "无权" in r.json()["detail"]


def test_super_admin_update_role_to_super_admin(client, admin_headers, tenant_setup):
    """super_admin 可把员工设为 super_admin"""
    emp_id = tenant_setup["emp_id"]
    # 用 super_admin 直接更新（不切换租户）
    r = client.put(f"/api/users/{emp_id}", json={"role": "super_admin"}, headers=admin_headers)
    assert r.status_code == 200, r.text

    db = SessionLocal()
    try:
        u = db.query(User).filter(User.id == emp_id).first()
        assert u.role == "super_admin"
    finally:
        db.close()


def test_super_admin_switch_tenant_cannot_modify_other_tenant_user(client, admin_headers, tenant_setup, second_tenant_setup):
    """super_admin 切换到租户 A 后不能改租户 B 的用户"""
    emp_id = tenant_setup["emp_id"]
    other_tid = second_tenant_setup["tenant_id"]

    # 切换到 second_tenant_setup，尝试改 tenant_setup 的员工
    headers = {**admin_headers, "X-Tenant-Id": str(other_tid)}
    r = client.put(f"/api/users/{emp_id}", json={"name": "被改了"}, headers=headers)
    assert r.status_code == 403, r.text


def test_invalid_role_rejected(client, admin_headers, tenant_setup):
    """无效角色被拒绝"""
    emp_id = tenant_setup["emp_id"]
    r = client.put(f"/api/users/{emp_id}", json={"role": "invalid_role"}, headers=admin_headers)
    assert r.status_code == 400, r.text


def test_user_list_returns_tenant_id_field(client, admin_headers, tenant_setup):
    """list_users 返回字段包含 tenant_id"""
    headers = {**admin_headers, "X-Tenant-Id": str(tenant_setup["tenant_id"])}
    r = client.get("/api/users", headers=headers)
    assert r.status_code == 200, r.text
    items = r.json()["data"]["items"]
    assert len(items) > 0
    # 每条都应有 tenant_id 字段
    for u in items:
        assert "tenant_id" in u
