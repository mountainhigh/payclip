"""认证接口：登录/获取当前用户/改密/注册租户/员工凭邀请注册"""
import json
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import User, Tenant, RegistrationCode, InvitationLink
from ..core.auth import (hash_password, verify_password, create_token, get_current_user)

router = APIRouter(prefix="/api/auth", tags=["认证"])


@router.post("/login")
def login(body: dict, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == body["username"]).first()
    if not user or not verify_password(body["password"], user.password_hash):
        raise HTTPException(401, "用户名或密码错误")
    if not user.is_active:
        raise HTTPException(403, "账号已禁用")
    if user.tenant_id is not None and user.role != "super_admin":
        tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
        if not tenant:
            raise HTTPException(403, "租户不存在")
        if tenant.status == "soft_deleted":
            raise HTTPException(403, "账号已归档，续费后可恢复使用")
        if tenant.status == "suspended":
            raise HTTPException(403, "租户已被暂停")
    token = create_token(user.id, user.perms_list, user.data_scope,
                         tenant_id=user.tenant_id, role=user.role)
    return {"code": 200, "message": "登录成功", "data": {"token": token, "user": {
        "id": user.id, "name": user.name, "username": user.username,
        "phone": user.phone, "role": user.role,
        "tenant_id": user.tenant_id, "permissions": user.perms_list,
        "data_scope": user.data_scope, "base_salary": float(user.base_salary),
        "is_admin": user.is_admin
    }}}


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"code": 200, "data": {"id": user.id, "name": user.name, "username": user.username,
            "phone": user.phone, "role": user.role, "tenant_id": user.tenant_id,
            "permissions": user.perms_list, "data_scope": user.data_scope,
            "base_salary": float(user.base_salary)}}


@router.put("/password")
def change_password(body: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(body["old_password"], user.password_hash):
        raise HTTPException(400, "原密码错误")
    user.password_hash = hash_password(body["new_password"])
    db.commit()
    return {"code": 200, "message": "密码修改成功"}


@router.post("/register")
def register(body: dict, db: Session = Depends(get_db)):
    """凭注册码注册新租户，首注册者自动成为租户管理员"""
    code = body.get("code", "").strip()
    phone = body.get("phone", "").strip()
    company_name = body.get("company_name", "").strip()
    username = body.get("username", "").strip()
    password = body.get("password", "")

    if not all([code, phone, company_name, username, password]):
        raise HTTPException(400, "请填写所有必填项")

    reg_code = db.query(RegistrationCode).filter(RegistrationCode.code == code).first()
    if not reg_code:
        raise HTTPException(400, "注册码无效")
    if reg_code.is_used:
        raise HTTPException(400, "该注册码已被使用")
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(400, "用户名已存在")

    # v3: 注册统一开 trial，付费由超管根据注册码 plan + 收款验证后手动升级（见 §2.4）
    trial_days = 30
    tenant = Tenant(name=company_name, plan="trial", status="active",
                    trial_expires=datetime.utcnow() + timedelta(days=trial_days),
                    plan_expires=datetime.utcnow() + timedelta(days=trial_days),
                    max_employees=0, contact_phone=phone)  # max_employees=0 表示不限人数（§2.1）
    db.add(tenant)
    db.flush()

    admin_user = User(tenant_id=tenant.id, username=username, phone=phone,
                      password_hash=hash_password(password), name=body.get("name", username),
                      role="tenant_admin", base_salary=0,
                      permissions=json.dumps(["tenant:admin","admin:config","payment:submit",
                      "payment:verify","salary:view","salary:manage","report:view"]),
                      data_scope="ALL", is_admin=False)
    db.add(admin_user)
    db.flush()

    reg_code.is_used = True
    reg_code.used_by_user_id = admin_user.id
    reg_code.used_by_tenant_id = tenant.id
    reg_code.used_at = datetime.utcnow()
    db.commit()

    token = create_token(admin_user.id, admin_user.perms_list, admin_user.data_scope,
                         tenant_id=admin_user.tenant_id, role=admin_user.role)
    return {"code": 200, "message": "注册成功", "data": {"token": token, "user": {
        "id": admin_user.id, "name": admin_user.name, "username": admin_user.username,
        "role": admin_user.role, "tenant_id": admin_user.tenant_id,
        "permissions": admin_user.perms_list, "data_scope": admin_user.data_scope
    }}}


@router.post("/register-employee")
def register_employee(body: dict, db: Session = Depends(get_db)):
    """员工凭邀请链接 token 自助注册"""
    token = body.get("token", "").strip()
    username = body.get("username", "").strip()
    password = body.get("password", "")
    name = body.get("name", "").strip()
    phone = body.get("phone", "").strip()

    if not all([token, username, password, name]):
        raise HTTPException(400, "请填写所有必填项")

    invite = db.query(InvitationLink).filter(InvitationLink.token == token).first()
    if not invite:
        raise HTTPException(400, "邀请链接无效")
    if invite.is_used:
        raise HTTPException(400, "该邀请链接已被使用")
    if invite.expires_at and invite.expires_at < datetime.utcnow():
        raise HTTPException(400, "邀请链接已过期")

    tenant = db.query(Tenant).filter(Tenant.id == invite.tenant_id).first()
    if not tenant or tenant.status not in ("active", "expired_readonly"):
        raise HTTPException(403, "租户状态异常，无法注册")

    # v3: 员工数不限，不再校验 max_employees（§2.1/§2.5）

    if db.query(User).filter(User.username == username).first():
        raise HTTPException(400, "用户名已存在")

    employee = User(tenant_id=tenant.id, username=username, phone=phone or None,
                    password_hash=hash_password(password), name=name,
                    role="employee", base_salary=0,
                    permissions=json.dumps(["payment:submit","salary:view"]),
                    data_scope="SELF", is_admin=False)
    db.add(employee)
    db.flush()

    invite.is_used = True
    invite.used_by_user_id = employee.id
    invite.used_at = datetime.utcnow()
    db.commit()

    jwt_token = create_token(employee.id, employee.perms_list, employee.data_scope,
                             tenant_id=employee.tenant_id, role=employee.role)
    return {"code": 200, "message": "注册成功", "data": {"token": jwt_token, "user": {
        "id": employee.id, "name": employee.name, "username": employee.username,
        "role": employee.role, "tenant_id": employee.tenant_id,
        "permissions": employee.perms_list, "data_scope": employee.data_scope
    }}}
