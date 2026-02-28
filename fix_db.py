
import psycopg2
import os
from dotenv import load_dotenv

# Load database configuration
load_dotenv()

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'root'),
    'database': os.getenv('DB_NAME', 'leave_management_db')
}

def fix_db():
    conn = None
    try:
        # Connect to the database
        conn = psycopg2.connect(
            host=DB_CONFIG['host'],
            port=DB_CONFIG['port'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            database=DB_CONFIG['database']
        )
        conn.autocommit = True
        cursor = conn.cursor()

        print("Checking leave_types table...")
        
        # Check if created_at exists in leave_types
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='leave_types' AND column_name='created_at';
        """)
        if not cursor.fetchone():
            print("Adding created_at column to leave_types...")
            cursor.execute("ALTER TABLE leave_types ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;")
        
        # Check if type exists in leave_types
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='leave_types' AND column_name='type';
        """)
        if not cursor.fetchone():
            print("Adding type column to leave_types...")
            cursor.execute("ALTER TABLE leave_types ADD COLUMN type VARCHAR(20) DEFAULT 'All';")

        print("Checking leave_requests table...")
        
        # Check for approval_reason and rejection_reason in leave_requests
        for col in ['approval_reason', 'rejection_reason']:
            cursor.execute(f"""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='leave_requests' AND column_name='{col}';
            """)
            if not cursor.fetchone():
                print(f"Adding {col} column to leave_requests...")
                cursor.execute(f"ALTER TABLE leave_requests ADD COLUMN {col} TEXT;")

        print("Database fix completed successfully!")
        
        cursor.close()
    except Exception as e:
        print(f"Error fixing database: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    fix_db()
