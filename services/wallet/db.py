from sqlalchemy import create_engine

from app.config import DATABASE_URL

# Pool sized so 30+ parallel requests in the Challenge 1 test don't starve
engine = create_engine(DATABASE_URL, pool_size=20, max_overflow=20, pool_pre_ping=True)