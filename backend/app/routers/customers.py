"""客户管理"""
import json
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from io import BytesIO
from ..database import get_db
from ..models import User, Company, Bill, Subscription, OneTimeProject, Supplier
from ..core.auth import (get_current_user, check_permission, require_tenant_user,
                         require_write_access)
from ..utils import parse_date, export_rows, parse_import_file, build_template

router = APIRouter(prefix="/api/customers", tags=["客户管理"])


# Excel 字段映射：(Excel 表头, 字典 key)
CUSTOMER_FIELDS = [
    ("客户名称", "name"), ("状态", "status"), ("新客户", "is_new_customer"),
    ("服务起始", "service_start_date"), ("区域标签", "region_tags"),
    ("介绍人类型", "introducer_type"), ("介绍人名称", "introducer_name"),
    ("销售负责人", "sales_person_name"), ("联系人姓名", "contact_name"),
    ("联系电话", "contact_phone"), ("邮箱", "contact_email"), ("备注", "remark"),
]


def _find_user_by_name(db, tenant_id, name):
    """按名称查用户，返回 user_id 或 None"""
    if not name:
        return None
    q = db.query(User).filter(User.name == name, User.is_active == True)
    if tenant_id:
        q = q.filter(User.tenant_id == tenant_id)
    u = q.first()
    return u.id if u else None


def _calc_is_new_customer(service_start_date):
    """根据服务开始时间判断是否为新客户：≤1年为新客户"""
    from datetime import date, timedelta
    if not service_start_date:
        return False
    try:
        sd = service_start_date if isinstance(service_start_date, date) else date.fromisoformat(str(service_start_date))
    except (ValueError, TypeError):
        return False
    return (date.today() - sd).days <= 365


