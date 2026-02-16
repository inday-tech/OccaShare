from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Database credentials
hostname = "localhost"
database = "occashare"
username = "postgres"
pwd = "1425"
port_id = 5432

SQLALCHEMY_DATABASE_URL = f"postgresql://{username}:{pwd}@{hostname}:{port_id}/{database}"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
