import json
from datetime import datetime
from sqlalchemy import (Column, BigInteger, String, Text, Integer, Date, DateTime,
                        DECIMAL as DecimalCol, JSON, Boolean, ForeignKey, CheckConstraint,
                        UniqueConstraint, Index, Computed)
from sqlalchemy.orm import relationship
from ..database import Base


# ==================== 租户模型（v3 新增） ====================

class Tenant(Base):
    """租户 = 使用本SaaS的薪资服务公司本身"""
    __tablename__ = "tenants"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment="租户名称（公司名）")
    plan = Column(String(20), nullable=False, default="trial", comment="套餐：trial/monthly/yearly")
    status = Column(String(20), nullable=False, default="pending_payment",
                    comment="状态：pending_payment/active/expired_readonly/soft_deleted/suspended")
    trial_expires = Column(DateTime, nullable=True, comment="试用到期时间")
    plan_expires = Column(DateTime, nullable=True, comment="套餐到期时间（付费后）")
    max_employees = Column(Integer, nullable=False, default=3, comment="最大员工数")
    contact_phone = Column(String(50), nullable=True, comment="联系人手机号")
    remark = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class RegistrationCode(Base):
    """注册码：super_admin 线下收款后生成，用户凭码注册"""
    __tablename__ = "registration_codes"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    code = Column(String(64), nullable=False, unique=True, index=True, comment="注册码")
    plan = Column(String(20), nullable=False, default="trial", comment="套餐类型")
    duration_days = Column(Integer, nullable=False, default=30, comment="有效天数")
    is_used = Column(Boolean, nullable=False, default=False, index=True)
    used_by_user_id = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    used_by_tenant_id = Column(BigInteger, ForeignKey("tenants.id"), nullable=True)
    created_by = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    used_at = Column(DateTime, nullable=True)
    remark = Column(String(500), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class InvitationLink(Base):
    """员工邀请链接：tenant_admin 生成，员工凭链接自助注册"""
    __tablename__ = "invitation_links"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, ForeignKey("tenants.id"), nullable=False, index=True)
    token = Column(String(128), nullable=False, unique=True, index=True)
    created_by = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    is_used = Column(Boolean, nullable=False, default=False)
    used_by_user_id = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    used_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True, comment="过期时间，NULL=永不过期")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


# ==================== 用户模型（改造） ====================

class User(Base):
    __tablename__ = "users"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, ForeignKey("tenants.id"), nullable=True, index=True,
                       comment="租户ID，super_admin 为 NULL")
    username = Column(String(50), nullable=False, index=True, comment="登录用户名")
    phone = Column(String(20), nullable=True, index=True, comment="手机号")
    password_hash = Column(String(255), nullable=False)
    name = Column(String(50), nullable=False)
    role = Column(String(20), nullable=False, default="employee",
                  comment="角色：super_admin/tenant_admin/employee")
    base_salary = Column(DecimalCol(12, 2), nullable=False, default=0)
    permissions = Column(JSON, nullable=False, default=list)
    data_scope = Column(String(10), nullable=False, default="SELF")
    is_active = Column(Boolean, nullable=False, default=True)
    is_admin = Column(Boolean, nullable=False, default=False, comment="兼容旧逻辑，super_admin=True")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (UniqueConstraint("tenant_id", "username", name="uk_tenant_username"),)

    @property
    def perms_list(self):
        return json.loads(self.permissions) if isinstance(self.permissions, str) else self.permissions

    @property
    def is_super_admin(self):
        return self.role == "super_admin"

    @property
    def is_tenant_admin(self):
        return self.role == "tenant_admin"


# ==================== 业务模型（全部加 tenant_id） ====================

