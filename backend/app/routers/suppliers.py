"""供应商管理"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import User, Supplier
from ..core.auth import (get_current_user, check_permission, require_tenant_user,
                         require_write_access)

router = APIRouter(prefix="/api/suppliers", tags=["供应商管理"])


@router.get("")
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


@router.post("")
def create_supplier(body: dict, user: User = Depends(require_tenant_user), db: Session = Depends(get_db)):
    if not (check_permission(user, "admin:config") or user.role == "tenant_admin"):
        raise HTTPException(403, "权限不足")
    s = Supplier(tenant_id=user.tenant_id, name=body["name"],
                 type=body.get("type","其他"), contact=body.get("contact"), remark=body.get("remark"))
    db.add(s)
    db.commit()
    return {"code": 200, "data": {"id": s.id}}


@router.put("/{sid}")
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


@router.delete("/{sid}")
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
