"""薪资管理：列表 + 明细"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import MonthlySalary, User, CommissionDetail, Company
from ..core.auth import get_current_user

router = APIRouter(prefix="/api/salaries", tags=["薪资管理"])


@router.get("")
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
                       "salary_year": ms.salary_year, "salary_month": ms.salary_month,
                       "base_salary": float(ms.base_salary),
                       "service_commission": float(ms.service_commission),
                       "sales_commission": float(ms.sales_commission),
                       "onetime_commission": float(ms.onetime_commission),
                       "total_deduction": float(ms.total_deduction),
                       "total_supplement": float(ms.total_supplement),
                       "gross_payable": float(ms.gross_payable)})
    return {"code": 200, "data": {"items": result, "total": total, "page": page, "page_size": page_size}}


@router.get("/{uid}/{year}/{month}")
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
    # 预加载所有相关公司名，避免 N+1 查询
    company_ids = {d.company_id for d in details if d.company_id}
    company_map = {}
    if company_ids:
        for c in db.query(Company).filter(Company.id.in_(company_ids)).all():
            company_map[c.id] = c.name
    return {"code": 200, "data": {"user_id": ms.user_id, "user_name": ms.user.name if ms.user else "",
            "salary_year": ms.salary_year, "salary_month": ms.salary_month,
            "base_salary": float(ms.base_salary),
            "service_commission": float(ms.service_commission),
            "sales_commission": float(ms.sales_commission),
            "onetime_commission": float(ms.onetime_commission),
            "total_deduction": float(ms.total_deduction),
            "total_supplement": float(ms.total_supplement),
            "gross_payable": float(ms.gross_payable),
            "bonus_amount": float(getattr(ms, "bonus_amount", 0) or 0),
            "year_end_bonus": float(getattr(ms, "year_end_bonus", 0) or 0),
            "commission_details": [{"id": d.id, "type": d.commission_type, "company_id": d.company_id,
             "company_name": company_map.get(d.company_id, "") if d.company_id else "",
             "base_amount": float(d.base_amount), "rate": float(d.rate),
             "commission_amount": float(d.commission_amount),
             "deduction_amount": float(d.deduction_amount),
             "supplement_amount": float(d.supplement_amount),
             "net_amount": float(d.net_amount), "is_supplement": d.is_supplement} for d in details]}}
