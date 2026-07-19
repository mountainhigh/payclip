"""系统配置：成本预设 + 阶梯奖金"""
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import User, CostPreset, BonusTier
from ..core.auth import (get_current_user, check_permission, require_tenant_user)

router = APIRouter(prefix="/api", tags=["系统配置"])


@router.get("/cost-presets")
def list_cost_presets(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(CostPreset)
    if user.tenant_id:
        q = q.filter(CostPreset.tenant_id == user.tenant_id)
    items = q.all()
    return {"code": 200, "data": [{"id": c.id, "business_type": c.business_type,
            "default_cost": float(c.default_cost), "is_active": c.is_active} for c in items]}


@router.post("/cost-presets")
def create_cost_preset(body: dict, user: User = Depends(require_tenant_user), db: Session = Depends(get_db)):
    if not (check_permission(user, "admin:config") or user.role == "tenant_admin"):
        raise HTTPException(403, "权限不足")
    c = CostPreset(tenant_id=user.tenant_id, business_type=body["business_type"],
                   default_cost=Decimal(str(body["default_cost"])))
    db.add(c)
    db.commit()
    return {"code": 200, "data": {"id": c.id}}


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
