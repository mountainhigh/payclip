"""客户管理"""
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import User, Company, Bill
from ..core.auth import (get_current_user, check_permission, require_tenant_user,
                         require_write_access)
from ..utils import parse_date

router = APIRouter(prefix="/api/customers", tags=["客户管理"])


def _serialize_company(c):
    return {"id": c.id, "name": c.name,
            "region_tags": json.loads(c.region_tags) if isinstance(c.region_tags, str) else c.region_tags,
            "is_new_customer": c.is_new_customer,
            "service_start_date": str(c.service_start_date) if c.service_start_date else None,
            "status": c.status, "introducer_type": c.introducer_type,
            "introducer_user_id": c.introducer_user_id, "introducer_name": c.introducer_name,
            "sales_person_id": c.sales_person_id, "contact_phone": c.contact_phone,
            "contact_email": c.contact_email, "remark": c.remark}


@router.get("")
def list_customers(keyword: str = "", page: int = 1, page_size: int = 20,
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(Company).filter(Company.is_archived == False)
    if user.tenant_id:
        q = q.filter(Company.tenant_id == user.tenant_id)
    if keyword:
        q = q.filter(Company.name.contains(keyword))
    total = q.count()
    items = q.order_by(Company.id.desc()).offset((page-1)*page_size).limit(page_size).all()
    return {"code": 200, "data": {"items": [_serialize_company(c) for c in items],
            "total": total, "page": page, "page_size": page_size}}


@router.get("/{cid}")
def get_customer(cid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(Company).filter(Company.id == cid, Company.is_archived == False)
    if user.tenant_id:
        q = q.filter(Company.tenant_id == user.tenant_id)
    c = q.first()
    if not c:
        raise HTTPException(404, "客户不存在")
    return {"code": 200, "data": _serialize_company(c)}


@router.post("")
def create_customer(body: dict, user: User = Depends(require_tenant_user), db: Session = Depends(get_db)):
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


@router.put("/{cid}")
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


@router.delete("/{cid}")
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
