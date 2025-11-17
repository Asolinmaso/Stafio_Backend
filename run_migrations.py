#!/usr/bin/env python3
"""
Script to run Alembic migrations automatically
This will be called when the application starts
"""
import os
import sys
from alembic.config import Config
from alembic import command
from dotenv import load_dotenv

load_dotenv()

def run_migrations():
    """Run Alembic migrations"""
    alembic_cfg = Config(os.path.join(os.path.dirname(__file__), "alembic.ini"))
    
    print("Running database migrations...")
    try:
        # Upgrade to head (latest migration)
        command.upgrade(alembic_cfg, "head")
        print("Migrations completed successfully!")
    except Exception as e:
        print(f"Error running migrations: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_migrations()