class Company(Base):
    __tablename__ = "companies"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, ForeignKey("tenants.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False, index=True)
    region_tags = Column(JSON, nullable=False, default=list)
    is_new_customer = Column(Boolean, nullable=False, default=False)
    service_start_date = Column(Date, nullable=True)
    status = Column(String(20), nullable=False, default="active")
    introducer_type = Column(String(10), nullable=False, default="external")
    introducer_user_id = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    introducer_name = Column(String(50), nullable=True)
    sales_person_id = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    business_owner_id = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    contact_name = Column(String(50), nullable=True, comment="客户联系人姓名")
    contact_phone = Column(String(50), nullable=True)
    contact_email = Column(String(100), nullable=True)
    remark = Column(Text, nullable=True)
    is_archived = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    introducer = relationship("User", foreign_keys=[introducer_user_id])
    sales_person = relationship("User", foreign_keys=[sales_person_id])
    business_owner = relationship("User", foreign_keys=[business_owner_id])
    subscriptions = relationship("Subscription", back_populates="company", lazy="dynamic")
    onetime_projects = relationship("OneTimeProject", back_populates="company", lazy="dynamic")
    bills = relationship("Bill", back_populates="company", lazy="dynamic")


class Supplier(Base):
    __tablename__ = "suppliers"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, ForeignKey("tenants.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False, index=True)
    type = Column(String(20), nullable=False, index=True)
    contact = Column(String(200), nullable=True)
    remark = Column(Text, nullable=True)
    is_archived = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class Subscription(Base):
    __tablename__ = "subscriptions"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, ForeignKey("tenants.id"), nullable=False, index=True)
    company_id = Column(BigInteger, ForeignKey("companies.id"), nullable=False, index=True)
    service_type = Column(String(50), nullable=False)
    billing_period = Column(String(10), nullable=False)
    monthly_fee = Column(DecimalCol(12, 2), nullable=False)
    is_cost_type = Column(Boolean, nullable=False, default=False)
    monthly_cost = Column(DecimalCol(12, 2), nullable=False, default=0)
    supplier_id = Column(BigInteger, ForeignKey("suppliers.id"), nullable=True)
    service_owner_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    sales_owner_id = Column(BigInteger, ForeignKey("users.id"), nullable=True, index=True)
    start_date = Column(Date, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    is_archived = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    company = relationship("Company", back_populates="subscriptions")
    supplier = relationship("Supplier")
    service_owner = relationship("User", foreign_keys=[service_owner_id])
    sales_owner = relationship("User", foreign_keys=[sales_owner_id])
    fee_histories = relationship("FeeHistory", back_populates="subscription", lazy="dynamic")
    bills = relationship("Bill", back_populates="subscription", lazy="dynamic")


class OneTimeProject(Base):
    __tablename__ = "onetime_projects"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, ForeignKey("tenants.id"), nullable=False, index=True)
    company_id = Column(BigInteger, ForeignKey("companies.id"), nullable=False, index=True)
    project_type = Column(String(50), nullable=False)
    revenue = Column(DecimalCol(12, 2), nullable=False)
    cost = Column(DecimalCol(12, 2), nullable=False, default=0)
    supplier_id = Column(BigInteger, ForeignKey("suppliers.id"), nullable=True)
    owner_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    completion_date = Column(Date, nullable=True, index=True)
    is_received = Column(Boolean, nullable=False, default=False)
    receive_date = Column(Date, nullable=True)
    is_archived = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    company = relationship("Company", back_populates="onetime_projects")
    supplier = relationship("Supplier")
    owner = relationship("User")
    bill = relationship("Bill", back_populates="onetime_project", uselist=False)


class FeeHistory(Base):
    __tablename__ = "fee_histories"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, ForeignKey("tenants.id"), nullable=False, index=True)
    subscription_id = Column(BigInteger, ForeignKey("subscriptions.id"), nullable=False, index=True)
    old_fee = Column(DecimalCol(12, 2), nullable=False)
    new_fee = Column(DecimalCol(12, 2), nullable=False)
    effective_date = Column(Date, nullable=False, index=True)
    changed_by = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    subscription = relationship("Subscription", back_populates="fee_histories")
    changer = relationship("User")


