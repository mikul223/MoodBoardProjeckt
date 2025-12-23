from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from pathlib import Path

current_dir = Path(__file__).parent
project_root = current_dir.parent.parent

from dotenv import load_dotenv
load_dotenv(project_root / '.env')

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://moodboard_user:xQ8bN3vC7zM5hJ4kP6tR@postgres:5432/moodboard"
)

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)