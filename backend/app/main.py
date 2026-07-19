"""薪资管理工具 — FastAPI 主入口

职责：
1. 创建 FastAPI 应用 + CORS 中间件 + 静态文件挂载
2. 启动钩子：建表 + 创建 super_admin
3. 挂载 14 个业务路由模块（routers/）
4. 健康检查 /api/health

所有业务逻辑在各 routers/*.py 中实现，本文件只做装配。
"""
import json
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .database import engine, get_db, Base
from .models import User
from .config import UPLOAD_DIR
from .core.auth import hash_password
from .routers import (auth_router, admin_router, tenant_router, users_router,
                      customers_router, suppliers_router, subscriptions_router,
                      onetime_router, bills_router, payments_router, prepayments_router,
                      ledger_router, salaries_router, reports_router, system_router)

app = FastAPI(title="薪资管理工具", version="2.0.0")

# ==================== 中间件 ====================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

# ==================== 静态资源 ====================
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


# ==================== 启动钩子：建表 + 创建超级管理员 ====================
@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    db = next(get_db())
    if not db.query(User).filter(User.role == "super_admin").first():
        admin = User(tenant_id=None, username="admin", phone=None,
                     password_hash=hash_password("admin123"), name="平台管理员",
                     role="super_admin", base_salary=0,
                     permissions=json.dumps(["admin:config", "payment:submit", "payment:verify",
                                             "salary:view", "salary:manage", "report:view",
                                             "tenant:admin"]),
                     data_scope="ALL", is_admin=True)
        db.add(admin)
        db.commit()
    # 轻量级迁移：为 companies 表补充 business_owner_id / contact_name 字段（create_all 不会修改已有表）
    _ensure_column(engine, "companies", "business_owner_id", "BIGINT NULL")
    _ensure_column(engine, "companies", "contact_name", "VARCHAR(50) NULL")
    # 为已存在的租户初始化默认收款渠道（仅当该租户无任何渠道时）
    _init_default_payment_channels(db)


def _init_default_payment_channels(db):
    """为每个已有租户初始化默认收款渠道（仅当该租户无任何渠道时）"""
    from .models import Tenant, PaymentChannel
    tenants = db.query(Tenant).all()
    DEFAULTS = [
        {"name": "银行转账", "code": "bank", "payee_name": "", "account_number": "", "account_type": "对公", "sort_order": 1},
        {"name": "支付宝", "code": "alipay", "payee_name": "", "account_number": "", "account_type": "个人", "sort_order": 2},
        {"name": "微信", "code": "wechat", "payee_name": "", "account_number": "", "account_type": "个人", "sort_order": 3},
        {"name": "现金", "code": "cash", "payee_name": "", "account_number": "", "account_type": "—", "sort_order": 4},
    ]
    for t in tenants:
        existing = db.query(PaymentChannel).filter(PaymentChannel.tenant_id == t.id).count()
        if existing > 0:
            continue
        for d in DEFAULTS:
            db.add(PaymentChannel(tenant_id=t.id, name=d["name"], code=d["code"],
                                  payee_name=d["payee_name"], account_number=d["account_number"],
                                  account_type=d["account_type"], is_active=True,
                                  sort_order=d["sort_order"]))
    db.commit()


def _ensure_column(eng, table_name, column_name, column_def):
    """幂等添加列：若列不存在则 ALTER TABLE 添加。仅支持 MySQL/PostgreSQL 方言。"""
    from sqlalchemy import text, inspect
    insp = inspect(eng)
    if not insp.has_table(table_name):
        return
    existing_cols = [c["name"] for c in insp.get_columns(table_name)]
    if column_name in existing_cols:
        return
    with eng.connect() as conn:
        conn.execute(text(f"ALTER TABLE `{table_name}` ADD COLUMN `{column_name}` {column_def}"))
        conn.commit()


# ==================== 挂载业务路由 ====================
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(tenant_router)
app.include_router(users_router)
app.include_router(customers_router)
app.include_router(suppliers_router)
app.include_router(subscriptions_router)
app.include_router(onetime_router)
app.include_router(bills_router)
app.include_router(payments_router)
app.include_router(prepayments_router)
app.include_router(ledger_router)
app.include_router(salaries_router)
app.include_router(reports_router)
app.include_router(system_router)


# ==================== 健康检查 ====================
@app.get("/api/health", tags=["系统"])
def health():
    return {"status": "ok", "version": "2.0.0", "multi_tenant": True}
