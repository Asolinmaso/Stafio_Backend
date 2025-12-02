# -*- coding: utf-8 -*-
"""init_db.py

Initialize PostgreSQL databases and create tables using SQLAlchemy
"""

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import os
from dotenv import load_dotenv
from database import init_db, DB_CONFIG

load_dotenv()

def create_database_if_not_exists(db_config, db_name):
    """Create a PostgreSQL database if it doesn't exist"""
    try:
        # Connect to PostgreSQL server (without specifying a database)
        # Don't pass password for initial connection to default database
        conn = psycopg2.connect(
            host=db_config['host'],
            port=db_config['port'],
            user=db_config['user'],
            password=db_config['password'],
            database='postgres'  # Connect to default postgres database
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Check if database exists
        cursor.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s",
            (db_name,)
        )
        exists = cursor.fetchone()
        
        if not exists:
            print(f"Creating database '{db_name}'...")
            cursor.execute(f'CREATE DATABASE {db_name}')
            print(f"Database '{db_name}' created successfully!")
        else:
            print(f"Database '{db_name}' already exists.")
        
        cursor.close()
        conn.close()
        
    except psycopg2.Error as err:
        print(f"Error creating database '{db_name}': {err}")
        raise

def initialize_database():
    """Initialize both databases and create tables"""
    print("=" * 60)
    print("Initializing PostgreSQL Databases")
    print("=" * 60)
    
    try:
        # Create leave_management_db if it doesn't exist
        print(f"\n1. Checking/Creating database '{DB_CONFIG['database']}'...")
        create_database_if_not_exists(DB_CONFIG, DB_CONFIG['database'])
        
        # Create employee_db if it doesn't exist
       
        
        # Initialize tables for leave_management_db
        print(f"\n3. Creating tables in '{DB_CONFIG['database']}'...")
        init_db()
        print(f"Tables created successfully in '{DB_CONFIG['database']}'!")
        
        # Initialize tables for employee_db
       
       
        
        print("\n" + "=" * 60)
        print("Database initialization completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\nError during initialization: {e}")
        raise

if __name__ == '__main__':
    initialize_database()
