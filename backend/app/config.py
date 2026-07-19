import os
from datetime import timedelta
from dotenv import load_dotenv

# 从 backend/.env 加载环境变量（文件不存在时静默跳过；不覆盖已存在的环境变量）
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://salary:salary123@localhost:3306/salary_manager?charset=utf8mb4")
JWT_SECRET = os.getenv("JWT_SECRET", "salary-manager-dev-secret-key")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY = timedelta(hours=24)
UPLOAD_DIR = os.getenv("UPLOAD_DIR", os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "uploads"))
MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5MB
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png"}
