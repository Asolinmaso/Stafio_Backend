from database import engine
from sqlalchemy import text

with engine.connect() as conn:
    print("Adding missing columns to 'regularizations' table...")
    try:
        conn.execute(text("ALTER TABLE regularizations ADD COLUMN IF NOT EXISTS approval_reason TEXT"))
        conn.execute(text("ALTER TABLE regularizations ADD COLUMN IF NOT EXISTS rejection_reason TEXT"))
        conn.commit()
        print("Columns added successfully!")
    except Exception as e:
        print(f"Error adding columns: {e}")
