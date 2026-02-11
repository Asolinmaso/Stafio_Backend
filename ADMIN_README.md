# Stafio Admin Section - API & Component Analysis

## 📊 Overview

This document serves as a reference for the Admin Section, detailing the mapping between Frontend Components and Backend APIs. It also highlights incomplete or missing features that need attention.

---

## ✅ Completed & Integrated Features

### 1. Authentication

| Frontend Component        | Backend API Endpoint            | Method | Status        |
| ------------------------- | ------------------------------- | ------ | ------------- |
| `AdminLogin.jsx`          | `/admin_login`                  | POST   | ✅ Integrated |
| `AdminRegister.jsx`       | `/register` (with role='admin') | POST   | ✅ Integrated |
| `ForgotPasswordPopup.jsx` | `/forgot_send_otp`              | POST   | ✅ Integrated |
|                           | `/forgot_verify_otp`            | POST   | ✅ Integrated |
|                           | `/reset_password`               | POST   | ✅ Integrated |

### 2. Dashboard

| Frontend Component | Backend API Endpoint | Method | Status        |
| ------------------ | -------------------- | ------ | ------------- |
| `Dashboard.jsx`    | `/admin_dashboard`   | GET    | ✅ Integrated |

### 3. Employee Management (Organization)

| Frontend Component     | Backend API Endpoint       | Method | Status        |
| ---------------------- | -------------------------- | ------ | ------------- |
| `EmployeesList.jsx`    | `/api/employeeslist`       | GET    | ✅ Integrated |
| `Topbar.jsx` (Profile) | `/admin_profile/{user_id}` | GET    | ✅ Integrated |
| `AdminProfile.jsx`     | `/admin_profile/{user_id}` | GET    | ✅ Integrated |

### 4. Attendance Management

| Frontend Component           | Backend API Endpoint          | Method | Status        |
| ---------------------------- | ----------------------------- | ------ | ------------- |
| `Attendance.jsx`             | `/api/attendancelist`         | GET    | ✅ Integrated |
| `WhoIsOnLeave.jsx`           | `/api/who_is_on_leave`        | GET    | ✅ Integrated |
| `RegularizationApproval.jsx` | `/api/regularizationapproval` | GET    | ✅ Integrated |
| `MyTeamRA.jsx`               | `/api/myteamra`               | GET    | ✅ Integrated |

### 5. Leave Management

| Frontend Component        | Backend API Endpoint               | Method | Status        |
| ------------------------- | ---------------------------------- | ------ | ------------- |
| `AllLeaveRecords.jsx`     | `/api/all_leave_records`           | GET    | ✅ Integrated |
| `LeaveApproval.jsx`       | `/api/leaveapproval`               | GET    | ✅ Integrated |
|                           | `/api/leave_requests/{id}/approve` | PUT    | ✅ Integrated |
|                           | `/api/leave_requests/{id}/reject`  | PUT    | ✅ Integrated |
| `LeavePolicies.jsx`       | `/api/leavepolicies`               | GET    | ✅ Integrated |
| `AddLeaveType.jsx`        | `/leave_types`                     | POST   | ✅ Integrated |
| `DepartmentLeaveView.jsx` | `/api/leave_by_department`         | GET    | ✅ Integrated |
| `MyTeamLeaveApproval.jsx` | `/api/myteamla`                    | GET    | ✅ Integrated |

### 6. Payroll

| Frontend Component     | Backend API Endpoint    | Method   | Status        |
| ---------------------- | ----------------------- | -------- | ------------- |
| `PayrollDashboard.jsx` | `/api/payroll/summary`  | GET      | ✅ Integrated |
|                        | `/api/payroll`          | GET      | ✅ Integrated |
|                        | `/api/payroll/{id}/pay` | PUT      | ✅ Integrated |
| `SalaryStructure.jsx`  | `/api/salary_structure` | GET/POST | ✅ Integrated |

### 7. Performance

| Frontend Component | Backend API Endpoint       | Method   | Status        |
| ------------------ | -------------------------- | -------- | ------------- |
| `Performance.jsx`  | `/api/performance/summary` | GET      | ✅ Integrated |
|                    | `/api/performance`         | GET/POST | ✅ Integrated |

### 8. Settings & Broadcast

| Frontend Component   | Backend API Endpoint        | Method     | Status        |
| -------------------- | --------------------------- | ---------- | ------------- |
| `AdminBroadCast.jsx` | `/api/broadcast`            | GET/POST   | ✅ Integrated |
| `admin-settings.jsx` | `/api/settings/general`     | GET/PUT    | ✅ Integrated |
|                      | `/api/settings/basic_info`  | GET/PUT    | ✅ Integrated |
|                      | `/api/settings/break_times` | GET/PUT    | ✅ Integrated |
|                      | `/api/settings/departments` | GET        | ✅ Integrated |
|                      | `/api/departments`          | POST       | ✅ Integrated |
|                      | `/api/departments/{id}`     | PUT/DELETE | ✅ Integrated |
|                      | `/api/settings/team`        | GET        | ✅ Integrated |

---

## 🚧 Pending / Incomplete APIs & Features

These are features that appear in the frontend or seem required but do not have full backend support or are not fully connected.

| Feature Area            | Missing / Incomplete API                   | Notes                                                                                                             |
| ----------------------- | ------------------------------------------ | ----------------------------------------------------------------------------------------------------------------- |
| **Letter Generation**   | `POST /api/generate_letter` (Hypothetical) | `AdminLetterGeneration.jsx` exists but has no backend logic for generating PDFs (Offer/Relieving letters).        |
| **Reports**             | `GET /api/reports/attendance`              | Detailed downloadable reports for attendance are missing (export to CSV/PDF).                                     |
|                         | `GET /api/reports/payroll`                 | Payroll export functionality is likely needed.                                                                    |
| **Notifications**       | `POST /api/notifications/send`             | Ability for admin to send direct individual notifications (outside of Broadcast).                                 |
| **Document Management** | `GET/POST /api/documents`                  | Basic endpoints exist but full file upload/storage handling (e.g., S3 or local storage serve) needs verification. |
| **Audit Logs**          | `GET /api/audit_logs`                      | No system in place to track admin actions (important for security).                                               |

---

## 📁 File Structure Reference

### Backend (`stafio_backend/`)

- `app_py_for_leave_management_backend.py`: Main entry point, contains core logic for Auth, Payroll, Performance, Attendance.
- `admin_endpoints.py`: Dedicated module for Admin-specific endpoints (Settings, Leave Records, Department management).
- `database.py`: SQLAlchemy models.

### Frontend (`stafio_frontend/src/Components/Admin-Section/`)

- Mapped extensively to the features above.
