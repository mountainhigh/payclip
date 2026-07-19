"""数据库现状检查脚本"""
import sys
sys.path.insert(0, "e:/code/ai_code/payclip/backend")
from app.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    tables = [r[0] for r in conn.execute(text("SHOW TABLES")).fetchall()]
    print("=== 所有表 ===")
    for t in tables:
        print(t)
    print("\n=== 各表数据量 ===")
    for t in tables:
        cnt = conn.execute(text(f"SELECT COUNT(*) FROM `{t}`")).scalar()
        print(f"{t}: {cnt}")
    print("\n=== 现有租户 ===")
    for r in conn.execute(text("SELECT id, name, plan, status FROM tenants")).fetchall():
        print(r)
    print("\n=== 现有用户 ===")
    for r in conn.execute(text("SELECT id, tenant_id, username, name, role FROM users")).fetchall():
        print(r)
    print("\n=== 现有客户 ===")
    for r in conn.execute(text("SELECT id, tenant_id, name, is_archived FROM companies")).fetchall():
        print(r)
