from database import engine
from sqlalchemy import inspect

inspector = inspect(engine)
columns = [c['name'] for c in inspector.get_columns('regularizations')]
print("Columns in 'regularizations' table:", columns)

essential_columns = ['reason', 'approval_reason', 'rejection_reason']
for col in essential_columns:
    if col not in columns:
        print(f"Missing column: {col}")
    else:
        print(f"Column exists: {col}")
