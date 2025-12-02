# Stafio Backend

Backend services for the Stafio application, now using PostgreSQL with SQLAlchemy ORM and Alembic for migrations.

## Quick Start

1. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

2. **Set up environment variables:**
   Create a `.env` file with your PostgreSQL credentials (see SETUP.md for details)

3. **Initialize databases:**

   ```bash
   python init_db_py.py
   ```

4. **Run migrations:**

   ```bash
   python run_migrations.py
   ```

5. **Start the server:**
   ```bash
   # Leave Management Backend (Port 5000)
   python app_py_for_leave_management_backend.py
   ```

## What Changed

### Database Migration: MySQL → PostgreSQL

- All database operations now use PostgreSQL
- Raw SQL queries replaced with SQLAlchemy ORM
- Database models defined in `database.py`

### Auto-Migration Support

- Alembic configured for database migrations
- Migrations run automatically on application startup
- Manual migration commands available

### Key Files

- `database.py` - SQLAlchemy models and database configuration
- `app_py_for_leave_management_backend.py` - Leave management API (Port 5000)
- `init_db_py.py` - Database initialization script
- `run_migrations.py` - Migration runner script
- `alembic/` - Alembic migration configuration

## Environment Variables

Create a `.env` file in the backend directory:

```env
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=your_password
DB_NAME=leave_management_db
```

## Database Models

### Leave Management Database (`leave_management_db`)

- `User` - User accounts
- `LeaveType` - Types of leave (Sick, Vacation, etc.)
- `LeaveBalance` - Employee leave balances
- `LeaveRequest` - Leave requests

## Migration Commands

```bash
# Create a new migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# View migration history
alembic history
```

## API Endpoints

### Leave Management Backend (Port 5000)

- `POST /register` - Register new user
- `POST /employee_login` - Employee login
- `POST /google_login` - Google OAuth login
- `GET /users/<id>` - Get user details
- `GET /dashboard` - Employee dashboard data
- `GET /admin_dashboard` - Admin dashboard data
- And more...

## Troubleshooting

See `SETUP.md` for detailed setup instructions and troubleshooting guide.
