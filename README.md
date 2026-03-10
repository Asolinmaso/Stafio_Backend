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

## Testing APIs with Postman

### Step 1: Setup Postman Environment

Create a Postman Environment called **"Stafio Local"** with these variables:

| Variable        | Initial Value           |
| --------------- | ----------------------- |
| `base_url`      | `http://127.0.0.1:5001` |
| `access_token`  | _(leave empty)_         |
| `refresh_token` | _(leave empty)_         |
| `user_id`       | _(leave empty)_         |
| `role`          | _(leave empty)_         |

### Step 2: Login to Get JWT Tokens

**Admin Login:**

```
POST {{base_url}}/admin_login
Content-Type: application/json

{
  "identifier": "your_admin_email@gmail.com",
  "password": "YourPassword123"
}
```

**Employee Login:**

```
POST {{base_url}}/employee_login
Content-Type: application/json

{
  "identifier": "employee_email@gmail.com",
  "password": "EmpPassword123"
}
```

**Response (both):**

```json
{
  "user_id": 1,
  "username": "admin",
  "role": "admin",
  "email": "admin@gmail.com",
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

> **Auto-save tokens:** In Postman, go to the login request's **Tests** tab and paste this script to auto-save tokens:
>
> ```javascript
> if (pm.response.code === 200) {
>   var data = pm.response.json();
>   pm.environment.set("access_token", data.access_token);
>   pm.environment.set("refresh_token", data.refresh_token);
>   pm.environment.set("user_id", data.user_id);
>   pm.environment.set("role", data.role);
> }
> ```

### Step 3: Use Tokens for Protected Routes

For **all protected endpoints**, add this header:

| Header          | Value                     |
| --------------- | ------------------------- |
| `Authorization` | `Bearer {{access_token}}` |

Or in Postman: Go to request → **Authorization** tab → Type: **Bearer Token** → Token: `{{access_token}}`

**Backward-compatible alternative** (if JWT isn't set):

| Header        | Value         |
| ------------- | ------------- |
| `X-User-ID`   | `{{user_id}}` |
| `X-User-Role` | `{{role}}`    |

### Step 4: Refresh Expired Tokens

Access tokens expire in **15 minutes**. To refresh:

```
POST {{base_url}}/api/refresh
Content-Type: application/json

{
  "refresh_token": "{{refresh_token}}"
}
```

**Response:**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

### Step 5: Logout

```
POST {{base_url}}/api/logout
Authorization: Bearer {{access_token}}
Content-Type: application/json

