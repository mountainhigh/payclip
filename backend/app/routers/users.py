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
    # super_admin 切换租户后（user.tenant_id 已被 X-Tenant-Id 临时覆盖）：
    # 返回选中租户用户 + 自己；未切换时返回全部用户
    if user.role == "super_admin":
        if user.tenant_id is not None:
            q = db.query(User).filter((User.tenant_id == user.tenant_id) | (User.id == user.id))
        else:
            q = db.query(User)
    else:
        q = db.query(User).filter(User.tenant_id == user.tenant_id)
    if keyword:
        q = q.filter(User.name.contains(keyword) | User.username.contains(keyword))
    total = q.count()
    items = q.offset((page-1)*page_size).limit(page_size).all()
    return {"code": 200, "data": {"items": [{"id": u.id, "username": u.username, "name": u.name,
            "phone": u.phone, "role": u.role, "base_salary": float(u.base_salary),
            "permissions": u.perms_list, "data_scope": u.data_scope, "is_active": u.is_active,
            "tenant_id": u.tenant_id}
            for u in items], "total": total, "page": page, "page_size": page_size}}


@router.post("")
def create_user(body: dict, user: User = Depends(require_tenant_user),
               db: Session = Depends(get_db)):
    if not (check_permission(user, "admin:config") or user.role == "tenant_admin"):
        raise HTTPException(403, "权限不足")
    # v3: 员工数不限，不再校验 max_employees（§2.1/§2.5）
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
    # 跨租户校验：super_admin 未切换时可操作所有用户；切换后只能改选中租户用户或自己
    # tenant_admin 只能改本租户用户，且不能改 super_admin 账号
    if user.role == "super_admin":
        if user.tenant_id is not None and u.tenant_id != user.tenant_id and u.id != user.id:
            raise HTTPException(403, "无权操作其他租户用户")
    else:
        if u.tenant_id != user.tenant_id:
            raise HTTPException(403, "无权操作其他租户用户")
        # tenant_admin 不能修改 super_admin 账号
        if u.role == "super_admin":
            raise HTTPException(403, "无权修改平台管理员")
    # 角色变更校验
    if "role" in body and body["role"]:
        new_role = body["role"]
        if new_role not in ("super_admin", "tenant_admin", "employee"):
            raise HTTPException(400, "无效的角色")
        # tenant_admin 只能在 employee/tenant_admin 间切换
        if user.role == "tenant_admin" and new_role not in ("employee", "tenant_admin"):
            raise HTTPException(403, "租户管理员只能设置员工或租户管理员角色")
        u.role = new_role
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
