"""FastAPI 路由模块聚合"""
from .auth import router as auth_router
from .admin import router as admin_router
from .tenant import router as tenant_router
from .users import router as users_router
from .customers import router as customers_router
from .suppliers import router as suppliers_router
from .subscriptions import router as subscriptions_router
from .onetime import router as onetime_router
from .bills import router as bills_router
from .payments import router as payments_router
from .ledger import router as ledger_router
from .salaries import router as salaries_router
from .reports import router as reports_router
from .system import router as system_router

__all__ = [
    "auth_router", "admin_router", "tenant_router", "users_router",
    "customers_router", "suppliers_router", "subscriptions_router",
    "onetime_router", "bills_router", "payments_router", "ledger_router",
    "salaries_router", "reports_router", "system_router",
]