{
  "refresh_token": "{{refresh_token}}"
}
```

---

## API Endpoints Reference

> **Auth**: 🔓 = Public (no token needed) | 🔒 = JWT required | 🔒👑 = JWT + Admin role required

### Authentication (🔓 Public)

| Method | Endpoint                    | Body                                         |
| ------ | --------------------------- | -------------------------------------------- |
| POST   | `/register`                 | `{ username, email, phone, password, role }` |
| POST   | `/admin_login`              | `{ identifier, password }`                   |
| POST   | `/employee_login`           | `{ identifier, password }`                   |
| POST   | `/admin_google_login`       | `{ access_token, role: "admin" }`            |
| POST   | `/employee_google_login`    | `{ access_token, role: "employee" }`         |
| POST   | `/admin_google_register`    | `{ email, username, role: "admin" }`         |
| POST   | `/employee_google_register` | `{ email, username, role: "employee" }`      |
| POST   | `/forgot_send_otp`          | `{ email }`                                  |
| POST   | `/forgot_verify_otp`        | `{ email, otp }`                             |
| POST   | `/reset_password`           | `{ email, new_password }`                    |

### Token Management

| Method | Endpoint       | Auth | Body                |
| ------ | -------------- | ---- | ------------------- |
| POST   | `/api/refresh` | 🔓   | `{ refresh_token }` |
| POST   | `/api/logout`  | 🔒   | `{ refresh_token }` |
| GET    | `/protected`   | 🔒   | —                   |

### Dashboard

| Method | Endpoint                | Auth | Params       |
| ------ | ----------------------- | ---- | ------------ |
| GET    | `/admin_dashboard`      | 🔒   | —            |
| GET    | `/employee_dashboard`   | 🔒   | `?user_id=1` |
| GET    | `/admin_dashboard_data` | 🔒   | —            |

### Attendance

| Method | Endpoint                      | Auth | Body / Params |
| ------ | ----------------------------- | ---- | ------------- |
| POST   | `/api/attendance/punch-in`    | 🔒   | `{ user_id }` |
| POST   | `/api/attendance/punch-out`   | 🔒   | `{ user_id }` |
| POST   | `/api/attendance/start-break` | 🔒   | `{ user_id }` |
| POST   | `/api/attendance/end-break`   | 🔒   | `{ user_id }` |
| GET    | `/api/attendance/today`       | 🔒   | `?user_id=1`  |
| GET    | `/api/attendancelist`         | 🔒   | —             |
| GET    | `/api/attendance_stats`       | 🔒   | `?user_id=1`  |
| GET    | `/api/attendance`             | 🔒   | `?user_id=1`  |

### Leave Management

| Method | Endpoint               | Auth | Body / Params                                              |
| ------ | ---------------------- | ---- | ---------------------------------------------------------- |
| POST   | `/api/leave_request`   | 🔒   | `{ user_id, leave_type_id, start_date, end_date, reason }` |
| GET    | `/api/leave_data`      | 🔒   | `?user_id=1`                                               |
| GET    | `/api/leave_balance`   | 🔒   | `?user_id=1`                                               |
| GET    | `/api/leave_types`     | 🔒   | —                                                          |
| GET    | `/api/who_is_on_leave` | 🔒   | —                                                          |

### Leave Approval (Admin)

| Method | Endpoint                          | Auth | Body                       |
| ------ | --------------------------------- | ---- | -------------------------- |
| GET    | `/api/leave_approval`             | 🔒👑 | —                          |
| GET    | `/api/my_team_leave_approval`     | 🔒   | `?user_id=1`               |
| PUT    | `/api/leave_request/<id>/approve` | 🔒👑 | `{ approved_by, remarks }` |
| PUT    | `/api/leave_request/<id>/reject`  | 🔒👑 | `{ approved_by, remarks }` |

### Leave Policies (Admin)

| Method | Endpoint                 | Auth | Body                                                      |
| ------ | ------------------------ | ---- | --------------------------------------------------------- |
| GET    | `/api/leave_policies`    | 🔒👑 | —                                                         |
| POST   | `/api/leave_type`        | 🔒👑 | `{ name, description, max_days_per_year, carry_forward }` |
| PUT    | `/api/leave_policy/<id>` | 🔒👑 | `{ name, max_days_per_year, ... }`                        |
| DELETE | `/api/leave_policy/<id>` | 🔒👑 | —                                                         |

### Regularization

| Method | Endpoint                           | Auth | Body / Params                                    |
| ------ | ---------------------------------- | ---- | ------------------------------------------------ |
| GET    | `/api/regularization`              | 🔒   | `?user_id=1`                                     |
| POST   | `/api/regularization`              | 🔒   | `{ user_id, date, check_in, check_out, reason }` |
| PUT    | `/api/regularization/<id>`         | 🔒   | `{ check_in, check_out, reason }`                |
| DELETE | `/api/regularization/<id>`         | 🔒   | —                                                |
| PUT    | `/api/regularization/<id>/approve` | 🔒👑 | `{ approved_by }`                                |
| PUT    | `/api/regularization/<id>/reject`  | 🔒👑 | `{ approved_by, remarks }`                       |

### Holidays

| Method | Endpoint        | Auth | Body                                              |
| ------ | --------------- | ---- | ------------------------------------------------- |
| GET    | `/api/holidays` | 🔒   | —                                                 |
| POST   | `/api/holidays` | 🔒👑 | `{ date, title, description, is_optional, year }` |

### Employee Management

| Method | Endpoint                         | Auth | Body                                                                                |
| ------ | -------------------------------- | ---- | ----------------------------------------------------------------------------------- |
| GET    | `/api/employeeslist`             | 🔒   | —                                                                                   |
| POST   | `/api/add_employee`              | 🔒👑 | `{ first_name, last_name, email, phone, department, position, supervisor_id, ... }` |
| PUT    | `/api/update_employee/<user_id>` | 🔒👑 | `{ first_name, last_name, phone, ... }`                                             |
| GET    | `/employee_profile/<user_id>`    | 🔒   | —                                                                                   |
| GET    | `/admin_profile/<user_id>`       | 🔒   | —                                                                                   |
| PUT    | `/admin_profile/<user_id>`       | 🔒   | `{ personal_info, education, skills, ... }`                                         |

### Organization (Admin Blueprint)

| Method | Endpoint                                       | Auth |
| ------ | ---------------------------------------------- | ---- |
| GET    | `/api/admin/all-leave-records`                 | 🔒👑 |
| GET    | `/api/admin/leave-by-department?department=IT` | 🔒👑 |
| GET    | `/api/admin/departments`                       | 🔒👑 |
| GET    | `/api/admin/my-team`                           | 🔒   |
| POST   | `/api/admin/add-team-member`                   | 🔒👑 |
| GET    | `/api/admin/employee-leave-balance/<user_id>`  | 🔒👑 |
| GET    | `/api/admin/supervisors`                       | 🔒👑 |

### Settings (Admin)

| Method | Endpoint                                  | Auth | Body                                    |
| ------ | ----------------------------------------- | ---- | --------------------------------------- |
| GET    | `/api/admin/settings/general`             | 🔒👑 | —                                       |
| PUT    | `/api/admin/settings/general`             | 🔒👑 | `{ system_language, admin_theme, ... }` |
| GET    | `/api/admin/settings/break-times`         | 🔒👑 | —                                       |
| PUT    | `/api/admin/settings/break-times`         | 🔒👑 | `{ lunch_break, coffee_break }`         |
| GET    | `/api/admin/settings/team`                | 🔒👑 | —                                       |
| PUT    | `/api/admin/settings/team/<user_id>/role` | 🔒👑 | `{ role }`                              |
| POST   | `/api/admin/settings/departments`         | 🔒👑 | `{ name, description, manager_id }`     |
| PUT    | `/api/admin/settings/departments/<id>`    | 🔒👑 | `{ name, manager_id }`                  |
| DELETE | `/api/admin/settings/departments/<id>`    | 🔒👑 | —                                       |

### Broadcasts / Announcements

| Method | Endpoint                              | Auth | Body                                     |
| ------ | ------------------------------------- | ---- | ---------------------------------------- |
| GET    | `/api/broadcast`                      | 🔓   | —                                        |
| GET    | `/api/admin/announcements`            | 🔒👑 | —                                        |
| POST   | `/api/admin/announcements`            | 🔒👑 | `{ title, message, category, priority }` |
| POST   | `/api/admin/announcements/<id>/react` | 🔒   | `{ reaction_type }`                      |

---

## Quick Test Workflow

Here's the recommended order to test everything in Postman:

```
1. POST /register          → Create a test user
2. POST /admin_login       → Get tokens (save them)
3. GET  /protected         → Verify token works (should return 200)
4. GET  /api/employeeslist → Test a protected endpoint
5. POST /api/leave_request → Create a leave request
6. GET  /api/leave_approval → See pending requests
7. PUT  /api/leave_request/1/approve → Approve it
8. POST /api/refresh       → Refresh when token expires
9. POST /api/logout        → Blacklist tokens
10. GET /protected         → Should return 401 (token blacklisted)
```

## Common Postman Errors

| Error                        | Cause                                            | Fix                                  |
| ---------------------------- | ------------------------------------------------ | ------------------------------------ |
| `401 Unauthorized`           | Missing or expired token                         | Login again or call `/api/refresh`   |
| `403 Forbidden`              | Wrong role (e.g. employee accessing admin route) | Login with admin account             |
| `404 Not Found`              | Wrong URL or missing path parameter              | Check endpoint URL spelling          |
| `415 Unsupported Media Type` | Missing Content-Type header                      | Add `Content-Type: application/json` |
| `500 Internal Server Error`  | Backend bug or DB issue                          | Check terminal for Python traceback  |

## Troubleshooting

See `SETUP.md` for detailed setup instructions and troubleshooting guide.
