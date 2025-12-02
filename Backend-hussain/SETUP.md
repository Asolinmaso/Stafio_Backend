# Setup Guide for Stafio Backend

This guide will help you set up the PostgreSQL database and run the backend applications with auto-migration support.

## Prerequisites

1. **PostgreSQL** installed and running on your system
2. **Python 3.8+** installed
3. **pip** (Python package manager)

## Step 1: Install PostgreSQL

If you don't have PostgreSQL installed:

- **macOS**: `brew install postgresql@14` (or latest version)
- **Linux**: `sudo apt-get install postgresql` (Ubuntu/Debian) or `sudo yum install postgresql` (CentOS/RHEL)
- **Windows**: Download from https://www.postgresql.org/download/windows/

Start PostgreSQL service:

- **macOS**: `brew services start postgresql@14`
- **Linux**: `sudo systemctl start postgresql`
- **Windows**: PostgreSQL service should start automatically

## Step 2: Create PostgreSQL User and Databases

Connect to PostgreSQL:

```bash
psql -U postgres
```

Create databases and user (if needed):

```sql
-- Create database
CREATE DATABASE leave_management_db;

-- Create user (optional, you can use 'postgres' user)
-- CREATE USER stafio_user WITH PASSWORD 'your_password';
-- GRANT ALL PRIVILEGES ON DATABASE leave_management_db TO stafio_user;
```

## Step 3: Configure Environment Variables

Create a `.env` file in the `Stafio_Backend` directory:

```bash
cd Stafio_Backend
touch .env
```

Add the following content to `.env`:

```env
# Database Configuration
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=your_postgres_password
DB_NAME=leave_management_db
```

**Important**: Replace `your_postgres_password` with your actual PostgreSQL password.

## Step 4: Install Python Dependencies

Install required packages:

```bash
cd Stafio_Backend
pip install -r requirements.txt
```

Or if you're using Python 3 specifically:

```bash
pip3 install -r requirements.txt
```

## Step 5: Initialize Databases

Run the initialization script to create databases and tables:

```bash
python init_db_py.py
```

Or:

```bash
python3 init_db_py.py
```

This will:

- Create the databases if they don't exist
- Create all necessary tables
- Set up the database schema

## Step 6: Create Initial Migration (Optional but Recommended)

Create an initial Alembic migration:

```bash
alembic revision --autogenerate -m "Initial migration"
```

This creates a migration file that tracks your current database schema.

## Step 7: Run Migrations

Run migrations to ensure your database is up to date:

```bash
python run_migrations.py
```

Or manually:

```bash
alembic upgrade head
```

## Step 8: Start the Backend Servers

### Start Leave Management Backend (Port 5000):

```bash
python app_py_for_leave_management_backend.py
```

## Auto-Migration on Startup

The application will automatically:

1. Initialize database tables if they don't exist
2. Run migrations to upgrade to the latest schema version

## Creating New Migrations

When you modify database models in `database.py`:

1. Create a new migration:

   ```bash
   alembic revision --autogenerate -m "Description of changes"
   ```

2. Review the generated migration file in `alembic/versions/`

3. Apply the migration:
   ```bash
   alembic upgrade head
   ```

## Troubleshooting

### Database Connection Errors

- Ensure PostgreSQL is running: `pg_isready` or `psql -U postgres`
- Check your `.env` file has correct credentials
- Verify databases exist: `psql -U postgres -l`

### Migration Errors

- Make sure you've run `init_db_py.py` first
- Check that Alembic is installed: `pip list | grep alembic`
- Review migration files in `alembic/versions/` for errors

### Port Already in Use

- Change the port in the app file if 5000 is already in use
- Or stop the process using the port: `lsof -ti:5000 | xargs kill`

## Notes

- The applications use SQLAlchemy ORM instead of raw SQL queries
- All database operations are now PostgreSQL-compatible
- Migrations are handled automatically via Alembic
- Environment variables are loaded from `.env` file
