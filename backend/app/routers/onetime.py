"""一次性业务管理"""
from decimal import Decimal
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from io import BytesIO
from ..database import get_db
from ..models import User, Company, Supplier, OneTimeProject, Bill
from ..core.auth import (get_current_user, check_permission, require_tenant_user,
                         require_write_access)
from ..utils import parse_date, export_rows, parse_import_file, build_template

router = APIRouter(prefix="/api/onetime-projects", tags=["一次性业务"])


ONETIME_FIELDS = [
    ("客户名称", "customer_name"), ("业务类型", "project_type"),
    ("收入", "revenue"), ("成本", "cost"),
    ("供应商", "supplier_name"), ("负责人", "owner_name"),
    ("完成日", "completion_date"),
]


def _find_user_by_name(db, tenant_id, name):
    if not name:
        return None
    q = db.query(User).filter(User.name == name, User.is_active == True)
    if tenant_id:
        q = q.filter(User.tenant_id == tenant_id)
    u = q.first()
    return u.id if u else None


def _find_company_by_name(db, tenant_id, name):
    if not name:
        return None
    q = db.query(Company).filter(Company.name == name, Company.is_archived == False)
    if tenant_id:
        q = q.filter(Company.tenant_id == tenant_id)
    c = q.first()
    return c.id if c else None


def _find_supplier_by_name(db, tenant_id, name):
    if not name:
        return None
    q = db.query(Supplier).filter(Supplier.name == name, Supplier.is_archived == False)
    if tenant_id:
        q = q.filter(Supplier.tenant_id == tenant_id)
    s = q.first()
    return s.id if s else None


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