def _serialize_company(c, db=None):
    sales_name = None
    business_owner_name = None
    if db is not None:
        if c.sales_person_id:
            u = db.query(User).filter(User.id == c.sales_person_id).first()
            sales_name = u.name if u else None
        if c.business_owner_id:
            u = db.query(User).filter(User.id == c.business_owner_id).first()
            business_owner_name = u.name if u else None
    return {"id": c.id, "name": c.name,
            "region_tags": json.loads(c.region_tags) if isinstance(c.region_tags, str) else c.region_tags,
            "is_new_customer": _calc_is_new_customer(c.service_start_date),
            "service_start_date": str(c.service_start_date) if c.service_start_date else None,
            "status": c.status, "introducer_type": c.introducer_type,
            "introducer_user_id": c.introducer_user_id, "introducer_name": c.introducer_name,
            "sales_person_id": c.sales_person_id, "sales_person_name": sales_name,
            "business_owner_id": c.business_owner_id, "business_owner_name": business_owner_name,
            "contact_name": c.contact_name,
            "contact_phone": c.contact_phone,
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
    return {"code": 200, "data": {"items": [_serialize_company(c, db) for c in items],
            "total": total, "page": page, "page_size": page_size}}


# ==================== Excel 导入导出（必须在 /{cid} 之前注册，避免被动态路径拦截） ====================

def _customer_to_row(c, db):
    """把 Company 模型转为导出字典（含销售负责人名称）"""
    sales_name = ""
    if c.sales_person_id:
        u = db.query(User).filter(User.id == c.sales_person_id).first()
        sales_name = u.name if u else ""
    tags = json.loads(c.region_tags) if isinstance(c.region_tags, str) else (c.region_tags or [])
    return {
        "name": c.name, "status": c.status,
        "is_new_customer": "是" if _calc_is_new_customer(c.service_start_date) else "否",
        "service_start_date": str(c.service_start_date) if c.service_start_date else "",
        "region_tags": ";".join(tags),
        "introducer_type": c.introducer_type, "introducer_name": c.introducer_name or "",
        "sales_person_name": sales_name,
        "contact_name": c.contact_name or "",
        "contact_phone": c.contact_phone or "", "contact_email": c.contact_email or "",
        "remark": c.remark or "",
    }


@router.get("/export")
def export_customers(keyword: str = "", mode: str = "simple",
                     user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """导出客户列表为 Excel
    mode=simple 仅客户清单；mode=with_business 含客户的长期+一次性业务清单（多 sheet）
    """
    q = db.query(Company).filter(Company.is_archived == False)
    if user.tenant_id:
        q = q.filter(Company.tenant_id == user.tenant_id)
    if keyword:
        q = q.filter(Company.name.contains(keyword))
    items = q.order_by(Company.id.desc()).all()
    rows = [_customer_to_row(c, db) for c in items]

    if mode == "with_business":
        # 导出含业务清单：在同一个 Excel 文件中输出多 sheet（客户/长期业务/一次性业务）
        from ..utils.excel import build_multi_sheet_workbook
        # 长期业务
        sub_rows = []
        for c in items:
            sq = db.query(Subscription).filter(Subscription.company_id == c.id,
                                                Subscription.is_archived == False)
            if user.tenant_id:
                sq = sq.filter(Subscription.tenant_id == user.tenant_id)
            for s in sq.all():
                owner = db.query(User).filter(User.id == s.service_owner_id).first()
                sales = db.query(User).filter(User.id == s.sales_owner_id).first() if s.sales_owner_id else None
                sub_rows.append({
                    "customer_name": c.name,
                    "service_type": s.service_type,
                    "billing_period": s.billing_period,
                    "monthly_fee": float(s.monthly_fee),
                    "is_active": "启用" if s.is_active else "停用",
                    "service_owner_name": owner.name if owner else "",
                    "sales_owner_name": sales.name if sales else "",
                    "start_date": str(s.start_date) if s.start_date else "",
                })
        SUB_FIELDS = [
            ("客户名称", "customer_name"), ("服务类型", "service_type"),
            ("计费周期", "billing_period"), ("费用", "monthly_fee"),
            ("状态", "is_active"), ("服务负责人", "service_owner_name"),
            ("销售负责人", "sales_owner_name"), ("开始日期", "start_date"),
        ]
        # 一次性业务
        ot_rows = []
        for c in items:
            oq = db.query(OneTimeProject).filter(OneTimeProject.company_id == c.id,
                                                  OneTimeProject.is_archived == False)
            if user.tenant_id:
                oq = oq.filter(OneTimeProject.tenant_id == user.tenant_id)
            for o in oq.all():
                owner = db.query(User).filter(User.id == o.owner_id).first()
                ot_rows.append({
                    "customer_name": c.name,
                    "project_type": o.project_type,
                    "revenue": float(o.revenue),
                    "cost": float(o.cost),
                    "gross_profit": float(o.revenue - o.cost),
                    "owner_name": owner.name if owner else "",
                    "completion_date": str(o.completion_date) if o.completion_date else "",
                    "is_received": "已收" if o.is_received else "未收",
                })
        OT_FIELDS = [
            ("客户名称", "customer_name"), ("业务类型", "project_type"),
            ("收入", "revenue"), ("成本", "cost"), ("毛利", "gross_profit"),
            ("负责人", "owner_name"), ("完成日", "completion_date"),
            ("收款状态", "is_received"),
        ]
        xlsx_bytes = build_multi_sheet_workbook([
            ("客户列表", CUSTOMER_FIELDS, rows),
            ("长期业务", SUB_FIELDS, sub_rows),
            ("一次性业务", OT_FIELDS, ot_rows),
        ])
        fname = "customers_with_business.xlsx"
    else:
        xlsx_bytes = export_rows(rows, CUSTOMER_FIELDS, sheet_name="客户列表")
        fname = "customers.xlsx"

    return StreamingResponse(BytesIO(xlsx_bytes),
                             media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f"attachment; filename={fname}"})


@router.get("/template")
def customer_template(user: User = Depends(get_current_user)):
    """下载客户导入模板"""
    sample = {"name": "示例客户", "status": "active", "is_new_customer": "是",
              "service_start_date": "2025-01-01", "region_tags": "广州;天河区",
              "introducer_type": "external", "introducer_name": "",
              "sales_person_name": "演示员工", "contact_name": "张三",
              "contact_phone": "13800000000",
              "contact_email": "", "remark": ""}
    xlsx_bytes = build_template(CUSTOMER_FIELDS, "客户列表", sample)
    return StreamingResponse(BytesIO(xlsx_bytes),
                             media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": "attachment; filename=customer_template.xlsx"})


@router.get("/{cid}")
def get_customer(cid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(Company).filter(Company.id == cid, Company.is_archived == False)
    if user.tenant_id:
        q = q.filter(Company.tenant_id == user.tenant_id)
    c = q.first()
    if not c:
        raise HTTPException(404, "客户不存在")
    return {"code": 200, "data": _serialize_company(c, db)}


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
                business_owner_id=body.get("business_owner_id"),
                contact_name=body.get("contact_name"),
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
    for f in ["name","status","introducer_type","introducer_name","contact_name","contact_phone","contact_email","remark"]:
        if f in body: setattr(c, f, body[f])
    if "region_tags" in body: c.region_tags = json.dumps(body["region_tags"])
    if "service_start_date" in body: c.service_start_date = parse_date(body["service_start_date"])
    if "is_new_customer" in body: c.is_new_customer = body["is_new_customer"]
    if "sales_person_id" in body: c.sales_person_id = body["sales_person_id"]
    if "business_owner_id" in body: c.business_owner_id = body["business_owner_id"]
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


@router.post("/import")
async def import_customers(file: UploadFile = File(...),
                           user: User = Depends(require_write_access),
                           db: Session = Depends(get_db)):
    """批量导入客户（按名称匹配，已存在则更新）"""
    if not (check_permission(user, "admin:config") or user.role == "tenant_admin"):
        raise HTTPException(403, "权限不足")
    contents = await file.read()
    try:
        rows = parse_import_file(contents, ["客户名称"])
    except ValueError as e:
        raise HTTPException(400, str(e))

    success = updated = created = 0
    errors = []
    for idx, row in enumerate(rows, start=2):
        try:
            name = row.get("客户名称", "").strip()
            if not name:
                errors.append({"row": idx, "reason": "客户名称为空"})
                continue
            existing = db.query(Company).filter(Company.name == name, Company.is_archived == False)
            if user.tenant_id:
                existing = existing.filter(Company.tenant_id == user.tenant_id)
            existing = existing.first()

            sales_name = row.get("销售负责人", "").strip()
            sales_id = _find_user_by_name(db, user.tenant_id, sales_name)
            if sales_name and not sales_id:
                errors.append({"row": idx, "reason": f"销售负责人「{sales_name}」不存在"})
                continue

            tags = [t.strip() for t in row.get("区域标签", "").split(";") if t.strip()]
            data = {
                "name": name,
                "status": row.get("状态", "active").strip() or "active",
                "is_new_customer": row.get("新客户", "否").strip() in ("是", "true", "True", "1"),
                "service_start_date": parse_date(row.get("服务起始")) or parse_date(row.get("合作起始")),
                "region_tags": json.dumps(tags),
                "introducer_type": row.get("介绍人类型", "external").strip() or "external",
                "introducer_name": row.get("介绍人名称", "").strip(),
                "sales_person_id": sales_id,
                "contact_name": row.get("联系人姓名", "").strip(),
                "contact_phone": row.get("联系电话", "").strip(),
                "contact_email": row.get("邮箱", "").strip(),
                "remark": row.get("备注", "").strip(),
            }
            if existing:
                for k, v in data.items():
                    setattr(existing, k, v)
                updated += 1
            else:
                c = Company(tenant_id=user.tenant_id, **data)
                db.add(c)
                created += 1
            success += 1
        except Exception as e:
            errors.append({"row": idx, "reason": str(e)})
    db.commit()
    return {"code": 200, "data": {"success_count": success, "updated_count": updated,
            "created_count": created, "errors": errors}}