class Bill(Base):
    __tablename__ = "bills"
    __table_args__ = (UniqueConstraint("tenant_id", "subscription_id", "billing_year", "billing_month", name="uk_tenant_sub_month"),
                      UniqueConstraint("tenant_id", "onetime_project_id", "billing_year", "billing_month", name="uk_tenant_ot_month"),)
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, ForeignKey("tenants.id"), nullable=False, index=True)
    company_id = Column(BigInteger, ForeignKey("companies.id"), nullable=False, index=True)
    subscription_id = Column(BigInteger, ForeignKey("subscriptions.id"), nullable=True)
    onetime_project_id = Column(BigInteger, ForeignKey("onetime_projects.id"), nullable=True)
    bill_type = Column(String(20), nullable=False)
    billing_year = Column(Integer, nullable=False, index=True)
    billing_month = Column(Integer, nullable=False, index=True)
    receivable_amount = Column(DecimalCol(12, 2), nullable=False)
    paid_amount = Column(DecimalCol(12, 2), nullable=False, default=0)
    payment_status = Column(String(10), nullable=False, default="unpaid", index=True)
    is_overdue = Column(Boolean, nullable=False, default=False)
    follow_up_user_id = Column(BigInteger, ForeignKey("users.id"), nullable=True, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    company = relationship("Company", back_populates="bills")
    subscription = relationship("Subscription", back_populates="bills")
    onetime_project = relationship("OneTimeProject", back_populates="bill")
    follow_up_user = relationship("User", foreign_keys=[follow_up_user_id])
    allocations = relationship("PaymentBillAllocation", back_populates="bill", lazy="dynamic")


class PaymentRecord(Base):
    __tablename__ = "payment_records"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, ForeignKey("tenants.id"), nullable=False, index=True)
    company_id = Column(BigInteger, ForeignKey("companies.id"), nullable=False, index=True)
    amount = Column(DecimalCol(12, 2), nullable=False)
    payment_date = Column(Date, nullable=False, index=True)
    channel = Column(String(20), nullable=False)
    submitter_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    assigned_verifier_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    verify_status = Column(String(10), nullable=False, default="pending", index=True)
    reject_reason = Column(String(500), nullable=True)
    usage_type = Column(String(10), nullable=False, default="public", index=True)
    remark = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (CheckConstraint("amount > 0", name="chk_amount"),)

    company = relationship("Company")
    submitter = relationship("User", foreign_keys=[submitter_id])
    verifier = relationship("User", foreign_keys=[assigned_verifier_id])
    allocations = relationship("PaymentBillAllocation", back_populates="payment_record", cascade="all, delete-orphan")
    screenshots = relationship("PaymentScreenshot", back_populates="payment_record", cascade="all, delete-orphan")


class PaymentBillAllocation(Base):
    __tablename__ = "payment_bill_allocations"
    __table_args__ = (CheckConstraint("allocation_amount > 0", name="chk_allocation"),)
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, ForeignKey("tenants.id"), nullable=False, index=True)
    payment_record_id = Column(BigInteger, ForeignKey("payment_records.id", ondelete="CASCADE"), nullable=False, index=True)
    bill_id = Column(BigInteger, ForeignKey("bills.id"), nullable=False, index=True)
    allocation_amount = Column(DecimalCol(12, 2), nullable=False)
    source = Column(String(20), nullable=False, default="payment")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    payment_record = relationship("PaymentRecord", back_populates="allocations")
    bill = relationship("Bill", back_populates="allocations")