@router.get("")
def list_onetime(company_id: int = None, page: int = 1, page_size: int = 20,
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(OneTimeProject).filter(OneTimeProject.is_archived == False)
    if user.tenant_id:
        q = q.filter(OneTimeProject.tenant_id == user.tenant_id)
    if company_id:
        q = q.filter(OneTimeProject.company_id == company_id)
    total = q.count()
    items = q.offset((page-1)*page_size).limit(page_size).all()
    return {"code": 200, "data": {"items": [_serialize_ot(o, db) for o in items],
            "total": total, "page": page, "page_size": page_size}}


@router.post("")
def create_onetime(body: dict, user: User = Depends(require_tenant_user), db: Session = Depends(get_db)):
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


@router.put("/{oid}")
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


@router.put("/{oid}/receive")
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


# ==================== Excel 导入导出 ====================

def _onetime_to_row(o, db):
    company = db.query(Company).filter(Company.id == o.company_id).first()
    supplier = db.query(Supplier).filter(Supplier.id == o.supplier_id).first() if o.supplier_id else None
    owner = db.query(User).filter(User.id == o.owner_id).first()
    return {
        "customer_name": company.name if company else "",
        "project_type": o.project_type,
        "revenue": float(o.revenue), "cost": float(o.cost),
        "supplier_name": supplier.name if supplier else "",
        "owner_name": owner.name if owner else "",
        "completion_date": str(o.completion_date) if o.completion_date else "",
    }


@router.get("/export")
def export_onetime(company_id: int = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(OneTimeProject).filter(OneTimeProject.is_archived == False)
    if user.tenant_id:
        q = q.filter(OneTimeProject.tenant_id == user.tenant_id)
    if company_id:
        q = q.filter(OneTimeProject.company_id == company_id)
    items = q.order_by(OneTimeProject.id.desc()).all()
    rows = [_onetime_to_row(o, db) for o in items]
    xlsx_bytes = export_rows(rows, ONETIME_FIELDS, "一次性业务")
    return StreamingResponse(BytesIO(xlsx_bytes),
                             media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": "attachment; filename=onetime_projects.xlsx"})


@router.get("/template")
def onetime_template(user: User = Depends(get_current_user)):
    sample = {"customer_name": "示例客户", "project_type": "公司注册",
              "revenue": 10000, "cost": 2000, "supplier_name": "",
              "owner_name": "演示员工", "completion_date": "2025-07-15"}
    xlsx_bytes = build_template(ONETIME_FIELDS, "一次性业务", sample)
    return StreamingResponse(BytesIO(xlsx_bytes),
                             media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": "attachment; filename=onetime_template.xlsx"})


@router.post("/import")
async def import_onetime(file: UploadFile = File(...),
                         user: User = Depends(require_write_access),
                         db: Session = Depends(get_db)):
    if not (check_permission(user, "admin:config") or user.role == "tenant_admin"):
        raise HTTPException(403, "权限不足")
    contents = await file.read()
    try:
        rows = parse_import_file(contents, ["客户名称", "业务类型", "收入", "负责人"])
    except ValueError as e:
        raise HTTPException(400, str(e))

    success = updated = created = 0
    errors = []
    for idx, row in enumerate(rows, start=2):
        try:
            cust_name = row.get("客户名称", "").strip()
            ptype = row.get("业务类型", "").strip()
            owner_name = row.get("负责人", "").strip()
            if not cust_name:
                errors.append({"row": idx, "reason": "客户名称为空"}); continue
            if not ptype:
                errors.append({"row": idx, "reason": "业务类型为空"}); continue
            if not owner_name:
                errors.append({"row": idx, "reason": "负责人为空"}); continue

            company_id = _find_company_by_name(db, user.tenant_id, cust_name)
            if not company_id:
                errors.append({"row": idx, "reason": f"客户「{cust_name}」不存在"}); continue
            owner_id = _find_user_by_name(db, user.tenant_id, owner_name)
            if not owner_id:
                errors.append({"row": idx, "reason": f"负责人「{owner_name}」不存在"}); continue
            supplier_name = row.get("供应商", "").strip()
            supplier_id = _find_supplier_by_name(db, user.tenant_id, supplier_name)
            if supplier_name and not supplier_id:
                errors.append({"row": idx, "reason": f"供应商「{supplier_name}」不存在"}); continue

            revenue = Decimal(str(row.get("收入", 0) or 0))
            cost = Decimal(str(row.get("成本", 0) or 0))
            completion_date = parse_date(row.get("完成日"))

            # 唯一键：客户 + 业务类型 + 完成日（同一客户同一类型同一天视为同一业务）
            existing = db.query(OneTimeProject).filter(
                OneTimeProject.company_id == company_id,
                OneTimeProject.project_type == ptype,
                OneTimeProject.is_archived == False)
            if completion_date:
                existing = existing.filter(OneTimeProject.completion_date == completion_date)
            if user.tenant_id:
                existing = existing.filter(OneTimeProject.tenant_id == user.tenant_id)
            existing = existing.first()

            data = {
                "company_id": company_id, "project_type": ptype,
                "revenue": revenue, "cost": cost,
                "supplier_id": supplier_id, "owner_id": owner_id,
                "completion_date": completion_date,
            }
            if existing:
                for k, v in data.items():
                    setattr(existing, k, v)
                # 同步更新关联账单应收金额
                bq = db.query(Bill).filter(Bill.onetime_project_id == existing.id)
                if user.tenant_id:
                    bq = bq.filter(Bill.tenant_id == user.tenant_id)
                bill = bq.first()
                if bill:
                    bill.receivable_amount = revenue - cost
                updated += 1
            else:
                o = OneTimeProject(tenant_id=user.tenant_id, **data)
                db.add(o); db.flush()
                # 同步生成一次性账单（与 create_onetime 保持一致）
                bill_year = completion_date.year if completion_date else date.today().year
                bill_month = completion_date.month if completion_date else date.today().month
                db.add(Bill(tenant_id=user.tenant_id, company_id=company_id,
                            onetime_project_id=o.id, bill_type="onetime",
                            billing_year=bill_year, billing_month=bill_month,
                            receivable_amount=revenue - cost, follow_up_user_id=owner_id))
                created += 1
            success += 1
        except Exception as e:
            errors.append({"row": idx, "reason": str(e)})
    db.commit()
    return {"code": 200, "data": {"success_count": success, "updated_count": updated,
            "created_count": created, "errors": errors}}
