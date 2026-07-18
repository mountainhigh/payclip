import os
import json
import uuid

# 测试库使用远程腾讯云 MySQL 上的 payclip_test（与运行库同实例，独立 schema）
_DB_HOST = "sh-cynosdbmysql-grp-gwj80jyq.sql.tencentcdb.com"
_DB_PORT = 23674
_DB_USER = "payclip"
_DB_PASS = "payclip@2026!"
_DB_TEST = "payclip_test"

os.environ["DATABASE_URL"] = (
    f"mysql+pymysql://{_DB_USER}:{_DB_PASS.replace('@','%40').replace('!','%21')}"
    f"@{_DB_HOST}:{_DB_PORT}/{_DB_TEST}"
)

import pytest
import pymysql

# 1. 用 pymysql 确保测试库存在（不依赖 mysql 客户端 CLI）
_admin_conn = pymysql.connect(host=_DB_HOST, port=_DB_PORT, user=_DB_USER,
                              password=_DB_PASS, database="payclip", connect_timeout=15)
with _admin_conn.cursor() as _c:
    _c.execute(f"CREATE DATABASE IF NOT EXISTS {_DB_TEST} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
_admin_conn.commit()
_admin_conn.close()

# 2. 导入 models 让表注册到 Base.metadata，再删表重建
from app.database import Base, engine
from app import models  # noqa: F401

Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

# 3. 导入 FastAPI 应用
from app.main import app
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def client():
    """TestClient 会触发 startup 事件，自动写入 super_admin 种子。"""
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def admin_token(client):
    """super_admin token"""
    r = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200, r.text
    return r.json()["data"]["token"]


@pytest.fixture
def admin_headers(admin_token):
    return {"Authorization": "Bearer " + admin_token}


@pytest.fixture
def tenant_setup(client, admin_headers):
    """创建一个完整的租户测试环境：注册码 → 注册租户 → 创建员工 → 创建客户 → 创建业务"""
    # 生成注册码
    r = client.post("/api/admin/registration-codes",
                    json={"plan": "trial", "duration_days": 30, "remark": "pytest测试"},
                    headers=admin_headers)
    assert r.status_code == 200
    reg_code = r.json()["data"]["code"]

    # 注册租户
    username = f"tenant_{uuid.uuid4().hex[:8]}"
    r = client.post("/api/auth/register", json={
        "code": reg_code, "company_name": "测试工作室", "name": "租户管理员",
        "username": username, "phone": "13800001111", "password": "123456"
    })
    assert r.status_code == 200
    data = r.json()["data"]
    tenant_token = data["token"]
    tenant_headers = {"Authorization": f"Bearer {tenant_token}"}
    tenant_id = data["user"]["tenant_id"]

    # 创建员工
    r = client.post("/api/users", json={
        "username": f"emp_{uuid.uuid4().hex[:8]}", "name": "测试员工",
        "password": "123456", "base_salary": 3000,
        "permissions": ["payment:submit", "salary:view"], "data_scope": "SELF"
    }, headers=tenant_headers)
    assert r.status_code == 200
    emp_id = r.json()["data"]["id"]

    # 创建客户
    r = client.post("/api/customers", json={
        "name": "测试客户", "region_tags": ["广州"],
        "is_new_customer": True, "service_start_date": "2025-01-01"
    }, headers=tenant_headers)
    assert r.status_code == 200
    customer_id = r.json()["data"]["id"]

    # 创建长期业务
    r = client.post("/api/subscriptions", json={
        "company_id": customer_id, "service_type": "代理记账",
        "billing_period": "monthly", "monthly_fee": 2000,
        "service_owner_id": emp_id, "start_date": "2025-01-01"
    }, headers=tenant_headers)
    assert r.status_code == 200
    sub_id = r.json()["data"]["id"]

    return {
        "tenant_headers": tenant_headers,
        "tenant_id": tenant_id,
        "emp_id": emp_id,
        "customer_id": customer_id,
        "sub_id": sub_id,
        "username": username
    }


@pytest.fixture
def second_tenant_setup(client, admin_headers):
    """创建第二个租户用于隔离测试"""
    r = client.post("/api/admin/registration-codes",
                    json={"plan": "trial", "duration_days": 30, "remark": "第二个租户"},
                    headers=admin_headers)
    reg_code = r.json()["data"]["code"]

    username = f"tenant2_{uuid.uuid4().hex[:8]}"
    r = client.post("/api/auth/register", json={
        "code": reg_code, "company_name": "第二个工作室", "name": "租户2管理员",
        "username": username, "phone": "13800002222", "password": "123456"
    })
    assert r.status_code == 200
    return {
        "tenant_headers": {"Authorization": f"Bearer {r.json()['data']['token']}"},
        "tenant_id": r.json()["data"]["user"]["tenant_id"],
        "username": username
    }
