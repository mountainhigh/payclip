import json, os, uuid, secrets
from datetime import datetime, date, timedelta
from decimal import Decimal
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from .database import engine, get_db, Base
from .models import *
from .config import JWT_SECRET, UPLOAD_DIR, ALLOWED_IMAGE_TYPES, MAX_UPLOAD_SIZE
from .core.auth import (hash_password, verify_password, create_token, get_current_user,
                         check_permission, require_super_admin, require_tenant_admin,
                         require_write_access, get_tenant_id)

app = FastAPI(title="薪资管理工具", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

os.makedirs(UPLOAD_DIR, exist_ok=True)

# ==================== 启动时建表 ====================
@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    db = next(get_db())
    # 创建超级管理员（不关联租户）
    if not db.query(User).filter(User.role == "super_admin").first():
        admin = User(tenant_id=None, username="admin", phone=None,
                     password_hash=hash_password("admin123"), name="平台管理员",
                     role="super_admin", base_salary=0,
                     permissions=json.dumps(["admin:config","payment:submit","payment:verify",
                     "salary:view","salary:manage","report:view","tenant:admin"]),
                     data_scope="ALL", is_admin=True)
        db.add(admin)
        db.commit()


# ==================== 认证接口 ====================
@app.post("/api/auth/login")
def login(body: dict, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == body["username"]).first()
    if not user or not verify_password(body["password"], user.password_hash):
        raise HTTPException(401, "用户名或密码错误")
    if not user.is_active:
        raise HTTPException(403, "账号已禁用")
    # 检查租户状态
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


@app.get("/api/auth/me")
def me(user: User = Depends(get_current_user)):
    return {"code": 200, "data": {"id": user.id, "name": user.name, "username": user.username,
            "phone": user.phone, "role": user.role, "tenant_id": user.tenant_id,
            "permissions": user.perms_list, "data_scope": user.data_scope,
            "base_salary": float(user.base_salary)}}


@app.put("/api/auth/password")
def change_password(body: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(body["old_password"], user.password_hash):
        raise HTTPException(400, "原密码错误")
    user.password_hash = hash_password(body["new_password"])
    db.commit()
    return {"code": 200, "message": "密码修改成功"}


# ==================== 租户注册接口（v3 新增） ====================
@app.post("/api/auth/register")
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

    # 创建租户
    trial_days = reg_code.duration_days or 30
    tenant = Tenant(name=company_name, plan=reg_code.plan, status="active",
                    trial_expires=datetime.utcnow() + timedelta(days=trial_days),
                    plan_expires=datetime.utcnow() + timedelta(days=trial_days),
                    max_employees=3, contact_phone=phone)
    db.add(tenant)
    db.flush()

    # 创建租户管理员
    admin_user = User(tenant_id=tenant.id, username=username, phone=phone,
                      password_hash=hash_password(password), name=body.get("name", username),
                      role="tenant_admin", base_salary=0,
                      permissions=json.dumps(["tenant:admin","admin:config","payment:submit",
                      "payment:verify","salary:view","salary:manage","report:view"]),
                      data_scope="ALL", is_admin=False)
    db.add(admin_user)
    db.flush()

    # 标记注册码已使用
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


@app.post("/api/auth/register-employee")
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

    # 检查员工数上限
    emp_count = db.query(User).filter(User.tenant_id == tenant.id, User.is_active == True).count()
    if emp_count >= tenant.max_employees:
        raise HTTPException(403, f"已达员工上限（{tenant.max_employees}人），请联系管理员升级套餐")

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


# ==================== 平台管理员接口（v3 新增） ====================
@app.get("/api/admin/tenants")
def list_tenants(page: int = 1, page_size: int = 20,
                 user: User = Depends(require_super_admin), db: Session = Depends(get_db)):
    q = db.query(Tenant)
    total = q.count()
    items = q.order_by(Tenant.id.desc()).offset((page-1)*page_size).limit(page_size).all()
    return {"code": 200, "data": {"items": [_serialize_tenant(t, db) for t in items],
            "total": total, "page": page, "page_size": page_size}}


@app.post("/api/admin/registration-codes")
def create_registration_code(body: dict,
                             user: User = Depends(require_super_admin), db: Session = Depends(get_db)):
    plan = body.get("plan", "trial")
    duration = body.get("duration_days", 30)
    remark = body.get("remark", "")
    code = secrets.token_hex(8).upper()
    reg = RegistrationCode(code=code, plan=plan, duration_days=duration,
                           created_by=user.id, remark=remark)
    db.add(reg)
    db.commit()
    return {"code": 200, "data": {"id": reg.id, "code": code, "plan": plan, "duration_days": duration}}


@app.get("/api/admin/registration-codes")
def list_registration_codes(page: int = 1, page_size: int = 20,
                             user: User = Depends(require_super_admin), db: Session = Depends(get_db)):
    q = db.query(RegistrationCode)
    total = q.count()
    items = q.order_by(RegistrationCode.id.desc()).offset((page-1)*page_size).limit(page_size).all()
    return {"code": 200, "data": {"items": [{"id": r.id, "code": r.code, "plan": r.plan,
            "duration_days": r.duration_days, "is_used": r.is_used,
            "used_at": str(r.used_at) if r.used_at else None, "remark": r.remark,
            "created_at": str(r.created_at)} for r in items], "total": total, "page": page, "page_size": page_size}}


@app.put("/api/admin/tenants/{tid}/status")
def update_tenant_status(tid: int, body: dict,
                         user: User = Depends(require_super_admin), db: Session = Depends(get_db)):
    tenant = db.query(Tenant).filter(Tenant.id == tid).first()
    if not tenant:
        raise HTTPException(404, "租户不存在")
    new_status = body.get("status")
    if new_status not in ("pending_payment", "active", "expired_readonly", "soft_deleted", "suspended"):
        raise HTTPException(400, "无效的租户状态")
    tenant.status = new_status
    if new_status == "active" and body.get("plan"):
        tenant.plan = body["plan"]
        days_map = {"monthly": 30, "yearly": 365, "trial": 30}
        days = days_map.get(body["plan"], 30)
        tenant.plan_expires = datetime.utcnow() + timedelta(days=days)
        tenant.trial_expires = tenant.plan_expires
        tenant.max_employees = body.get("max_employees", 20 if body["plan"] != "trial" else 3)
    db.commit()
    return {"code": 200, "message": "租户状态已更新", "data": _serialize_tenant(tenant, db)}


@app.post("/api/admin/tenants/{tid}/renew")
def renew_tenant(tid: int, body: dict,
                 user: User = Depends(require_super_admin), db: Session = Depends(get_db)):
    tenant = db.query(Tenant).filter(Tenant.id == tid).first()
    if not tenant:
        raise HTTPException(404, "租户不存在")
    plan = body.get("plan", "monthly")
    days_map = {"monthly": 30, "yearly": 365, "trial": 30}
    days = days_map.get(plan, 30)
    # 从当前到期时间或现在开始续期
    base = tenant.plan_expires if tenant.plan_expires and tenant.plan_expires > datetime.utcnow() else datetime.utcnow()
    tenant.plan = plan
    tenant.status = "active"
    tenant.plan_expires = base + timedelta(days=days)
    tenant.trial_expires = tenant.plan_expires
    tenant.max_employees = body.get("max_employees", 20 if plan != "trial" else 3)
    db.commit()
    return {"code": 200, "message": "续费成功", "data": _serialize_tenant(tenant, db)}


def _serialize_tenant(t, db):
    emp_count = db.query(User).filter(User.tenant_id == t.id, User.is_active == True).count()
    return {"id": t.id, "name": t.name, "plan": t.plan, "status": t.status,
            "trial_expires": str(t.trial_expires) if t.trial_expires else None,
            "plan_expires": str(t.plan_expires) if t.plan_expires else None,
            "max_employees": t.max_employees, "employee_count": emp_count,
            "contact_phone": t.contact_phone, "remark": t.remark,
            "created_at": str(t.created_at)}


# ==================== 租户管理员接口（v3 新增） ====================
@app.post("/api/tenant/invitations")
def create_invitation(body: dict,
                      user: User = Depends(require_tenant_admin), db: Session = Depends(get_db)):
    tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
    emp_count = db.query(User).filter(User.tenant_id == user.tenant_id, User.is_active == True).count()
    if emp_count >= tenant.max_employees:
        raise HTTPException(403, f"已达员工上限（{tenant.max_employees}人），请升级套餐")
    token = secrets.token_hex(16)
    invite = InvitationLink(tenant_id=user.tenant_id, token=token, created_by=user.id,
                             expires_at=datetime.utcnow() + timedelta(days=7) if body.get("expire_days") else None)
    db.add(invite)
    db.commit()
    return {"code": 200, "data": {"id": invite.id, "token": token,
            "url": f"/register-employee?token={token}"}}


@app.get("/api/tenant/invitations")
def list_invitations(user: User = Depends(require_tenant_admin), db: Session = Depends(get_db)):
    items = db.query(InvitationLink).filter(InvitationLink.tenant_id == user.tenant_id)\
               .order_by(InvitationLink.id.desc()).all()
    return {"code": 200, "data": [{"id": i.id, "token": i.token, "is_used": i.is_used,
            "used_at": str(i.used_at) if i.used_at else None,
            "expires_at": str(i.expires_at) if i.expires_at else None,
            "created_at": str(i.created_at)} for i in items]}


@app.get("/api/tenant/info")
def get_tenant_info(user: User = Depends(require_tenant_admin), db: Session = Depends(get_db)):
    tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
    if not tenant:
        raise HTTPException(404, "租户不存在")
    return {"code": 200, "data": _serialize_tenant(tenant, db)}


# ==================== 用户管理 ====================
@app.get("/api/users")
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


@app.post("/api/users")
def create_user(body: dict, user: User = Depends(require_write_access),
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


@app.put("/api/users/{uid}")
def update_user(uid: int, body: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not (check_permission(user, "admin:config") or user.role == "tenant_admin"):
        raise HTTPException(403, "权限不足")
    u = db.query(User).filter(User.id == uid).first()
    if not u:
        raise HTTPException(404, "用户不存在")
    # 租户管理员只能管理本租户用户
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


@app.put("/api/users/{uid}/deactivate")
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


# ==================== 客户管理 ====================
@app.get("/api/customers")
def list_customers(keyword: str = "", page: int = 1, page_size: int = 20,
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(Company).filter(Company.is_archived == False)
    if user.tenant_id:
        q = q.filter(Company.tenant_id == user.tenant_id)
    if keyword:
        q = q.filter(Company.name.contains(keyword))
    total = q.count()
    items = q.order_by(Company.id.desc()).offset((page-1)*page_size).limit(page_size).all()
    return {"code": 200, "data": {"items": [_serialize_company(c) for c in items], "total": total, "page": page, "page_size": page_size}}


@app.get("/api/customers/{cid}")
def get_customer(cid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(Company).filter(Company.id == cid, Company.is_archived == False)
    if user.tenant_id:
        q = q.filter(Company.tenant_id == user.tenant_id)
    c = q.first()
    if not c:
        raise HTTPException(404, "客户不存在")
    return {"code": 200, "data": _serialize_company(c)}


@app.post("/api/customers")
def create_customer(body: dict, user: User = Depends(require_write_access), db: Session = Depends(get_db)):
    if not (check_permission(user, "admin:config") or user.role == "tenant_admin"):
        raise HTTPException(403, "权限不足")
    c = Company(tenant_id=user.tenant_id, name=body["name"],
                region_tags=json.dumps(body.get("region_tags", [])),
                is_new_customer=body.get("is_new_customer", False),
                service_start_date=parse_date(body.get("service_start_date")),
                status=body.get("status", "active"),
                introducer_type=body.get("introducer_type", "external"),
                introducer_user_id=body.get("introducer_user_id"),
                introducer_name=body.get("introducer_name"),
                sales_person_id=body.get("sales_person_id"),
                contact_phone=body.get("contact_phone"),
                contact_email=body.get("contact_email"),
                remark=body.get("remark"))
    db.add(c)
    db.commit()
    return {"code": 200, "data": {"id": c.id}}


@app.put("/api/customers/{cid}")
def update_customer(cid: int, body: dict, user: User = Depends(require_write_access), db: Session = Depends(get_db)):
    if not (check_permission(user, "admin:config") or user.role == "tenant_admin"):
        raise HTTPException(403, "权限不足")
    q = db.query(Company).filter(Company.id == cid, Company.is_archived == False)
    if user.tenant_id:
        q = q.filter(Company.tenant_id == user.tenant_id)
    c = q.first()
    if not c:
        raise HTTPException(404, "客户不存在")
    for f in ["name","status","introducer_type","introducer_name","contact_phone","contact_email","remark"]:
        if f in body: setattr(c, f, body[f])
    if "region_tags" in body: c.region_tags = json.dumps(body["region_tags"])
    if "service_start_date" in body: c.service_start_date = parse_date(body["service_start_date"])
    if "is_new_customer" in body: c.is_new_customer = body["is_new_customer"]
    if "sales_person_id" in body: c.sales_person_id = body["sales_person_id"]
    if "introducer_user_id" in body: c.introducer_user_id = body["introducer_user_id"]
    db.commit()
    return {"code": 200, "message": "更新成功"}


@app.delete("/api/customers/{cid}")
def archive_customer(cid: int, user: User = Depends(require_write_access), db: Session = Depends(get_db)):
    if not (check_permission(user, "admin:config") or user.role == "tenant_admin"):
        raise HTTPException(403, "权限不足")
    q = db.query(Company).filter(Company.id == cid, Company.is_archived == False)
    if user.tenant_id:
        q = q.filter(Company.tenant_id == user.tenant_id)
    c = q.first()
    if not c:
        raise HTTPException(404, "客户不存在")
    unpaid = db.query(Bill).filter(Bill.company_id == cid,
                     Bill.payment_status.in_(["unpaid","partial","overdue"])).first()
    if unpaid:
        raise HTTPException(422, "该客户有未结清账单，禁止删除")
    c.is_archived = True
    db.commit()
    return {"code": 200, "message": "已归档"}


def _serialize_company(c):
    return {"id": c.id, "name": c.name,
            "region_tags": json.loads(c.region_tags) if isinstance(c.region_tags, str) else c.region_tags,
            "is_new_customer": c.is_new_customer,
            "service_start_date": str(c.service_start_date) if c.service_start_date else None,
            "status": c.status, "introducer_type": c.introducer_type,
            "introducer_user_id": c.introducer_user_id, "introducer_name": c.introducer_name,
            "sales_person_id": c.sales_person_id, "contact_phone": c.contact_phone,
            "contact_email": c.contact_email, "remark": c.remark}


# ==================== 供应商管理 ====================
@app.get("/api/suppliers")
def list_suppliers(keyword: str = "", page: int = 1, page_size: int = 20,
                  user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(Supplier).filter(Supplier.is_archived == False)
    if user.tenant_id:
        q = q.filter(Supplier.tenant_id == user.tenant_id)
    if keyword:
        q = q.filter(Supplier.name.contains(keyword))
    total = q.count()
    items = q.offset((page-1)*page_size).limit(page_size).all()
    return {"code": 200, "data": {"items": [{"id": s.id, "name": s.name, "type": s.type,
            "contact": s.contact, "remark": s.remark} for s in items],
            "total": total, "page": page, "page_size": page_size}}


@app.post("/api/suppliers")
def create_supplier(body: dict, user: User = Depends(require_write_access), db: Session = Depends(get_db)):
    if not (check_permission(user, "admin:config") or user.role == "tenant_admin"):
        raise HTTPException(403, "权限不足")
    s = Supplier(tenant_id=user.tenant_id, name=body["name"],
                 type=body.get("type","其他"), contact=body.get("contact"), remark=body.get("remark"))
    db.add(s)
    db.commit()
    return {"code": 200, "data": {"id": s.id}}


@app.put("/api/suppliers/{sid}")
def update_supplier(sid: int, body: dict, user: User = Depends(require_write_access), db: Session = Depends(get_db)):
    if not (check_permission(user, "admin:config") or user.role == "tenant_admin"):
        raise HTTPException(403, "权限不足")
    q = db.query(Supplier).filter(Supplier.id == sid, Supplier.is_archived == False)
    if user.tenant_id:
        q = q.filter(Supplier.tenant_id == user.tenant_id)
    s = q.first()
    if not s:
        raise HTTPException(404, "供应商不存在")
    for f in ["name","type","contact","remark"]:
        if f in body: setattr(s, f, body[f])
    db.commit()
    return {"code": 200, "message": "更新成功"}


@app.delete("/api/suppliers/{sid}")
def archive_supplier(sid: int, user: User = Depends(require_write_access), db: Session = Depends(get_db)):
    if not (check_permission(user, "admin:config") or user.role == "tenant_admin"):
        raise HTTPException(403, "权限不足")
    q = db.query(Supplier).filter(Supplier.id == sid)
    if user.tenant_id:
        q = q.filter(Supplier.tenant_id == user.tenant_id)
    s = q.first()
    if s:
        s.is_archived = True
        db.commit()
    return {"code": 200, "message": "已归档"}


# ==================== 长期业务 ====================
@app.get("/api/subscriptions")
def list_subscriptions(company_id: int = None, page: int = 1, page_size: int = 20,
                       user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(Subscription).filter(Subscription.is_archived == False)
    if user.tenant_id:
        q = q.filter(Subscription.tenant_id == user.tenant_id)
    if company_id:
        q = q.filter(Subscription.company_id == company_id)
    total = q.count()
    items = q.offset((page-1)*page_size).limit(page_size).all()
    return {"code": 200, "data": {"items": [_serialize_sub(s, db) for s in items], "total": total, "page": page, "page_size": page_size}}


@app.post("/api/subscriptions")
def create_subscription(body: dict, user: User = Depends(require_write_access), db: Session = Depends(get_db)):
    if not (check_permission(user, "admin:config") or user.role == "tenant_admin"):
        raise HTTPException(403, "权限不足")
    s = Subscription(tenant_id=user.tenant_id, company_id=body["company_id"],
                     service_type=body["service_type"], billing_period=body["billing_period"],
                     monthly_fee=Decimal(str(body["monthly_fee"])),
                     is_cost_type=body.get("is_cost_type", False),
                     monthly_cost=Decimal(str(body.get("monthly_cost", 0))),
                     supplier_id=body.get("supplier_id"),
                     service_owner_id=body["service_owner_id"],
                     sales_owner_id=body.get("sales_owner_id"),
                     start_date=parse_date(body.get("start_date")))
    db.add(s)
    db.flush()
    fh = FeeHistory(tenant_id=user.tenant_id, subscription_id=s.id,
                    old_fee=Decimal("0"), new_fee=Decimal(str(body["monthly_fee"])),
                    effective_date=parse_date(body.get("start_date")), changed_by=user.id)
    db.add(fh)
    db.commit()
    return {"code": 200, "data": {"id": s.id}}


@app.put("/api/subscriptions/{sid}")
def update_subscription(sid: int, body: dict, user: User = Depends(require_write_access), db: Session = Depends(get_db)):
    if not (check_permission(user, "admin:config") or user.role == "tenant_admin"):
        raise HTTPException(403, "权限不足")
    q = db.query(Subscription).filter(Subscription.id == sid, Subscription.is_archived == False)
    if user.tenant_id:
        q = q.filter(Subscription.tenant_id == user.tenant_id)
    s = q.first()
    if not s:
        raise HTTPException(404, "业务不存在")
    for f in ["service_type","billing_period","is_cost_type"]:
        if f in body: setattr(s, f, body[f])
    for f_dec in ["monthly_fee","monthly_cost"]:
        if f_dec in body: setattr(s, f_dec, Decimal(str(body[f_dec])))
    for f_int in ["company_id","supplier_id","service_owner_id","sales_owner_id"]:
        if f_int in body: setattr(s, f_int, body[f_int])
    if "start_date" in body: s.start_date = parse_date(body["start_date"])
    db.commit()
    return {"code": 200, "message": "更新成功"}


@app.put("/api/subscriptions/{sid}/toggle")
def toggle_subscription(sid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(Subscription).filter(Subscription.id == sid)
    if user.tenant_id:
        q = q.filter(Subscription.tenant_id == user.tenant_id)
    s = q.first()
    if not s:
        raise HTTPException(404, "业务不存在")
    s.is_active = not s.is_active
    db.commit()
    return {"code": 200, "data": {"is_active": s.is_active}}


@app.post("/api/subscriptions/{sid}/fee-change")
def change_fee(sid: int, body: dict, user: User = Depends(require_write_access), db: Session = Depends(get_db)):
    if not (check_permission(user, "admin:config") or user.role == "tenant_admin"):
        raise HTTPException(403, "权限不足")
    q = db.query(Subscription).filter(Subscription.id == sid)
    if user.tenant_id:
        q = q.filter(Subscription.tenant_id == user.tenant_id)
    s = q.first()
    if not s:
        raise HTTPException(404, "业务不存在")
    old_fee = s.monthly_fee
    new_fee = Decimal(str(body["new_fee"]))
    eff_date = parse_date(body["effective_date"])
    s.monthly_fee = new_fee
    fh = FeeHistory(tenant_id=user.tenant_id, subscription_id=sid,
                    old_fee=old_fee, new_fee=new_fee, effective_date=eff_date, changed_by=user.id)
    db.add(fh)
    db.commit()
    return {"code": 200, "message": "月费已变更"}


@app.get("/api/subscriptions/{sid}/fee-history")
def get_fee_history(sid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(FeeHistory).filter(FeeHistory.subscription_id == sid)
    if user.tenant_id:
        q = q.filter(FeeHistory.tenant_id == user.tenant_id)
    items = q.order_by(FeeHistory.effective_date.desc()).all()
    return {"code": 200, "data": [{"id": f.id, "old_fee": float(f.old_fee), "new_fee": float(f.new_fee),
            "effective_date": str(f.effective_date)} for f in items]}


def _serialize_sub(s, db):
    owner = db.query(User).filter(User.id == s.service_owner_id).first()
    sales = db.query(User).filter(User.id == s.sales_owner_id).first() if s.sales_owner_id else None
    return {"id": s.id, "company_id": s.company_id, "service_type": s.service_type,
            "billing_period": s.billing_period, "monthly_fee": float(s.monthly_fee),
            "is_cost_type": s.is_cost_type, "monthly_cost": float(s.monthly_cost),
            "supplier_id": s.supplier_id, "service_owner_id": s.service_owner_id,
            "service_owner_name": owner.name if owner else "",
            "sales_owner_id": s.sales_owner_id,
            "sales_owner_name": sales.name if sales else "",
            "start_date": str(s.start_date) if s.start_date else None,
            "is_active": s.is_active}


# ==================== 一次性业务 ====================
@app.get("/api/onetime-projects")
def list_onetime(company_id: int = None, page: int = 1, page_size: int = 20,
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(OneTimeProject).filter(OneTimeProject.is_archived == False)
    if user.tenant_id:
        q = q.filter(OneTimeProject.tenant_id == user.tenant_id)
    if company_id:
        q = q.filter(OneTimeProject.company_id == company_id)
    total = q.count()
    items = q.offset((page-1)*page_size).limit(page_size).all()
    return {"code": 200, "data": {"items": [_serialize_ot(o, db) for o in items], "total": total, "page": page, "page_size": page_size}}


@app.post("/api/onetime-projects")
def create_onetime(body: dict, user: User = Depends(require_write_access), db: Session = Depends(get_db)):
    if not (check_permission(user, "admin:config") or user.role == "tenant_admin"):
        raise HTTPException(403, "权限不足")
    o = OneTimeProject(tenant_id=user.tenant_id, company_id=body["company_id"],
                       project_type=body["project_type"], revenue=Decimal(str(body["revenue"])),
                       cost=Decimal(str(body.get("cost", 0))),
                       supplier_id=body.get("supplier_id"), owner_id=body["owner_id"],
                       completion_date=parse_date(body.get("completion_date")))
    db.add(o)
    db.flush()
    bill = Bill(tenant_id=user.tenant_id, company_id=body["company_id"],
                onetime_project_id=o.id, bill_type="onetime",
                billing_year=o.completion_date.year if o.completion_date else date.today().year,
                billing_month=o.completion_date.month if o.completion_date else date.today().month,
                receivable_amount=o.revenue - o.cost, follow_up_user_id=o.owner_id)
    db.add(bill)
    db.commit()
    return {"code": 200, "data": {"id": o.id}}


@app.put("/api/onetime-projects/{oid}")
def update_onetime(oid: int, body: dict, user: User = Depends(require_write_access), db: Session = Depends(get_db)):
    if not (check_permission(user, "admin:config") or user.role == "tenant_admin"):
        raise HTTPException(403, "权限不足")
    q = db.query(OneTimeProject).filter(OneTimeProject.id == oid)
    if user.tenant_id:
        q = q.filter(OneTimeProject.tenant_id == user.tenant_id)
    o = q.first()
    if not o:
        raise HTTPException(404, "业务不存在")
    for f in ["project_type"]:
        if f in body: setattr(o, f, body[f])
    if "revenue" in body: o.revenue = Decimal(str(body["revenue"]))
    if "cost" in body: o.cost = Decimal(str(body["cost"]))
    db.commit()
    return {"code": 200, "message": "更新成功"}


@app.put("/api/onetime-projects/{oid}/receive")
def receive_onetime(oid: int, body: dict, user: User = Depends(require_write_access), db: Session = Depends(get_db)):
    q = db.query(OneTimeProject).filter(OneTimeProject.id == oid)
    if user.tenant_id:
        q = q.filter(OneTimeProject.tenant_id == user.tenant_id)
    o = q.first()
    if not o:
        raise HTTPException(404, "业务不存在")
    o.is_received = True
    o.receive_date = parse_date(body.get("receive_date"))
    bq = db.query(Bill).filter(Bill.onetime_project_id == oid)
    if user.tenant_id:
        bq = bq.filter(Bill.tenant_id == user.tenant_id)
    bill = bq.first()
    if bill:
        bill.payment_status = "paid"
        bill.paid_amount = bill.receivable_amount
    db.commit()
    return {"code": 200, "message": "已标记收款"}


def _serialize_ot(o, db):
    owner = db.query(User).filter(User.id == o.owner_id).first()
    return {"id": o.id, "company_id": o.company_id, "project_type": o.project_type,
            "revenue": float(o.revenue), "cost": float(o.cost),
            "gross_profit": float(o.revenue - o.cost),
            "supplier_id": o.supplier_id, "owner_id": o.owner_id,
            "owner_name": owner.name if owner else "",
            "completion_date": str(o.completion_date) if o.completion_date else None,
            "is_received": o.is_received,
            "receive_date": str(o.receive_date) if o.receive_date else None}


# ==================== 账单管理 ====================
@app.get("/api/bills")
def list_bills(company_id: int = None, year: int = None, month: int = None,
               status: str = None, page: int = 1, page_size: int = 20,
               user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(Bill)
    if user.tenant_id:
        q = q.filter(Bill.tenant_id == user.tenant_id)
    if company_id:
        q = q.filter(Bill.company_id == company_id)
    if year:
        q = q.filter(Bill.billing_year == year)
    if month:
        q = q.filter(Bill.billing_month == month)
    if status:
        q = q.filter(Bill.payment_status == status)
    total = q.count()
    items = q.order_by(Bill.id.desc()).offset((page-1)*page_size).limit(page_size).all()
    return {"code": 200, "data": {"items": [_serialize_bill(b, db) for b in items], "total": total, "page": page, "page_size": page_size}}


@app.get("/api/bills/{bid}")
def get_bill(bid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(Bill).filter(Bill.id == bid)
    if user.tenant_id:
        q = q.filter(Bill.tenant_id == user.tenant_id)
    b = q.first()
    if not b:
        raise HTTPException(404, "账单不存在")
    return {"code": 200, "data": _serialize_bill(b, db)}


@app.post("/api/bills/generate")
def generate_bills(body: dict, user: User = Depends(require_write_access), db: Session = Depends(get_db)):
    if not check_permission(user, "salary:manage") and user.role != "tenant_admin":
        raise HTTPException(403, "权限不足")
    year, month = body["year"], body["month"]
    count = 0
    sq = db.query(Subscription).filter(Subscription.is_active == True, Subscription.is_archived == False)
    if user.tenant_id:
        sq = sq.filter(Subscription.tenant_id == user.tenant_id)
    subs = sq.all()
    for sub in subs:
        eq = db.query(Bill).filter(Bill.subscription_id == sub.id, Bill.billing_year == year, Bill.billing_month == month)
        if user.tenant_id:
            eq = eq.filter(Bill.tenant_id == user.tenant_id)
        existing = eq.first()
        if existing:
            continue
        bill = Bill(tenant_id=user.tenant_id or sub.tenant_id, company_id=sub.company_id,
                    subscription_id=sub.id, bill_type="subscription",
                    billing_year=year, billing_month=month,
                    receivable_amount=sub.monthly_fee, follow_up_user_id=sub.service_owner_id)
        db.add(bill)
        pq = db.query(CustomerPrepayment).filter(CustomerPrepayment.company_id == sub.company_id, CustomerPrepayment.balance > 0)
        if user.tenant_id:
            pq = pq.filter(CustomerPrepayment.tenant_id == user.tenant_id)
        prepay = pq.first()
        if prepay:
            use = min(prepay.balance, bill.receivable_amount)
            bill.paid_amount = use
            bill.payment_status = "paid" if use >= bill.receivable_amount else "partial"
            prepay.balance -= use
            db.add(PaymentBillAllocation(tenant_id=user.tenant_id or sub.tenant_id,
                                         payment_record_id=None, bill_id=bill.id,
                                         allocation_amount=use, source="prepayment"))
        count += 1
    db.commit()
    return {"code": 200, "data": {"generated": count}}


def _serialize_bill(b, db):
    company = db.query(Company).filter(Company.id == b.company_id).first()
    return {"id": b.id, "company_id": b.company_id,
            "company_name": company.name if company else "",
            "subscription_id": b.subscription_id, "onetime_project_id": b.onetime_project_id,
            "bill_type": b.bill_type, "billing_year": b.billing_year, "billing_month": b.billing_month,
            "receivable_amount": float(b.receivable_amount), "paid_amount": float(b.paid_amount),
            "payment_status": b.payment_status, "is_overdue": b.is_overdue}


# ==================== 收款管理 ====================
@app.get("/api/payments")
def list_payments(company_id: int = None, verify_status: str = None,
                  year: int = None, month: int = None,
                  page: int = 1, page_size: int = 20,
                  user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(PaymentRecord)
    if user.tenant_id:
        q = q.filter(PaymentRecord.tenant_id == user.tenant_id)
    if user.data_scope == "SELF" and user.role == "employee":
        if check_permission(user, "payment:verify"):
            q = q.filter(PaymentRecord.assigned_verifier_id == user.id)
        else:
            q = q.filter(PaymentRecord.submitter_id == user.id)
    if company_id:
        q = q.filter(PaymentRecord.company_id == company_id)
    if verify_status:
        q = q.filter(PaymentRecord.verify_status == verify_status)
    if year and month:
        q = q.filter(func.year(PaymentRecord.payment_date) == year, func.month(PaymentRecord.payment_date) == month)
    total = q.count()
    items = q.order_by(PaymentRecord.id.desc()).offset((page-1)*page_size).limit(page_size).all()
    return {"code": 200, "data": {"items": [_serialize_payment(p, db) for p in items], "total": total, "page": page, "page_size": page_size}}


@app.get("/api/payments/{pid}")
def get_payment(pid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(PaymentRecord).filter(PaymentRecord.id == pid)
    if user.tenant_id:
        q = q.filter(PaymentRecord.tenant_id == user.tenant_id)
    p = q.first()
    if not p:
        raise HTTPException(404, "收款记录不存在")
    return {"code": 200, "data": _serialize_payment(p, db)}


@app.post("/api/payments")
def create_payment(body: dict, user: User = Depends(require_write_access), db: Session = Depends(get_db)):
    if not check_permission(user, "payment:submit") and user.role != "tenant_admin":
        raise HTTPException(403, "权限不足")
    pdate = parse_date(body["payment_date"])
    lq = db.query(LedgerValidation).filter(LedgerValidation.ledger_year == pdate.year,
         LedgerValidation.ledger_month == pdate.month, LedgerValidation.status == "locked")
    if user.tenant_id:
        lq = lq.filter(LedgerValidation.tenant_id == user.tenant_id)
    locked = lq.first()
    if locked:
        raise HTTPException(409, "该月已锁定，无法新增收款")
    p = PaymentRecord(tenant_id=user.tenant_id, company_id=body["company_id"],
                      amount=Decimal(str(body["amount"])), payment_date=pdate,
                      channel=body["channel"], submitter_id=user.id,
                      assigned_verifier_id=body["assigned_verifier_id"],
                      usage_type=body.get("usage_type", "public"), remark=body.get("remark"))
    db.add(p)
    db.flush()
    allocs = body.get("bill_allocations", [])
    total_alloc = Decimal("0")
    for a in allocs:
        amt = Decimal(str(a["allocation_amount"]))
        db.add(PaymentBillAllocation(tenant_id=user.tenant_id, payment_record_id=p.id,
                                     bill_id=a["bill_id"], allocation_amount=amt))
        total_alloc += amt
    p_amount = Decimal(str(body["amount"]))
    if total_alloc < p_amount:
        over = p_amount - total_alloc
        pq = db.query(CustomerPrepayment).filter(CustomerPrepayment.company_id == body["company_id"])
        if user.tenant_id:
            pq = pq.filter(CustomerPrepayment.tenant_id == user.tenant_id)
        prepay = pq.first()
        if prepay:
            prepay.balance += over
        else:
            db.add(CustomerPrepayment(tenant_id=user.tenant_id, company_id=body["company_id"],
                                      balance=over, source="overpayment"))
    db.commit()
    return {"code": 200, "data": {"id": p.id}}


@app.post("/api/payments/{pid}/verify")
def verify_payment(pid: int, body: dict, user: User = Depends(require_write_access), db: Session = Depends(get_db)):
    if not check_permission(user, "payment:verify") and user.role != "tenant_admin":
        raise HTTPException(403, "权限不足")
    q = db.query(PaymentRecord).filter(PaymentRecord.id == pid)
    if user.tenant_id:
        q = q.filter(PaymentRecord.tenant_id == user.tenant_id)
    p = q.first()
    if not p:
        raise HTTPException(404, "收款记录不存在")
    if p.assigned_verifier_id != user.id and user.data_scope != "ALL" and user.role != "tenant_admin":
        raise HTTPException(403, "无权核对非自己的收款")
    action = body["action"]
    if action == "approve":
        p.verify_status = "approved"
        if p.usage_type == "public":
            aq = db.query(PaymentBillAllocation).filter(PaymentBillAllocation.payment_record_id == pid)
            if user.tenant_id:
                aq = aq.filter(PaymentBillAllocation.tenant_id == user.tenant_id)
            allocs = aq.all()
            for a in allocs:
                bill = db.query(Bill).filter(Bill.id == a.bill_id).first()
                if bill:
                    bill.paid_amount = Decimal(str(bill.paid_amount)) + a.allocation_amount
                    if bill.paid_amount >= bill.receivable_amount:
                        bill.payment_status = "paid"
                    elif bill.paid_amount > 0:
                        bill.payment_status = "partial"
    else:
        p.verify_status = "rejected"
        p.reject_reason = body.get("reject_reason", "")
    db.commit()
    return {"code": 200, "message": "核对完成"}


@app.post("/api/payments/batch-verify")
def batch_verify(body: dict, user: User = Depends(require_write_access), db: Session = Depends(get_db)):
    if not check_permission(user, "payment:verify") and user.role != "tenant_admin":
        raise HTTPException(403, "权限不足")
    action = body["action"]
    for pid in body["ids"]:
        q = db.query(PaymentRecord).filter(PaymentRecord.id == pid)
        if user.tenant_id:
            q = q.filter(PaymentRecord.tenant_id == user.tenant_id)
        p = q.first()
        if not p:
            continue
        if p.assigned_verifier_id != user.id and user.data_scope != "ALL" and user.role != "tenant_admin":
            continue
        p.verify_status = "approved" if action == "approve" else "rejected"
        if action == "approve" and p.usage_type == "public":
            aq = db.query(PaymentBillAllocation).filter(PaymentBillAllocation.payment_record_id == pid)
            if user.tenant_id:
                aq = aq.filter(PaymentBillAllocation.tenant_id == user.tenant_id)
            allocs = aq.all()
            for a in allocs:
                bill = db.query(Bill).filter(Bill.id == a.bill_id).first()
                if bill:
                    bill.paid_amount = Decimal(str(bill.paid_amount)) + a.allocation_amount
                    bill.payment_status = "paid" if bill.paid_amount >= bill.receivable_amount else "partial"
    db.commit()
    return {"code": 200, "message": "批量核对完成"}


def _serialize_payment(p, db):
    aq = db.query(PaymentBillAllocation).filter(PaymentBillAllocation.payment_record_id == p.id)
    if p.tenant_id:
        aq = aq.filter(PaymentBillAllocation.tenant_id == p.tenant_id)
    allocs = aq.all()
    company = db.query(Company).filter(Company.id == p.company_id).first()
    submitter = db.query(User).filter(User.id == p.submitter_id).first()
    verifier = db.query(User).filter(User.id == p.assigned_verifier_id).first()
    sq = db.query(PaymentScreenshot).filter(PaymentScreenshot.payment_record_id == p.id)
    if p.tenant_id:
        sq = sq.filter(PaymentScreenshot.tenant_id == p.tenant_id)
    screenshots = sq.all()
    return {"id": p.id, "company_id": p.company_id,
            "company_name": company.name if company else "",
            "amount": float(p.amount), "payment_date": str(p.payment_date),
            "channel": p.channel, "submitter_id": p.submitter_id,
            "submitter_name": submitter.name if submitter else "",
            "assigned_verifier_id": p.assigned_verifier_id,
            "verifier_name": verifier.name if verifier else "",
            "verify_status": p.verify_status, "reject_reason": p.reject_reason,
            "usage_type": p.usage_type, "remark": p.remark,
            "bill_allocations": [{"bill_id": a.bill_id, "allocation_amount": float(a.allocation_amount),
                                  "source": a.source} for a in allocs],
            "screenshots": [{"id": ss.id, "file_path": ss.file_path, "file_name": ss.file_name} for ss in screenshots]}


# ==================== 截图上传 ====================
@app.post("/api/payments/{pid}/screenshots")
async def upload_screenshot(pid: int, file: UploadFile = File(...),
                             user: User = Depends(require_write_access), db: Session = Depends(get_db)):
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(400, "仅支持 JPG/PNG 格式")
    contents = await file.read()
    if len(contents) > MAX_UPLOAD_SIZE:
        raise HTTPException(400, "文件超过5MB")
    q = db.query(PaymentScreenshot).filter(PaymentScreenshot.payment_record_id == pid)
    if user.tenant_id:
        q = q.filter(PaymentScreenshot.tenant_id == user.tenant_id)
    count = q.count()
    if count >= 3:
        raise HTTPException(400, "每条收款限3张截图")
    ext = file.filename.rsplit('.',1)[-1] if '.' in file.filename else 'jpg'
    fname = f"{uuid.uuid4().hex}.{ext}"
    fpath = os.path.join(UPLOAD_DIR, fname)
    with open(fpath, "wb") as f:
        f.write(contents)
    ss = PaymentScreenshot(tenant_id=user.tenant_id, payment_record_id=pid,
                          file_path=f"/uploads/{fname}", file_name=file.filename, file_size=len(contents))
    db.add(ss)
    db.commit()
    return {"code": 200, "data": {"id": ss.id, "file_path": ss.file_path}}


# ==================== 提成计算引擎 ====================
@app.post("/api/ledger/validate-and-calculate")
def validate_and_calculate(body: dict, user: User = Depends(require_write_access), db: Session = Depends(get_db)):
    if not check_permission(user, "salary:manage") and user.role != "tenant_admin":
        raise HTTPException(403, "权限不足")
    year, month = body["year"], body["month"]

    lq = db.query(LedgerValidation).filter(LedgerValidation.ledger_year == year, LedgerValidation.ledger_month == month)
    if user.tenant_id:
        lq = lq.filter(LedgerValidation.tenant_id == user.tenant_id)
    existing = lq.first()
    if existing and existing.status == "locked":
        raise HTTPException(409, "该月已锁定")
    if existing and existing.calculation_status == "running":
        raise HTTPException(409, "正在计算中，请稍候")

    if not existing:
        existing = LedgerValidation(tenant_id=user.tenant_id, ledger_year=year,
                                    ledger_month=month, status="calculating",
                                    calculation_status="running", locked_by=user.id, locked_at=datetime.utcnow())
        db.add(existing)
    else:
        existing.status = "calculating"
        existing.calculation_status = "running"
        existing.locked_by = user.id
        existing.locked_at = datetime.utcnow()
    db.flush()

    try:
        uq = db.query(User).filter(User.is_active == True)
        if user.tenant_id:
            uq = uq.filter(User.tenant_id == user.tenant_id)
        active_users = uq.all()

        bq = db.query(Bill).filter(Bill.billing_year == year, Bill.billing_month == month)
        if user.tenant_id:
            bq = bq.filter(Bill.tenant_id == user.tenant_id)
        bills = bq.all()

        commission_count = 0
        for bill in bills:
            if bill.bill_type == "subscription" and bill.subscription_id:
                sub = db.query(Subscription).filter(Subscription.id == bill.subscription_id).first()
                if not sub:
                    continue
                fee = _get_effective_fee(db, sub.id, year, month)
                commission = fee * Decimal("0.15")
                deduction = Decimal("0")
                if bill.payment_status in ("unpaid", "overdue"):
                    deduction = fee * Decimal("0.05")
                supplement_deduction = None
                if bill.payment_status == "paid":
                    supplement_deduction = _calc_supplement(db, bill.id, sub.id, bill.company_id, year, month, tenant_id=user.tenant_id)
                cd = CommissionDetail(tenant_id=user.tenant_id, user_id=sub.service_owner_id,
                                      commission_type="service", bill_id=bill.id,
                                      company_id=bill.company_id, subscription_id=sub.id,
                                      billing_year=year, billing_month=month, base_amount=fee,
                                      rate=Decimal("0.15"), commission_amount=commission,
                                      deduction_amount=deduction, supplement_amount=Decimal("0"),
                                      net_amount=commission - deduction, is_supplement=False,
                                      ledger_validation_id=existing.id)
                db.add(cd)
                commission_count += 1
                if supplement_deduction:
                    cd2 = CommissionDetail(tenant_id=user.tenant_id, user_id=supplement_deduction.user_id,
                                           commission_type="service", bill_id=bill.id,
                                           company_id=bill.company_id, subscription_id=sub.id,
                                           billing_year=year, billing_month=month, base_amount=Decimal("0"),
                                           rate=Decimal("0"), commission_amount=Decimal("0"),
                                           deduction_amount=Decimal("0"),
                                           supplement_amount=supplement_deduction.deduction_amount,
                                           net_amount=supplement_deduction.deduction_amount,
                                           is_supplement=True,
                                           supplement_for_user_id=supplement_deduction.user_id,
                                           ledger_validation_id=existing.id)
                    db.add(cd2)
                    commission_count += 1
                if sub.sales_owner_id and _in_sales_window(bill.company_id, year, month, db, user.tenant_id):
                    approved_alloc = _get_approved_allocations(db, bill.id, year, month, user.tenant_id)
                    for alloc_amt in approved_alloc:
                        sc = CommissionDetail(tenant_id=user.tenant_id, user_id=sub.sales_owner_id,
                                              commission_type="sales", bill_id=bill.id,
                                              company_id=bill.company_id, subscription_id=sub.id,
                                              billing_year=year, billing_month=month, base_amount=alloc_amt,
                                              rate=Decimal("0.15"),
                                              commission_amount=alloc_amt * Decimal("0.15"),
                                              deduction_amount=Decimal("0"), supplement_amount=Decimal("0"),
                                              net_amount=alloc_amt * Decimal("0.15"),
                                              is_supplement=False, ledger_validation_id=existing.id)
                        db.add(sc)
                        commission_count += 1

            elif bill.bill_type == "onetime" and bill.onetime_project_id:
                proj = db.query(OneTimeProject).filter(OneTimeProject.id == bill.onetime_project_id).first()
                if not proj:
                    continue
                gp = proj.revenue - proj.cost
                commission = gp * Decimal("0.20")
                deduction = Decimal("0") if proj.is_received else gp * Decimal("0.05")
                cd = CommissionDetail(tenant_id=user.tenant_id, user_id=proj.owner_id,
                                      commission_type="onetime", bill_id=bill.id,
                                      company_id=bill.company_id, onetime_project_id=proj.id,
                                      billing_year=year, billing_month=month, base_amount=gp,
                                      rate=Decimal("0.20"), commission_amount=commission,
                                      deduction_amount=deduction, supplement_amount=Decimal("0"),
                                      net_amount=commission - deduction, is_supplement=False,
                                      ledger_validation_id=existing.id)
                db.add(cd)
                commission_count += 1

        db.flush()

        salary_count = 0
        for u in active_users:
            dq = db.query(CommissionDetail).filter(
                CommissionDetail.user_id == u.id,
                CommissionDetail.ledger_validation_id == existing.id)
            if user.tenant_id:
                dq = dq.filter(CommissionDetail.tenant_id == user.tenant_id)
            details = dq.all()
            svc = sum(d.commission_amount for d in details if d.commission_type == "service" and not d.is_supplement)
            sls = sum(d.commission_amount for d in details if d.commission_type == "sales")
            ot = sum(d.commission_amount for d in details if d.commission_type == "onetime")
            ded = sum(d.deduction_amount for d in details)
            sup = sum(d.supplement_amount for d in details)
            gross = u.base_salary + svc + sls + ot + sup - ded
            ms = MonthlySalary(tenant_id=user.tenant_id, user_id=u.id,
                               salary_year=year, salary_month=month, base_salary=u.base_salary,
                               service_commission=svc, sales_commission=sls, onetime_commission=ot,
                               total_deduction=ded, total_supplement=sup, gross_payable=gross,
                               ledger_validation_id=existing.id)
            db.add(ms)
            salary_count += 1

        existing.status = "locked"
        existing.calculation_status = "completed"
        db.commit()
        return {"code": 200, "data": {"ledger_id": existing.id, "status": "locked",
                "salary_count": salary_count, "commission_count": commission_count}}

    except Exception as e:
        db.rollback()
        if existing:
            existing.calculation_status = "failed"
            existing.status = "unlocked"
            db.commit()
        raise HTTPException(500, f"计算失败: {str(e)}")


@app.get("/api/ledger/status")
def get_ledger_status(year: int = None, month: int = None,
                      user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(LedgerValidation)
    if user.tenant_id:
        q = q.filter(LedgerValidation.tenant_id == user.tenant_id)
    if year:
        q = q.filter(LedgerValidation.ledger_year == year)
    if month:
        q = q.filter(LedgerValidation.ledger_month == month)
    items = q.order_by(LedgerValidation.ledger_year.desc(), LedgerValidation.ledger_month.desc()).limit(24).all()
    return {"code": 200, "data": [{"id": l.id, "year": l.ledger_year, "month": l.ledger_month,
            "status": l.status, "calculation_status": l.calculation_status,
            "locked_at": str(l.locked_at) if l.locked_at else None} for l in items]}


@app.post("/api/ledger/{lid}/unlock")
def unlock_ledger(lid: int, user: User = Depends(require_write_access), db: Session = Depends(get_db)):
    if not check_permission(user, "salary:manage") and user.role != "tenant_admin":
        raise HTTPException(403, "权限不足")
    q = db.query(LedgerValidation).filter(LedgerValidation.id == lid)
    if user.tenant_id:
        q = q.filter(LedgerValidation.tenant_id == user.tenant_id)
    ledger = q.first()
    if not ledger:
        raise HTTPException(404, "锁定记录不存在")
    if ledger.status != "locked":
        raise HTTPException(422, "仅锁定状态可撤销")
    lq = db.query(LedgerValidation).filter(LedgerValidation.status == "locked")
    if user.tenant_id:
        lq = lq.filter(LedgerValidation.tenant_id == user.tenant_id)
    latest = lq.order_by(LedgerValidation.ledger_year.desc(), LedgerValidation.ledger_month.desc()).first()
    if latest and latest.id != ledger.id:
        raise HTTPException(422, "仅最近一个锁定月可撤销")

    mq = db.query(MonthlySalary).filter(MonthlySalary.ledger_validation_id == ledger.id)
    if user.tenant_id:
        mq = mq.filter(MonthlySalary.tenant_id == user.tenant_id)
    mq.delete()

    pq = db.query(CommissionDetail).filter(
        CommissionDetail.ledger_validation_id == ledger.id,
        CommissionDetail.is_supplement == False,
        CommissionDetail.deduction_amount > 0)
    if user.tenant_id:
        pq = pq.filter(CommissionDetail.tenant_id == user.tenant_id)
    preserved = pq.all()
    for d in preserved:
        d.commission_amount = Decimal("0")
        d.base_amount = Decimal("0")
        d.rate = Decimal("0")
        d.net_amount = d.deduction_amount
    dq = db.query(CommissionDetail).filter(
        CommissionDetail.ledger_validation_id == ledger.id,
        CommissionDetail.is_supplement == False,
        CommissionDetail.deduction_amount == 0)
    if user.tenant_id:
        dq = dq.filter(CommissionDetail.tenant_id == user.tenant_id)
    dq.delete()

    ledger.status = "unlocked"
    ledger.calculation_status = "idle"
    ledger.unlocked_by = user.id
    ledger.unlocked_at = datetime.utcnow()
    db.commit()
    return {"code": 200, "message": "已撤销"}


# ==================== 薪资管理 ====================
@app.get("/api/salaries")
def list_salaries(year: int = None, month: int = None,
                  page: int = 1, page_size: int = 20,
                  user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(MonthlySalary)
    if user.tenant_id:
        q = q.filter(MonthlySalary.tenant_id == user.tenant_id)
    if user.data_scope == "SELF" and user.role == "employee":
        q = q.filter(MonthlySalary.user_id == user.id)
    if year:
        q = q.filter(MonthlySalary.salary_year == year)
    if month:
        q = q.filter(MonthlySalary.salary_month == month)
    total = q.count()
    items = q.order_by(MonthlySalary.salary_year.desc(), MonthlySalary.salary_month.desc()).offset((page-1)*page_size).limit(page_size).all()
    result = []
    for ms in items:
        u = db.query(User).filter(User.id == ms.user_id).first()
        result.append({"id": ms.id, "user_id": ms.user_id, "user_name": u.name if u else "",
                       "year": ms.salary_year, "month": ms.salary_month,
                       "base_salary": float(ms.base_salary),
                       "service_commission": float(ms.service_commission),
                       "sales_commission": float(ms.sales_commission),
                       "onetime_commission": float(ms.onetime_commission),
                       "total_deduction": float(ms.total_deduction),
                       "total_supplement": float(ms.total_supplement),
                       "gross_payable": float(ms.gross_payable)})
    return {"code": 200, "data": {"items": result, "total": total, "page": page, "page_size": page_size}}


@app.get("/api/salaries/{uid}/{year}/{month}")
def get_salary_detail(uid: int, year: int, month: int,
                      user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.data_scope == "SELF" and user.role == "employee" and uid != user.id:
        raise HTTPException(403, "无权查看他人薪资")
    mq = db.query(MonthlySalary).filter(MonthlySalary.user_id == uid,
             MonthlySalary.salary_year == year, MonthlySalary.salary_month == month)
    if user.tenant_id:
        mq = mq.filter(MonthlySalary.tenant_id == user.tenant_id)
    ms = mq.first()
    if not ms:
        raise HTTPException(404, "薪资记录不存在")
    dq = db.query(CommissionDetail).filter(CommissionDetail.user_id == uid,
          CommissionDetail.billing_year == year, CommissionDetail.billing_month == month)
    if user.tenant_id:
        dq = dq.filter(CommissionDetail.tenant_id == user.tenant_id)
    details = dq.all()
    return {"code": 200, "data": {"user_id": ms.user_id, "year": ms.salary_year, "month": ms.salary_month,
            "base_salary": float(ms.base_salary),
            "service_commission": float(ms.service_commission),
            "sales_commission": float(ms.sales_commission),
            "onetime_commission": float(ms.onetime_commission),
            "total_deduction": float(ms.total_deduction),
            "total_supplement": float(ms.total_supplement),
            "gross_payable": float(ms.gross_payable),
            "commission_details": [{"type": d.commission_type, "company_id": d.company_id,
             "base_amount": float(d.base_amount), "rate": float(d.rate),
             "commission_amount": float(d.commission_amount),
             "deduction_amount": float(d.deduction_amount),
             "supplement_amount": float(d.supplement_amount),
             "net_amount": float(d.net_amount), "is_supplement": d.is_supplement} for d in details]}}


# ==================== 报表 ====================
@app.get("/api/reports/region")
def report_region(year: int, month: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    pq = db.query(PaymentRecord).filter(
        func.year(PaymentRecord.payment_date) == year, func.month(PaymentRecord.payment_date) == month,
        PaymentRecord.verify_status == "approved", PaymentRecord.usage_type == "public")
    if user.tenant_id:
        pq = pq.filter(PaymentRecord.tenant_id == user.tenant_id)
    payments = pq.all()
    regions = {}
    for p in payments:
        cq = db.query(Company).filter(Company.id == p.company_id)
        if user.tenant_id:
            cq = cq.filter(Company.tenant_id == user.tenant_id)
        c = cq.first()
        tags = json.loads(c.region_tags) if c and isinstance(c.region_tags, str) else (c.region_tags if c else [])
        for tag in tags:
            regions[tag] = regions.get(tag, 0) + float(p.amount)
    return {"code": 200, "data": [{"region": k, "amount": v} for k, v in regions.items()]}


@app.get("/api/reports/cost")
def report_cost(year: int, month: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sq = db.query(Subscription).filter(Subscription.is_active == True, Subscription.is_archived == False, Subscription.is_cost_type == True)
    if user.tenant_id:
        sq = sq.filter(Subscription.tenant_id == user.tenant_id)
    subs = sq.all()
    cost_items = []
    for s in subs:
        fq = db.query(FeeHistory).filter(FeeHistory.subscription_id == s.id, FeeHistory.effective_date <= date(year, month, 1))
        if user.tenant_id:
            fq = fq.filter(FeeHistory.tenant_id == user.tenant_id)
        fees = fq.order_by(FeeHistory.effective_date.desc()).first()
        monthly = fees.new_fee if fees else s.monthly_fee
        cost_items.append({"type": s.service_type, "amount": float(monthly)})
    return {"code": 200, "data": cost_items}


@app.get("/api/reports/trend")
def report_trend(end_year: int, end_month: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    result = []
    for i in range(11, -1, -1):
        y, m = end_year, end_month - i
        if m <= 0: y -= 1; m += 12
        tq = db.query(func.sum(PaymentRecord.amount)).filter(
            func.year(PaymentRecord.payment_date) == y, func.month(PaymentRecord.payment_date) == m,
            PaymentRecord.verify_status == "approved", PaymentRecord.usage_type == "public")
        if user.tenant_id:
            tq = tq.filter(PaymentRecord.tenant_id == user.tenant_id)
        total = tq.scalar() or 0
        result.append({"year": y, "month": m, "amount": float(total)})
    return {"code": 200, "data": result}


# ==================== 成本预设 / 阶梯配置 ====================
@app.get("/api/cost-presets")
def list_cost_presets(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(CostPreset)
    if user.tenant_id:
        q = q.filter(CostPreset.tenant_id == user.tenant_id)
    items = q.all()
    return {"code": 200, "data": [{"id": c.id, "business_type": c.business_type,
            "default_cost": float(c.default_cost), "is_active": c.is_active} for c in items]}


@app.post("/api/cost-presets")
def create_cost_preset(body: dict, user: User = Depends(require_write_access), db: Session = Depends(get_db)):
    if not (check_permission(user, "admin:config") or user.role == "tenant_admin"):
        raise HTTPException(403, "权限不足")
    c = CostPreset(tenant_id=user.tenant_id, business_type=body["business_type"],
                   default_cost=Decimal(str(body["default_cost"])))
    db.add(c)
    db.commit()
    return {"code": 200, "data": {"id": c.id}}


@app.get("/api/bonus-tiers")
def list_bonus_tiers(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(BonusTier)
    if user.tenant_id:
        q = q.filter(BonusTier.tenant_id == user.tenant_id)
    items = q.order_by(BonusTier.sort_order).all()
    return {"code": 200, "data": [{"id": t.id, "tier_name": t.tier_name,
            "min_amount": float(t.min_amount),
            "max_amount": float(t.max_amount) if t.max_amount else None,
            "bonus_rate": float(t.bonus_rate), "sort_order": t.sort_order} for t in items]}


@app.post("/api/bonus-tiers")
def create_bonus_tier(body: dict, user: User = Depends(require_write_access), db: Session = Depends(get_db)):
    if not (check_permission(user, "admin:config") or user.role == "tenant_admin"):
        raise HTTPException(403, "权限不足")
    t = BonusTier(tenant_id=user.tenant_id, tier_name=body["tier_name"],
                  min_amount=Decimal(str(body["min_amount"])),
                  max_amount=Decimal(str(body["max_amount"])) if body.get("max_amount") else None,
                  bonus_rate=Decimal(str(body["bonus_rate"])), sort_order=body.get("sort_order", 0))
    db.add(t)
    db.commit()
    return {"code": 200, "data": {"id": t.id}}


# ==================== 静态文件 ====================
@app.get("/api/health")
def health():
    return {"status": "ok", "version": "2.0.0", "multi_tenant": True}


# ==================== 辅助函数 ====================
def parse_date(val):
    if not val:
        return None
    if isinstance(val, date):
        return val
    return date.fromisoformat(str(val))


def _get_effective_fee(db, sub_id, year, month):
    target = date(year, month, 1)
    fh = db.query(FeeHistory).filter(FeeHistory.subscription_id == sub_id,
         FeeHistory.effective_date <= target).order_by(FeeHistory.effective_date.desc()).first()
    if fh:
        return fh.new_fee
    sub = db.query(Subscription).filter(Subscription.id == sub_id).first()
    return sub.monthly_fee if sub else Decimal("0")


def _calc_supplement(db, bill_id, sub_id, company_id, year, month, tenant_id=None):
    current_month_seq = year * 12 + month
    dq = db.query(CommissionDetail).filter(
        CommissionDetail.subscription_id == sub_id,
        CommissionDetail.commission_type == "service",
        CommissionDetail.deduction_amount > 0,
        CommissionDetail.is_supplement == False
    )
    if tenant_id:
        dq = dq.filter(CommissionDetail.tenant_id == tenant_id)
    deductions = dq.all()
    valid_deductions = [d for d in deductions if (d.billing_year * 12 + d.billing_month) < current_month_seq]
    if not valid_deductions:
        return None
    deduction = valid_deductions[0]
    already_supp = db.query(CommissionDetail).filter(
        CommissionDetail.subscription_id == sub_id,
        CommissionDetail.is_supplement == True,
        CommissionDetail.supplement_for_user_id == deduction.user_id,
        CommissionDetail.billing_year == deduction.billing_year,
        CommissionDetail.billing_month == deduction.billing_month
    ).first()
    if already_supp:
        return None
    return deduction


def _in_sales_window(company_id, year, month, db, tenant_id=None):
    cq = db.query(Company).filter(Company.id == company_id)
    if tenant_id:
        cq = cq.filter(Company.tenant_id == tenant_id)
    c = cq.first()
    if not c or not c.is_new_customer or not c.service_start_date:
        return False
    start = c.service_start_date
    s_months = start.year * 12 + start.month
    t_months = year * 12 + month
    return 0 <= (t_months - s_months) <= 11


def _get_approved_allocations(db, bill_id, year, month, tenant_id=None):
    q = db.query(PaymentBillAllocation).join(PaymentRecord).filter(
        PaymentBillAllocation.bill_id == bill_id,
        PaymentRecord.verify_status == "approved",
        PaymentRecord.usage_type == "public",
        func.year(PaymentRecord.payment_date) == year,
        func.month(PaymentRecord.payment_date) == month
    )
    if tenant_id:
        q = q.filter(PaymentBillAllocation.tenant_id == tenant_id)
    allocs = q.all()
    return [a.allocation_amount for a in allocs]