class PaymentScreenshot(Base):
    __tablename__ = "payment_screenshots"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, ForeignKey("tenants.id"), nullable=False, index=True)
    payment_record_id = Column(BigInteger, ForeignKey("payment_records.id", ondelete="CASCADE"), nullable=False, index=True)
    file_path = Column(String(500), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    payment_record = relationship("PaymentRecord", back_populates="screenshots")


class CustomerPrepayment(Base):
    __tablename__ = "customer_prepayments"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, ForeignKey("tenants.id"), nullable=False, index=True)
    company_id = Column(BigInteger, ForeignKey("companies.id"), nullable=False, index=True)
    balance = Column(DecimalCol(12, 2), nullable=False, default=0)
    source = Column(String(20), nullable=False, default="overpayment")
    remark = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class PrepaymentLog(Base):
    """预付款变动明细：每次余额变动都记录一条流水"""
    __tablename__ = "prepayment_logs"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, ForeignKey("tenants.id"), nullable=False, index=True)
    company_id = Column(BigInteger, ForeignKey("companies.id"), nullable=False, index=True)
    change_type = Column(String(20), nullable=False, comment="变动类型：in增加/out扣减")
    amount = Column(DecimalCol(12, 2), nullable=False, comment="变动金额（正数）")
    balance_after = Column(DecimalCol(12, 2), nullable=False, comment="变动后余额")
    source = Column(String(30), nullable=False, default="overpayment",
                    comment="来源：overpayment/payment/prepayment_use/manual")
    payment_record_id = Column(BigInteger, ForeignKey("payment_records.id"), nullable=True, index=True)
    bill_id = Column(BigInteger, ForeignKey("bills.id"), nullable=True, index=True)
    operator_id = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    remark = Column(String(500), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)


