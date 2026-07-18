import os
from datetime import timedelta

DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://salary:salary123@localhost:3306/salary_manager")
JWT_SECRET = os.getenv("JWT_SECRET", "salary-manager-dev-secret-key")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY = timedelta(hours=24)
UPLOAD_DIR = os.getenv("UPLOAD_DIR", os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "uploads"))
MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5MB
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png"}
