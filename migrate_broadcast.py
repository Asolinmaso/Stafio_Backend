
import psycopg2
import os
from dotenv import load_dotenv

def migrate():
    load_dotenv()
    
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        port=os.getenv('DB_PORT', '5432'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', 'root'),
        database=os.getenv('DB_NAME', 'leave_management_db')
    )
    conn.autocommit = True
    cursor = conn.cursor()
    
    print("Migrating 'broadcasts' table...")
    
    columns_to_add = [
        ("event_date", "DATE"),
        ("event_name", "VARCHAR(200)"),
        ("event_time", "VARCHAR(50)"),
        ("event_type", "VARCHAR(50)"),
        ("image_url", "VARCHAR(500)"),
        ("mentioned_employee_id", "INTEGER"),
        ("author_name", "VARCHAR(100)"),
        ("author_email", "VARCHAR(100)"),
        ("author_designation", "VARCHAR(100)"),
        ("reactions_count", "INTEGER DEFAULT 0")
    ]
    
    for col_name, col_type in columns_to_add:
        try:
            cursor.execute(f"ALTER TABLE broadcasts ADD COLUMN {col_name} {col_type}")
            print(f"Added column: {col_name}")
        except psycopg2.Error as e:
            if "already exists" in str(e):
                print(f"Column {col_name} already exists.")
            else:
                print(f"Error adding {col_name}: {e}")
    
    # Also add constraints for mentioned_employee_id
    try:
        cursor.execute("ALTER TABLE broadcasts ADD CONSTRAINT fk_mentioned_employee FOREIGN KEY (mentioned_employee_id) REFERENCES users(id) ON DELETE SET NULL")
        print("Added foreign key constraint for mentioned_employee_id")
    except Exception as e:
        print(f"Note: {e}")

    # Create the broadcast_reactions table if not exists
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS broadcast_reactions (
                id SERIAL PRIMARY KEY,
                broadcast_id INTEGER REFERENCES broadcasts(id) ON DELETE CASCADE,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                reaction_type VARCHAR(20) DEFAULT 'like',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("Created broadcast_reactions table")
    except Exception as e:
        print(f"Error creating broadcast_reactions table: {e}")

    cursor.close()
    conn.close()
    print("Migration completed!")

if __name__ == "__main__":
    migrate()