class CommissionDetail(Base):
    __tablename__ = "commission_details"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, ForeignKey("tenants.id"), nullable=False, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    commission_type = Column(String(10), nullable=False)
    bill_id = Column(BigInteger, ForeignKey("bills.id"), nullable=True, index=True)
    payment_record_id = Column(BigInteger, ForeignKey("payment_records.id"), nullable=True)
    company_id = Column(BigInteger, ForeignKey("companies.id"), nullable=False, index=True)
    subscription_id = Column(BigInteger, ForeignKey("subscriptions.id"), nullable=True)
    onetime_project_id = Column(BigInteger, ForeignKey("onetime_projects.id"), nullable=True)
    billing_year = Column(Integer, nullable=False, index=True)
    billing_month = Column(Integer, nullable=False, index=True)
    base_amount = Column(DecimalCol(12, 2), nullable=False)
    rate = Column(DecimalCol(5, 4), nullable=False)
    commission_amount = Column(DecimalCol(12, 2), nullable=False)
    deduction_amount = Column(DecimalCol(12, 2), nullable=False, default=0)
    supplement_amount = Column(DecimalCol(12, 2), nullable=False, default=0)
    net_amount = Column(DecimalCol(12, 2), nullable=False)
    is_supplement = Column(Boolean, nullable=False, default=False)
    supplement_for_user_id = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    ledger_validation_id = Column(BigInteger, ForeignKey("ledger_validations.id"), nullable=True, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    Index("idx_user_month", "user_id", "billing_year", "billing_month")

    user = relationship("User", foreign_keys=[user_id])
    bill = relationship("Bill")
    company = relationship("Company")


class MonthlySalary(Base):
    __tablename__ = "monthly_salaries"
    __table_args__ = (UniqueConstraint("tenant_id", "user_id", "salary_year", "salary_month", name="uk_tenant_user_month"),)
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, ForeignKey("tenants.id"), nullable=False, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    salary_year = Column(Integer, nullable=False, index=True)
    salary_month = Column(Integer, nullable=False, index=True)
    base_salary = Column(DecimalCol(12, 2), nullable=False)
    service_commission = Column(DecimalCol(12, 2), nullable=False, default=0)
    sales_commission = Column(DecimalCol(12, 2), nullable=False, default=0)
    onetime_commission = Column(DecimalCol(12, 2), nullable=False, default=0)
    total_deduction = Column(DecimalCol(12, 2), nullable=False, default=0)
    total_supplement = Column(DecimalCol(12, 2), nullable=False, default=0)
    bonus_amount = Column(DecimalCol(12, 2), nullable=False, default=0)
    gross_payable = Column(DecimalCol(12, 2), nullable=False)
    year_end_bonus = Column(DecimalCol(12, 2), nullable=False, default=0)
    tax_amount = Column(DecimalCol(12, 2), nullable=False, default=0)
    social_insurance = Column(DecimalCol(12, 2), nullable=False, default=0)
    housing_fund = Column(DecimalCol(12, 2), nullable=False, default=0)
    ledger_validation_id = Column(BigInteger, ForeignKey("ledger_validations.id"), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    user = relationship("User")


class LedgerValidation(Base):
    __tablename__ = "ledger_validations"
    __table_args__ = (UniqueConstraint("tenant_id", "ledger_year", "ledger_month", name="uk_tenant_year_month"),)
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, ForeignKey("tenants.id"), nullable=False, index=True)
    ledger_year = Column(Integer, nullable=False)
    ledger_month = Column(Integer, nullable=False)
    status = Column(String(15), nullable=False, default="unlocked", index=True)
    locked_by = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    locked_at = Column(DateTime, nullable=True)
    unlocked_by = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    unlocked_at = Column(DateTime, nullable=True)
    calculation_status = Column(String(15), nullable=False, default="idle")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class CostPreset(Base):
    __tablename__ = "cost_presets"
    __table_args__ = (UniqueConstraint("tenant_id", "business_type", name="uk_tenant_biz_type"),)
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, ForeignKey("tenants.id"), nullable=False, index=True)
    business_type = Column(String(50), nullable=False)
    default_cost = Column(DecimalCol(12, 2), nullable=False)
    supplier_id = Column(BigInteger, ForeignKey("suppliers.id"), nullable=True, index=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class BonusTier(Base):
    __tablename__ = "bonus_tiers"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, ForeignKey("tenants.id"), nullable=False, index=True)
    tier_name = Column(String(50), nullable=False)
    min_amount = Column(DecimalCol(12, 2), nullable=False)
    max_amount = Column(DecimalCol(12, 2), nullable=True)
    bonus_rate = Column(DecimalCol(5, 4), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    sort_order = Column(Integer, nullable=False, default=0, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class SubscriptionOwnerHistory(Base):
    __tablename__ = "subscription_owner_histories"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, ForeignKey("tenants.id"), nullable=False, index=True)
    subscription_id = Column(BigInteger, ForeignKey("subscriptions.id"), nullable=False, index=True)
    change_type = Column(String(20), nullable=False, index=True)
    old_user_id = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    new_user_id = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    effective_date = Column(Date, nullable=False, index=True)
    changed_by = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    remark = Column(String(500), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class OnetimeOwnerHistory(Base):
    __tablename__ = "onetime_owner_histories"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, ForeignKey("tenants.id"), nullable=False, index=True)
    onetime_project_id = Column(BigInteger, ForeignKey("onetime_projects.id"), nullable=False, index=True)
    old_user_id = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    new_user_id = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    effective_date = Column(Date, nullable=False, index=True)
    changed_by = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    remark = Column(String(500), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class BillFollowUpHistory(Base):
    __tablename__ = "bill_follow_up_histories"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, ForeignKey("tenants.id"), nullable=False, index=True)
    bill_id = Column(BigInteger, ForeignKey("bills.id"), nullable=False, index=True)
    old_user_id = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    new_user_id = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    effective_date = Column(Date, nullable=False, index=True)
    changed_by = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    remark = Column(String(500), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class PaymentChannel(Base):
    """收款渠道配置：在系统设置里维护，供收款填报时选择"""
    __tablename__ = "payment_channels"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, ForeignKey("tenants.id"), nullable=False, index=True)
    name = Column(String(50), nullable=False, comment="渠道名称，如：银行转账")
    code = Column(String(30), nullable=False, comment="渠道代码，如：bank")
    payee_name = Column(String(80), nullable=True, comment="收款人姓名")
    account_number = Column(String(100), nullable=True, comment="收款账号")
    account_type = Column(String(30), nullable=True, comment="账号类型：储蓄/对公/支付宝/微信等")
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    sort_order = Column(Integer, nullable=False, default=0, index=True)
    remark = Column(String(500), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uk_tenant_channel_code"),)


class ServiceType(Base):
    """服务类型配置：在系统设置里维护，供长期业务选择服务类型"""
    __tablename__ = "service_types"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, ForeignKey("tenants.id"), nullable=False, index=True)
    name = Column(String(50), nullable=False, comment="服务类型名称，如：代理记账")
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    sort_order = Column(Integer, nullable=False, default=0, index=True)
    remark = Column(String(500), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uk_tenant_service_type_name"),)
