"""用户管理"""
import json
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import User, Tenant
from ..core.auth import (get_current_user, check_permission, require_tenant_user)

router = APIRouter(prefix="/api/users", tags=["用户管理"])


@router.get("")
def list_users(keyword: str = "", page: int = 1, page_size: int = 20,
               user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not (check_permission(user, "admin:config") or user.role == "tenant_admin"):
        raise HTTPException(403, "权限不足")
    q = db.query(User).filter(User.tenant_id == user.tenant_id) if user.tenant_id else db.query(User)
    if user.role != "super_admin":
        q = q.filter(User.tenant_id == user.tenant_id)
    if keyword:
        q = q.filter(User.name.contains(keyword) | User.username.contains(keyword))
    total = q.count()
    items = q.offset((page-1)*page_size).limit(page_size).all()
    return {"code": 200, "data": {"items": [{"id": u.id, "username": u.username, "name": u.name,
            "phone": u.phone, "role": u.role, "base_salary": float(u.base_salary),
            "permissions": u.perms_list, "data_scope": u.data_scope, "is_active": u.is_active}
            for u in items], "total": total, "page": page, "page_size": page_size}}


@router.post("")
def create_user(body: dict, user: User = Depends(require_tenant_user),
               db: Session = Depends(get_db)):
    if not (check_permission(user, "admin:config") or user.role == "tenant_admin"):
        raise HTTPException(403, "权限不足")
    if user.role != "super_admin" and user.tenant_id:
        tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
        emp_count = db.query(User).filter(User.tenant_id == user.tenant_id, User.is_active == True).count()
        if emp_count >= tenant.max_employees:
            raise HTTPException(403, f"已达员工上限（{tenant.max_employees}人），请升级套餐")
    if db.query(User).filter(User.username == body["username"]).first():
        raise HTTPException(400, "用户名已存在")
    u = User(tenant_id=user.tenant_id, username=body["username"],
             phone=body.get("phone"), password_hash=hash_password(body.get("password", "123456")),
             name=body["name"], role=body.get("role", "employee"),
             base_salary=Decimal(str(body.get("base_salary", 0))),
             permissions=json.dumps(body.get("permissions", ["payment:submit","salary:view"])),
             data_scope=body.get("data_scope", "SELF"))
    db.add(u)
    db.commit()
    return {"code": 200, "data": {"id": u.id}}


@router.put("/{uid}")
def update_user(uid: int, body: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not (check_permission(user, "admin:config") or user.role == "tenant_admin"):
        raise HTTPException(403, "权限不足")
    u = db.query(User).filter(User.id == uid).first()
    if not u:
        raise HTTPException(404, "用户不存在")
    if user.role != "super_admin" and u.tenant_id != user.tenant_id:
        raise HTTPException(403, "无权操作其他租户用户")
    if "name" in body: u.name = body["name"]
    if "phone" in body: u.phone = body["phone"]
    if "base_salary" in body: u.base_salary = Decimal(str(body["base_salary"]))
    if "permissions" in body: u.permissions = json.dumps(body["permissions"])
    if "data_scope" in body: u.data_scope = body["data_scope"]
    if "password" in body and body["password"]: u.password_hash = hash_password(body["password"])
    if "is_active" in body: u.is_active = body["is_active"]
    db.commit()
    return {"code": 200, "message": "更新成功"}


@router.put("/{uid}/deactivate")
def deactivate_user(uid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not (check_permission(user, "admin:config") or user.role == "tenant_admin"):
        raise HTTPException(403, "权限不足")
    u = db.query(User).filter(User.id == uid).first()
    if not u:
        raise HTTPException(404, "用户不存在")
    if user.role != "super_admin" and u.tenant_id != user.tenant_id:
        raise HTTPException(403, "无权操作其他租户用户")
    u.is_active = False
    db.commit()
    return {"code": 200, "message": "已设置为离职"}


# 局部导入避免循环依赖
from ..core.auth import hash_password
