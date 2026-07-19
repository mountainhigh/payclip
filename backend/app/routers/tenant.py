"""租户管理员接口：邀请链接 + 租户信息"""
import secrets
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Tenant, User, InvitationLink
from ..core.auth import require_tenant_admin

router = APIRouter(prefix="/api/tenant", tags=["租户管理"])


def _serialize_tenant(t, db):
    emp_count = db.query(User).filter(User.tenant_id == t.id, User.is_active == True).count()
    return {"id": t.id, "name": t.name, "plan": t.plan, "status": t.status,
            "trial_expires": str(t.trial_expires) if t.trial_expires else None,
            "plan_expires": str(t.plan_expires) if t.plan_expires else None,
            "max_employees": t.max_employees, "employee_count": emp_count,
            "contact_phone": t.contact_phone, "remark": t.remark,
            "created_at": str(t.created_at)}


@router.post("/invitations")
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


@router.get("/invitations")
def list_invitations(user: User = Depends(require_tenant_admin), db: Session = Depends(get_db)):
    items = db.query(InvitationLink).filter(InvitationLink.tenant_id == user.tenant_id)\
               .order_by(InvitationLink.id.desc()).all()
    return {"code": 200, "data": [{"id": i.id, "token": i.token, "is_used": i.is_used,
            "used_at": str(i.used_at) if i.used_at else None,
            "expires_at": str(i.expires_at) if i.expires_at else None,
            "created_at": str(i.created_at)} for i in items]}


@router.get("/info")
def get_tenant_info(user: User = Depends(require_tenant_admin), db: Session = Depends(get_db)):
    tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
    if not tenant:
        raise HTTPException(404, "租户不存在")
    return {"code": 200, "data": _serialize_tenant(tenant, db)}
