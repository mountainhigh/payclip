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
                      onetime_router, bills_router, payments_router, ledger_router,
                      salaries_router, reports_router, system_router)

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
app.include_router(ledger_router)
app.include_router(salaries_router)
app.include_router(reports_router)
app.include_router(system_router)


# ==================== 健康检查 ====================
@app.get("/api/health", tags=["系统"])
def health():
    return {"status": "ok", "version": "2.0.0", "multi_tenant": True}
