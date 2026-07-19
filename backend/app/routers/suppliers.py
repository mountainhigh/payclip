"""供应商管理"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from io import BytesIO
from ..database import get_db
from ..models import User, Supplier
from ..core.auth import (get_current_user, check_permission, require_tenant_user,
                         require_write_access)
from ..utils import export_rows, parse_import_file, build_template

router = APIRouter(prefix="/api/suppliers", tags=["供应商管理"])


SUPPLIER_FIELDS = [
    ("供应商名称", "name"), ("类型", "type"),
    ("联系人", "contact"), ("备注", "remark"),
]


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


# ==================== Excel 导入导出 ====================

def _supplier_to_row(s):
    return {"name": s.name, "type": s.type, "contact": s.contact or "", "remark": s.remark or ""}


@router.get("/export")
def export_suppliers(keyword: str = "", user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(Supplier).filter(Supplier.is_archived == False)
    if user.tenant_id:
        q = q.filter(Supplier.tenant_id == user.tenant_id)
    if keyword:
        q = q.filter(Supplier.name.contains(keyword))
    items = q.order_by(Supplier.id.desc()).all()
    rows = [_supplier_to_row(s) for s in items]
    xlsx_bytes = export_rows(rows, SUPPLIER_FIELDS, "供应商列表")
    return StreamingResponse(BytesIO(xlsx_bytes),
                             media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": "attachment; filename=suppliers.xlsx"})


@router.get("/template")
def supplier_template(user: User = Depends(get_current_user)):
    sample = {"name": "示例供应商", "type": "刻章", "contact": "王师傅 13800000000", "remark": ""}
    xlsx_bytes = build_template(SUPPLIER_FIELDS, "供应商列表", sample)
    return StreamingResponse(BytesIO(xlsx_bytes),
                             media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": "attachment; filename=supplier_template.xlsx"})


@router.post("/import")
async def import_suppliers(file: UploadFile = File(...),
                           user: User = Depends(require_write_access),
                           db: Session = Depends(get_db)):
    if not (check_permission(user, "admin:config") or user.role == "tenant_admin"):
        raise HTTPException(403, "权限不足")
    contents = await file.read()
    try:
        rows = parse_import_file(contents, ["供应商名称"])
    except ValueError as e:
        raise HTTPException(400, str(e))

    success = updated = created = 0
    errors = []
    for idx, row in enumerate(rows, start=2):
        try:
            name = row.get("供应商名称", "").strip()
            if not name:
                errors.append({"row": idx, "reason": "供应商名称为空"})
                continue
            existing = db.query(Supplier).filter(Supplier.name == name, Supplier.is_archived == False)
            if user.tenant_id:
                existing = existing.filter(Supplier.tenant_id == user.tenant_id)
            existing = existing.first()
            data = {
                "name": name,
                "type": row.get("类型", "其他").strip() or "其他",
                "contact": row.get("联系人", "").strip(),
                "remark": row.get("备注", "").strip(),
            }
            if existing:
                for k, v in data.items():
                    setattr(existing, k, v)
                updated += 1
            else:
                db.add(Supplier(tenant_id=user.tenant_id, **data))
                created += 1
            success += 1
        except Exception as e:
            errors.append({"row": idx, "reason": str(e)})
    db.commit()
    return {"code": 200, "data": {"success_count": success, "updated_count": updated,
            "created_count": created, "errors": errors}}
