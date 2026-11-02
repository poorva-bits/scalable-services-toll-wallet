from sqlalchemy import create_engine

from app.config import DATABASE_URL

# Pooled engine shared by the whole service
engine = create_engine(DATABASE_URL, pool_size=20, max_overflow=20, pool_pre_ping=True)