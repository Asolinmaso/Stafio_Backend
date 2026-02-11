# Frontend-Backend Integration Report

This document maps every Frontend component to its corresponding Backend API endpoints.

## 📂 Admin Section

| Frontend File             | Backend API Endpoint               | HTTP Method | Description                   |
| ------------------------- | ---------------------------------- | ----------- | ----------------------------- |
| **Authentication**        |                                    |             |                               |
| `AdminLogin.jsx`          | `/admin_login`                     | POST        | Admin authentication          |
| `AdminRegister.jsx`       | `/register`                        | POST        | Admin registration            |
|                           |                                    |             |                               |
| **Dashboard**             |                                    |             |                               |
| `Dashboard.jsx`           | `/admin_dashboard`                 | GET         | Admin dashboard statistics    |
|                           |                                    |             |                               |
| **Organization**          |                                    |             |                               |
| `EmployeesList.jsx`       | `/api/employeeslist`               | GET         | List of all employees         |
| `EmployeesMyTeam.jsx`     | `/api/my_team`                     | GET         | Team members for manager      |
| `AdminProfile.jsx`        | `/admin_profile/{id}`              | GET         | View Admin Profile            |
|                           | `/api/user/{id}`                   | PUT         | Update Basic Info             |
| `Topbar.jsx`              | `/admin_profile/{id}`              | GET         | Profile popup details         |
|                           |                                    |             |                               |
| **Attendance**            |                                    |             |                               |
| `Attendance.jsx`          | `/api/attendancelist`              | GET         | All attendance records        |
| `whoIsOnLeave.jsx`        | `/api/who_is_on_leave`             | GET         | Approved leave requests       |
|                           |                                    |             |                               |
| **Leave Management**      |                                    |             |                               |
| `AllLeaveRecords.jsx`     | `/api/all_leave_records`           | GET         | History of all leaves         |
| `LeaveApproval.jsx`       | `/api/leaveapproval`               | GET         | Pending leave requests        |
|                           | `/api/leave_requests/{id}/approve` | PUT         | Approve leave                 |
|                           | `/api/leave_requests/{id}/reject`  | PUT         | Reject leave                  |
| `MyTeamLeaveApproval.jsx` | `/api/myteamla`                    | GET         | Team leave requests           |
| `DepartmentLeaveView.jsx` | `/api/leave_by_department`         | GET         | Leaves filtered by department |
| `LeavePolicies.jsx`       | `/api/leavepolicies`               | GET         | List leave types              |
| `AddLeaveType.jsx`        | `/leave_types`                     | POST        | Create new leave type         |
|                           |                                    |             |                               |
| **Payroll**               |                                    |             |                               |
| `PayrollDashboard.jsx`    | `/api/payroll/summary`             | GET         | Payroll stats                 |
|                           | `/api/payroll`                     | GET         | Payroll records               |
|                           | `/api/payroll/{id}/pay`            | PUT         | Process payment               |
|                           |                                    |             |                               |
| **Performance**           |                                    |             |                               |
| `Performance.jsx`         | `/api/performance/summary`         | GET         | Performance stats             |
|                           | `/api/performance`                 | GET         | Performance reviews           |
|                           |                                    |             |                               |
| **Settings & Tools**      |                                    |             |                               |
| `admin-settings.jsx`      | `/api/settings/general`            | GET/PUT     | General settings              |
|                           | `/api/settings/basic_info`         | GET/PUT     | Admin info                    |
|                           | `/api/settings/break_times`        | GET/PUT     | Break time config             |
|                           | `/api/settings/departments`        | GET         | Department list               |
|                           | `/api/departments`                 | POST        | Create Department             |
|                           | `/api/departments/{id}`            | PUT/DELETE  | Edit/Delete Department        |
| `AdminBroadCast.jsx`      | `/api/broadcast`                   | GET/POST    | Create/View announcements     |

## 📂 Employee Section

| Frontend File                    | Backend API Endpoint         | HTTP Method     | Description                |
| -------------------------------- | ---------------------------- | --------------- | -------------------------- |
| **Authentication**               |                              |                 |                            |
| `EmployeeLogin.jsx`              | `/employee_login`            | POST            | Employee Login             |
|                                  | `/employee_google_login`     | POST            | Google Login               |
| `EmployeeRegister.jsx`           | `/register`                  | POST            | Employee Registration      |
|                                  | `/employee_google_register`  | POST            | Google Registration        |
|                                  |                              |                 |                            |
| **Dashboard**                    |                              |                 |                            |
| `EmployeeDashboard.jsx`          | `/dashboard`                 | GET             | Employee dashboard stats   |
|                                  |                              |                 |                            |
| **Profile**                      |                              |                 |                            |
| `EmployeeProfile.jsx`            | `/employee_profile/{id}`     | GET             | View Profile               |
|                                  | `/api/employee_profile/{id}` | PUT             | Update Profile             |
|                                  |                              |                 |                            |
| **Attendance**                   |                              |                 |                            |
| `Attendance.jsx`                 | `/api/attendance`            | GET             | My attendance history      |
|                                  | `/api/attendance_stats`      | GET             | Attendance summary         |
| `MyRegularization.jsx`           | `/api/myregularization`      | GET             | My regularization requests |
|                                  |                              |                 |                            |
| **Leave**                        |                              |                 |                            |
| `MyLeave.jsx`                    | `/api/myleave`               | GET             | My leave history           |
|                                  | `/api/leave_balance`         | GET             | Leave balance              |
| `ApplyLeave.jsx`                 | `/leave_requests`            | POST            | Submit leave request       |
| `MyHoliday.jsx`                  | `/api/myholidays`            | GET             | Holiday list               |
|                                  |                              |                 |                            |
| **Performance**                  |                              |                 |                            |
| `EmployeePerformanceTracker.jsx` | `/api/tasks`                 | GET/POST/PUT    | detailed task management   |
|                                  | `/api/performance`           | GET             | My performance reviews     |
|                                  |                              |                 |                            |
| **Payroll**                      |                              |                 |                            |
| `EmployeePayroll.jsx`            | `/api/payroll/{id}`          | GET             | My payroll history         |
|                                  | `/api/salary_structure/{id}` | GET             | My salary structure        |
|                                  |                              |                 |                            |
| **Documents**                    |                              |                 |                            |
| `EmployeeDocuments.jsx`          | `/api/documents`             | GET/POST/DELETE | Manage documents           |

## 📂 Core / Shared

| Frontend File   | Backend API Endpoint | HTTP Method | Description           |
| --------------- | -------------------- | ----------- | --------------------- |
| `main.jsx`      | N/A                  |             | Axios defaults setup  |
| `api/client.js` | N/A                  |             | Axios instance config |

---

**Note:** `axios` base URL is usually set to `http://127.0.0.1:5001`.
