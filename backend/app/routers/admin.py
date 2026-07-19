"""平台管理员接口：租户管理 + 注册码管理"""
import secrets
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Tenant, User, RegistrationCode
from ..core.auth import require_super_admin

router = APIRouter(prefix="/api/admin", tags=["平台管理"])


def _serialize_tenant(t, db):
    emp_count = db.query(User).filter(User.tenant_id == t.id, User.is_active == True).count()
    return {"id": t.id, "name": t.name, "plan": t.plan, "status": t.status,
            "trial_expires": str(t.trial_expires) if t.trial_expires else None,
            "plan_expires": str(t.plan_expires) if t.plan_expires else None,
            "max_employees": t.max_employees, "employee_count": emp_count,
            "contact_phone": t.contact_phone, "remark": t.remark,
            "created_at": str(t.created_at)}


@router.get("/tenants")
def list_tenants(page: int = 1, page_size: int = 20,
                 user: User = Depends(require_super_admin), db: Session = Depends(get_db)):
    q = db.query(Tenant)
    total = q.count()
    items = q.order_by(Tenant.id.desc()).offset((page-1)*page_size).limit(page_size).all()
    return {"code": 200, "data": {"items": [_serialize_tenant(t, db) for t in items],
            "total": total, "page": page, "page_size": page_size}}


@router.post("/registration-codes")
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


@router.get("/registration-codes")
def list_registration_codes(page: int = 1, page_size: int = 20,
                             user: User = Depends(require_super_admin), db: Session = Depends(get_db)):
    q = db.query(RegistrationCode)
    total = q.count()
    items = q.order_by(RegistrationCode.id.desc()).offset((page-1)*page_size).limit(page_size).all()
    return {"code": 200, "data": {"items": [{"id": r.id, "code": r.code, "plan": r.plan,
            "duration_days": r.duration_days, "is_used": r.is_used,
            "used_at": str(r.used_at) if r.used_at else None, "remark": r.remark,
            "created_at": str(r.created_at)} for r in items], "total": total, "page": page, "page_size": page_size}}


@router.put("/tenants/{tid}/status")
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


@router.post("/tenants/{tid}/renew")
def renew_tenant(tid: int, body: dict,
                 user: User = Depends(require_super_admin), db: Session = Depends(get_db)):
    tenant = db.query(Tenant).filter(Tenant.id == tid).first()
    if not tenant:
        raise HTTPException(404, "租户不存在")
    plan = body.get("plan", "monthly")
    days_map = {"monthly": 30, "yearly": 365, "trial": 30}
    days = days_map.get(plan, 30)
    base = tenant.plan_expires if tenant.plan_expires and tenant.plan_expires > datetime.utcnow() else datetime.utcnow()
    tenant.plan = plan
    tenant.status = "active"
    tenant.plan_expires = base + timedelta(days=days)
    tenant.trial_expires = tenant.plan_expires
    tenant.max_employees = body.get("max_employees", 20 if plan != "trial" else 3)
    db.commit()
    return {"code": 200, "message": "续费成功", "data": _serialize_tenant(tenant, db)}
