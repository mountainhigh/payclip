from datetime import datetime, timedelta
from jose import jwt, JWTError
import bcrypt
from fastapi import HTTPException, Depends, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from ..config import JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRY
from ..database import get_db

security = HTTPBearer()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode('utf-8'), hashed.encode('utf-8'))


def create_token(user_id: int, permissions: list, data_scope: str,
                 tenant_id: int = None, role: str = "employee") -> str:
    payload = {
        "sub": str(user_id),
        "perms": permissions,
        "scope": data_scope,
        "tenant_id": tenant_id,
        "role": role,
        "exp": datetime.utcnow() + JWT_EXPIRY,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的令牌")


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security),
                     db: Session = Depends(get_db),
                     x_tenant_id: str = Header(None, alias="X-Tenant-Id")):
    payload = decode_token(credentials.credentials)
    user_id = int(payload.get("sub"))
    from ..models import User, Tenant
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已禁用")
    # super_admin 切换租户：若提供 X-Tenant-Id，临时覆盖 user.tenant_id（不写库）
    if user.role == "super_admin" and x_tenant_id:
        try:
            tid = int(x_tenant_id)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="X-Tenant-Id 格式错误")
        tenant = db.query(Tenant).filter(Tenant.id == tid).first()
        if not tenant:
            raise HTTPException(status_code=404, detail="目标租户不存在")
        if tenant.status in ("soft_deleted", "suspended"):
            raise HTTPException(status_code=403, detail=f"目标租户状态异常: {tenant.status}")
        # 关键：先把 user 从 session 中 expunge，避免 SQLAlchemy 跟踪 tenant_id 修改
        # 否则后续接口的 db.commit() 会把 super_admin 的 tenant_id 持久化写库
        db.expunge(user)
        # 临时覆盖（仅本次请求生效），后续所有 if user.tenant_id 过滤将自动生效
        user.tenant_id = tid
    elif user.tenant_id is not None and user.role != "super_admin":
        # 普通用户：检查租户状态
        tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
        if not tenant:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="租户不存在")
        if tenant.status == "soft_deleted":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="账号已归档，续费后可恢复使用")
        if tenant.status == "suspended":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="租户已被暂停")
    return user


def check_permission(user, permission: str) -> bool:
    import json
    perms = json.loads(user.permissions) if isinstance(user.permissions, str) else user.permissions
    return permission in perms or "admin:config" in perms or user.role in ("super_admin", "tenant_admin")


def require_super_admin(user=Depends(get_current_user)):
    """仅平台超级管理员可访问"""
    if user.role != "super_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要平台管理员权限")
    return user


def require_tenant_admin(user=Depends(get_current_user)):
    """租户管理员或平台管理员可访问"""
    if user.role not in ("super_admin", "tenant_admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要租户管理员权限")
    return user


def require_write_access(user=Depends(get_current_user), db: Session = Depends(get_db)):
    """检查租户是否有写权限（非只读降级状态）"""
    if user.role == "super_admin":
        return user
    if user.tenant_id is not None:
        from ..models import Tenant
        tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
        if tenant and tenant.status == "expired_readonly":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="套餐已过期，数据为只读模式，续费后可继续操作")
    return user


def require_tenant_user(user=Depends(get_current_user), db: Session = Depends(get_db)):
    """要求非 super_admin 用户（用于创建租户级数据的接口），同时校验只读降级状态。
    super_admin 在切换租户后（user.tenant_id 已被临时覆盖）也可通过。"""
    if user.role == "super_admin" and user.tenant_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="平台管理员请先选择租户再操作")
    if user.tenant_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="平台管理员请先选择租户再操作")
    from ..models import Tenant
    tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
    if tenant and tenant.status == "expired_readonly":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="套餐已过期，数据为只读模式，续费后可继续操作")
    return user


def get_tenant_id(user) -> int:
    """获取当前用户的租户ID，super_admin 返回 None"""
    return user.tenant_id
