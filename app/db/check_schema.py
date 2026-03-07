from sqlalchemy import create_engine, text, inspect
import os
from dotenv import load_dotenv

load_dotenv()

# Database credentials (from env)
hostname = os.getenv("DB_HOST", "localhost")
database = os.getenv("DB_NAME", "occashare")
username = os.getenv("DB_USER", "postgres")
pwd = os.getenv("DB_PASSWORD", "1425")
port_id = os.getenv("DB_PORT", "5432")

SQLALCHEMY_DATABASE_URL = f"postgresql://{username}:{pwd}@{hostname}:{port_id}/{database}"
engine = create_engine(SQLALCHEMY_DATABASE_URL)

def check_schema():
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"Tables in database: {tables}")
    
    if "bookings" in tables:
        columns = [c["name"] for c in inspector.get_columns("bookings")]
        print(f"Columns in 'bookings': {columns}")
        if "payout_id" in columns:
            print("SUCCESS: 'payout_id' exists in 'bookings'.")
        else:
            print("MISSING: 'payout_id' is missing from 'bookings'.")
    else:
        print("MISSING: 'bookings' table does not exist.")

    for table in ["payouts", "payout_items"]:
        if table in tables:
            print(f"SUCCESS: '{table}' table exists.")
        else:
            print(f"MISSING: '{table}' table is missing.")

if __name__ == "__main__":
    check_schema()
