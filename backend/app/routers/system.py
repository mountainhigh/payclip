"""系统配置：成本预设 + 阶梯奖金 + 收款渠道 + 服务类型"""
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import User, CostPreset, BonusTier, PaymentChannel, ServiceType, Supplier
from ..core.auth import (get_current_user, check_permission, require_tenant_user,
                         require_write_access)

router = APIRouter(prefix="/api", tags=["系统配置"])


@router.get("/cost-presets")
def list_cost_presets(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(CostPreset)
    if user.tenant_id:
        q = q.filter(CostPreset.tenant_id == user.tenant_id)
    items = q.all()
    suppliers_map = {}
    if items:
        sids = set(c.supplier_id for c in items if c.supplier_id)
        if sids:
            suppliers = db.query(Supplier).filter(Supplier.id.in_(sids)).all()
            suppliers_map = {s.id: s.name for s in suppliers}
    return {"code": 200, "data": [{"id": c.id, "business_type": c.business_type,
            "default_cost": float(c.default_cost), "supplier_id": c.supplier_id,
            "supplier_name": suppliers_map.get(c.supplier_id) or "", "is_active": c.is_active} for c in items]}


@router.post("/cost-presets")
def create_cost_preset(body: dict, user: User = Depends(require_tenant_user), db: Session = Depends(get_db)):
    if not (check_permission(user, "admin:config") or user.role == "tenant_admin"):
        raise HTTPException(403, "权限不足")
    c = CostPreset(tenant_id=user.tenant_id, business_type=body["business_type"],
                   default_cost=Decimal(str(body["default_cost"])),
                   supplier_id=body.get("supplier_id"))
    db.add(c)
    db.commit()
    return {"code": 200, "data": {"id": c.id}}


@router.put("/cost-presets/{cid}")
def update_cost_preset(cid: int, body: dict, user: User = Depends(require_write_access),
                       db: Session = Depends(get_db)):
    if not (check_permission(user, "admin:config") or user.role == "tenant_admin"):
        raise HTTPException(403, "权限不足")
    q = db.query(CostPreset).filter(CostPreset.id == cid)
    if user.tenant_id:
        q = q.filter(CostPreset.tenant_id == user.tenant_id)
    c = q.first()
    if not c:
        raise HTTPException(404, "成本预设不存在")
    if "business_type" in body:
        c.business_type = body["business_type"]
    if "default_cost" in body:
        c.default_cost = Decimal(str(body["default_cost"]))
    if "supplier_id" in body:
        c.supplier_id = body["supplier_id"]
    if "is_active" in body:
        c.is_active = bool(body["is_active"])
    db.commit()
    return {"code": 200, "message": "已更新"}


@router.get("/bonus-tiers")
def list_bonus_tiers(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(BonusTier)
    if user.tenant_id:
        q = q.filter(BonusTier.tenant_id == user.tenant_id)
    items = q.order_by(BonusTier.sort_order).all()
    return {"code": 200, "data": [{"id": t.id, "tier_name": t.tier_name,
            "min_amount": float(t.min_amount),
            "max_amount": float(t.max_amount) if t.max_amount else None,
            "bonus_rate": float(t.bonus_rate), "sort_order": t.sort_order} for t in items]}


@router.post("/bonus-tiers")
def create_bonus_tier(body: dict, user: User = Depends(require_tenant_user), db: Session = Depends(get_db)):
    if not (check_permission(user, "admin:config") or user.role == "tenant_admin"):
        raise HTTPException(403, "权限不足")
    t = BonusTier(tenant_id=user.tenant_id, tier_name=body["tier_name"],
                  min_amount=Decimal(str(body["min_amount"])),
                  max_amount=Decimal(str(body["max_amount"])) if body.get("max_amount") else None,
                  bonus_rate=Decimal(str(body["bonus_rate"])),
                  sort_order=body.get("sort_order", 0))
    db.add(t)
    db.commit()
    return {"code": 200, "data": {"id": t.id}}


@router.put("/bonus-tiers/{bid}")
def update_bonus_tier(bid: int, body: dict, user: User = Depends(require_write_access),
                      db: Session = Depends(get_db)):
    if not (check_permission(user, "admin:config") or user.role == "tenant_admin"):
        raise HTTPException(403, "权限不足")
    q = db.query(BonusTier).filter(BonusTier.id == bid)
    if user.tenant_id:
        q = q.filter(BonusTier.tenant_id == user.tenant_id)
    t = q.first()
    if not t:
        raise HTTPException(404, "阶梯奖金不存在")
    if "tier_name" in body:
        t.tier_name = body["tier_name"]
    if "min_amount" in body:
        t.min_amount = Decimal(str(body["min_amount"]))
    if "max_amount" in body:
        t.max_amount = Decimal(str(body["max_amount"])) if body.get("max_amount") else None
    if "bonus_rate" in body:
        t.bonus_rate = Decimal(str(body["bonus_rate"]))
    if "sort_order" in body:
        t.sort_order = body["sort_order"]
    db.commit()
    return {"code": 200, "message": "已更新"}


# ==================== 收款渠道配置 ====================

@router.get("/payment-channels")
def list_payment_channels(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(PaymentChannel)
    if user.tenant_id:
        q = q.filter(PaymentChannel.tenant_id == user.tenant_id)
    items = q.order_by(PaymentChannel.sort_order, PaymentChannel.id).all()
    return {"code": 200, "data": [{"id": c.id, "name": c.name, "code": c.code,
            "payee_name": c.payee_name or "", "account_number": c.account_number or "",
            "account_type": c.account_type or "", "is_active": c.is_active,
            "sort_order": c.sort_order, "remark": c.remark or ""} for c in items]}


@router.post("/payment-channels")
def create_payment_channel(body: dict, user: User = Depends(require_tenant_user),
                           db: Session = Depends(get_db)):
    if not (check_permission(user, "admin:config") or user.role == "tenant_admin"):
        raise HTTPException(403, "权限不足")
    c = PaymentChannel(tenant_id=user.tenant_id, name=body["name"], code=body.get("code") or body["name"],
                       payee_name=body.get("payee_name"), account_number=body.get("account_number"),
                       account_type=body.get("account_type"), is_active=body.get("is_active", True),
                       sort_order=body.get("sort_order", 0), remark=body.get("remark"))
    db.add(c)
    db.commit()
    return {"code": 200, "data": {"id": c.id}}


@router.put("/payment-channels/{cid}")
def update_payment_channel(cid: int, body: dict, user: User = Depends(require_write_access),
                           db: Session = Depends(get_db)):
    if not (check_permission(user, "admin:config") or user.role == "tenant_admin"):
        raise HTTPException(403, "权限不足")
    q = db.query(PaymentChannel).filter(PaymentChannel.id == cid)
    if user.tenant_id:
        q = q.filter(PaymentChannel.tenant_id == user.tenant_id)
    c = q.first()
    if not c:
        raise HTTPException(404, "收款渠道不存在")
    for f in ["name", "code", "payee_name", "account_number", "account_type", "remark"]:
        if f in body:
            setattr(c, f, body[f])
    if "is_active" in body:
        c.is_active = bool(body["is_active"])
    if "sort_order" in body:
        c.sort_order = body["sort_order"]
    db.commit()
    return {"code": 200, "message": "已更新"}


@router.delete("/payment-channels/{cid}")
def delete_payment_channel(cid: int, user: User = Depends(require_write_access),
                           db: Session = Depends(get_db)):
    if not (check_permission(user, "admin:config") or user.role == "tenant_admin"):
        raise HTTPException(403, "权限不足")
    q = db.query(PaymentChannel).filter(PaymentChannel.id == cid)
    if user.tenant_id:
        q = q.filter(PaymentChannel.tenant_id == user.tenant_id)
    c = q.first()
    if not c:
        raise HTTPException(404, "收款渠道不存在")
    db.delete(c)
    db.commit()
    return {"code": 200, "message": "已删除"}


# ==================== 服务类型配置 ====================

@router.get("/service-types")
def list_service_types(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(ServiceType)
    if user.tenant_id:
        q = q.filter(ServiceType.tenant_id == user.tenant_id)
    items = q.order_by(ServiceType.sort_order, ServiceType.id).all()
    return {"code": 200, "data": [{"id": t.id, "name": t.name, "is_active": t.is_active,
            "sort_order": t.sort_order, "remark": t.remark or ""} for t in items]}


@router.post("/service-types")
def create_service_type(body: dict, user: User = Depends(require_tenant_user),
                        db: Session = Depends(get_db)):
    if not (check_permission(user, "admin:config") or user.role == "tenant_admin"):
        raise HTTPException(403, "权限不足")
    t = ServiceType(tenant_id=user.tenant_id, name=body["name"],
                    is_active=body.get("is_active", True),
                    sort_order=body.get("sort_order", 0), remark=body.get("remark"))
    db.add(t)
    db.commit()
    return {"code": 200, "data": {"id": t.id}}


@router.put("/service-types/{tid}")
def update_service_type(tid: int, body: dict, user: User = Depends(require_write_access),
                        db: Session = Depends(get_db)):
    if not (check_permission(user, "admin:config") or user.role == "tenant_admin"):
        raise HTTPException(403, "权限不足")
    q = db.query(ServiceType).filter(ServiceType.id == tid)
    if user.tenant_id:
        q = q.filter(ServiceType.tenant_id == user.tenant_id)
    t = q.first()
    if not t:
        raise HTTPException(404, "服务类型不存在")
    for f in ["name", "remark"]:
        if f in body:
            setattr(t, f, body[f])
    if "is_active" in body:
        t.is_active = bool(body["is_active"])
    if "sort_order" in body:
        t.sort_order = body["sort_order"]
    db.commit()
    return {"code": 200, "message": "已更新"}


@router.delete("/service-types/{tid}")
def delete_service_type(tid: int, user: User = Depends(require_write_access),
                        db: Session = Depends(get_db)):
    if not (check_permission(user, "admin:config") or user.role == "tenant_admin"):
        raise HTTPException(403, "权限不足")
    q = db.query(ServiceType).filter(ServiceType.id == tid)
    if user.tenant_id:
        q = q.filter(ServiceType.tenant_id == user.tenant_id)
    t = q.first()
    if not t:
        raise HTTPException(404, "服务类型不存在")
    db.delete(t)
    db.commit()
    return {"code": 200, "message": "已删除"}

