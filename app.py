import os
import csv
import io
import json
import sqlite3
from datetime import datetime, date
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, Response
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")
app = Flask(__name__, template_folder=TEMPLATES_DIR, static_folder=STATIC_DIR)
app.secret_key = os.environ.get("SECRET_KEY", "vvitu_3d_glass_secret_2026")
DATA_DIR = os.path.join(BASE_DIR, "data")
SLIPS_DIR = os.path.join(DATA_DIR, "saved_payslips")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(SLIPS_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "workforce.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('HR', 'Administrator')),
            department TEXT,
            avatar_url TEXT DEFAULT '/static/images/avatar_hr.png',
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            emp_code TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT NOT NULL,
            gender TEXT NOT NULL,
            dob TEXT NOT NULL,
            address TEXT NOT NULL,
            department TEXT NOT NULL,
            emp_role TEXT NOT NULL,
            employment_type TEXT NOT NULL,
            joining_date TEXT NOT NULL,
            basic_salary REAL NOT NULL,
            hra_percent REAL DEFAULT 20.0,
            special_allowance REAL DEFAULT 0.0,
            pf_percent REAL DEFAULT 5.0,
            bank_account TEXT,
            emergency_contact TEXT,
            avatar_url TEXT DEFAULT '/static/images/avatar_emp1.png',
            password_hash TEXT NOT NULL,
            status TEXT DEFAULT 'Active',
            added_by TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            att_date TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('Present', 'Absent', 'Half-Day', 'Leave')),
            remarks TEXT,
            marked_by TEXT,
            UNIQUE(employee_id, att_date),
            FOREIGN KEY(employee_id) REFERENCES employees(id) ON DELETE CASCADE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS payroll (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            month_year TEXT NOT NULL,
            working_days INTEGER NOT NULL,
            present_days REAL NOT NULL,
            basic_salary REAL NOT NULL,
            hra_allowance REAL NOT NULL,
            special_allowance REAL DEFAULT 0.0,
            bonus REAL DEFAULT 0.0,
            deductions REAL NOT NULL,
            net_salary REAL NOT NULL,
            payment_status TEXT DEFAULT 'Pending',
            paid_date TEXT,
            paid_by TEXT,
            receipt_no TEXT,
            saved_slip_file TEXT,
            slip_snapshot TEXT,
            generated_by TEXT,
            generated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(employee_id, month_year),
            FOREIGN KEY(employee_id) REFERENCES employees(id) ON DELETE CASCADE
        )
    """)

    cur.execute("SELECT COUNT(*) as cnt FROM users")
    if cur.fetchone()["cnt"] == 0:
        cur.execute(
            "INSERT INTO users (full_name, email, phone, role, department, avatar_url, password_hash) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("VVITU Admin", "admin@vvitu.ac.in", "9876543210", "Administrator", "Operations", "/static/images/avatar_admin.png", generate_password_hash("admin123"))
        )
        cur.execute(
            "INSERT INTO users (full_name, email, phone, role, department, avatar_url, password_hash) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("VVITU HR", "hr@vvitu.ac.in", "9876543211", "HR", "Human Resources", "/static/images/avatar_hr.png", generate_password_hash("hr123"))
        )

    cur.execute("SELECT COUNT(*) as cnt FROM employees")
    if cur.fetchone()["cnt"] == 0:
        default_emp_pw = generate_password_hash("emp123")
        sample_emps = [
            ("VVITUEMP01", "VVITUEMP01", "vvituemp01@vvitu.ac.in", "9123456780", "Male", "1996-05-14", "VVITU Office", "Engineering", "Senior Software Engineer", "Full-Time", "2023-06-15", 82000.0, 20.0, 6500.0, 5.0, "HDFC0001234", "9123456789", "/static/images/avatar_emp1.png", default_emp_pw, "Active", "VVITU Admin"),
            ("VVITUEMP02", "VVITUEMP02", "vvituemp02@vvitu.ac.in", "9123456781", "Female", "1998-08-22", "VVITU Office", "Human Resources", "HR Executive", "Full-Time", "2024-03-10", 52000.0, 20.0, 4000.0, 5.0, "ICIC0005678", "9123456790", "/static/images/avatar_emp2.png", default_emp_pw, "Active", "VVITU HR"),
            ("VVITUEMP03", "VVITUEMP03", "vvituemp03@vvitu.ac.in", "9123456782", "Male", "1993-11-02", "VVITU Office", "Product", "Team Lead", "Full-Time", "2022-07-01", 98000.0, 20.0, 9000.0, 5.0, "SBIN0009876", "9123456791", "/static/images/avatar_emp3.png", default_emp_pw, "Active", "VVITU Admin"),
        ]
        cur.executemany("""
            INSERT INTO employees (
                emp_code, full_name, email, phone, gender, dob, address,
                department, emp_role, employment_type, joining_date,
                basic_salary, hra_percent, special_allowance, pf_percent,
                bank_account, emergency_contact, avatar_url, password_hash, status, added_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, sample_emps)

    conn.commit()
    conn.close()


init_db()


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please sign in to VVITU Portal.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def staff_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get("role") not in ("HR", "Administrator"):
            flash("Restricted to HR & Administrators.", "danger")
            return redirect(url_for("employee_dashboard"))
        return f(*args, **kwargs)
    return decorated


def employee_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get("role") != "Employee":
            flash("Please sign in using Employee tab.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def save_permanent_payslip_file(p_row):
    filename = f"VVITU_Payslip_{p_row['emp_code']}_{p_row['month_year']}_{p_row['receipt_no']}.html"
    filepath = os.path.join(SLIPS_DIR, filename)
    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>VVITU Payslip - {p_row['emp_code']} ({p_row['month_year']})</title>
<style>
  body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #1e1b4b; padding: 30px; color: #0f172a; }}
  .slip {{ max-width: 740px; margin: 0 auto; background: #ffffff; padding: 34px; border-radius: 16px; box-shadow: 0 20px 40px rgba(0,0,0,0.35); }}
  .header {{ display: flex; justify-content: space-between; border-bottom: 2px solid #312e81; padding-bottom: 14px; margin-bottom: 20px; }}
  .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 22px; font-size: 14px; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
  th, td {{ padding: 11px 12px; border: 1px solid #e2e8f0; text-align: left; font-size: 14px; }}
  th {{ background: #f1f5f9; }}
  .total {{ background: #ecfdf5; font-weight: bold; font-size: 16px; }}
  .stamp {{ display: inline-block; padding: 5px 14px; background: #dcfce7; color: #166534; border-radius: 999px; font-weight: bold; font-size: 12px; }}
</style>
</head>
<body>
<div class="slip">
  <div class="header">
    <div>
      <h2 style="margin:0; color:#312e81;">VVITU — Payroll System</h2>
      <p style="margin:4px 0 0; color:#475569;">Receipt No: <strong>{p_row['receipt_no']}</strong></p>
    </div>
    <div style="text-align:right;">
      <span class="stamp">PAID & SAVED</span>
      <p style="margin:6px 0 0; font-size:13px;">Paid Date: {p_row['paid_date']}</p>
    </div>
  </div>
  <div class="grid">
    <div><strong>Employee ID:</strong> {p_row['emp_code']}</div>
    <div><strong>VVITU Email:</strong> {p_row['email']}</div>
    <div><strong>Department:</strong> {p_row['department']}</div>
    <div><strong>Role:</strong> {p_row['emp_role']}</div>
    <div><strong>Pay Month:</strong> {p_row['month_year']}</div>
    <div><strong>Bank Account:</strong> {p_row['bank_account'] or 'N/A'}</div>
    <div><strong>Present / Working:</strong> {p_row['present_days']} / {p_row['working_days']}</div>
    <div><strong>Authorized By:</strong> {p_row['paid_by']}</div>
  </div>
  <table>
    <thead>
      <tr><th>Salary Component</th><th>Type</th><th style="text-align:right;">Amount (Rs.)</th></tr>
    </thead>
    <tbody>
      <tr><td>Earned Basic Salary</td><td>Earning</td><td style="text-align:right;">{p_row['basic_salary']:.2f}</td></tr>
      <tr><td>House Rent Allowance (HRA)</td><td>Earning</td><td style="text-align:right;">{p_row['hra_allowance']:.2f}</td></tr>
      <tr><td>Special Allowance</td><td>Earning</td><td style="text-align:right;">{p_row['special_allowance']:.2f}</td></tr>
      <tr><td>Performance Bonus</td><td>Earning</td><td style="text-align:right;">{p_row['bonus']:.2f}</td></tr>
      <tr><td>PF / Tax Deductions</td><td>Deduction</td><td style="text-align:right; color:#dc2626;">-{p_row['deductions']:.2f}</td></tr>
      <tr class="total"><td colspan="2">Net Salary Paid</td><td style="text-align:right;">Rs. {p_row['net_salary']:.2f}</td></tr>
    </tbody>
  </table>
</div>
</body>
</html>"""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html_doc)
    return filename


@app.route("/")
def index():
    if "user_id" in session:
        if session.get("role") == "Employee":
            return redirect(url_for("employee_dashboard"))
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        selected_role = request.form.get("role", "HR")

        conn = get_db()
        if selected_role == "Employee":
            emp = conn.execute("SELECT * FROM employees WHERE email = ?", (email,)).fetchone()
            conn.close()
            if emp and check_password_hash(emp["password_hash"], password):
                session.clear()
                session["user_id"] = emp["id"]
                session["emp_code"] = emp["emp_code"]
                session["user_name"] = emp["full_name"]
                session["user_email"] = emp["email"]
                session["avatar_url"] = emp["avatar_url"] or "/static/images/avatar_emp1.png"
                session["role"] = "Employee"
                flash(f"Welcome to VVITU ({emp['email']})!", "success")
                return redirect(url_for("employee_dashboard"))
            else:
                flash("Invalid VVITU Employee email or password.", "danger")
        else:
            user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            conn.close()
            if user and check_password_hash(user["password_hash"], password):
                if user["role"] != selected_role:
                    flash(f"Role mismatch! Account registered as {user['role']}.", "danger")
                    return redirect(url_for("login"))

                session.clear()
                session["user_id"] = user["id"]
                session["user_name"] = user["full_name"]
                session["user_email"] = user["email"]
                session["avatar_url"] = user["avatar_url"] or "/static/images/avatar_admin.png"
                session["role"] = user["role"]
                flash(f"Welcome back to VVITU ({user['role']})!", "success")
                return redirect(url_for("dashboard"))
            else:
                flash("Invalid credentials for selected role.", "danger")

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        role = request.form.get("role", "").strip()
        department = request.form.get("department", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if role not in ("HR", "Administrator"):
            flash("Please choose HR or Administrator role.", "danger")
            return redirect(url_for("register"))

        if password != confirm_password:
            flash("Passwords do not match!", "danger")
            return redirect(url_for("register"))

        avatar_url = "/static/images/avatar_admin.png" if role == "Administrator" else "/static/images/avatar_hr.png"

        conn = get_db()
        existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            conn.close()
            flash("Email already registered!", "danger")
            return redirect(url_for("register"))

        conn.execute(
            "INSERT INTO users (full_name, email, phone, role, department, avatar_url, password_hash) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (full_name, email, phone, role, department, avatar_url, generate_password_hash(password))
        )
        conn.commit()
        conn.close()
        flash(f"{role} account saved permanently! Please sign in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Signed out from VVITU Portal.", "info")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
@staff_required
def dashboard():
    conn = get_db()
    total_employees = conn.execute("SELECT COUNT(*) as c FROM employees").fetchone()["c"]
    active_employees = conn.execute("SELECT COUNT(*) as c FROM employees WHERE status='Active'").fetchone()["c"]
    today_str = date.today().isoformat()
    current_month = datetime.now().strftime("%Y-%m")

    present_today = conn.execute(
        "SELECT COUNT(*) as c FROM attendance WHERE att_date = ? AND status IN ('Present', 'Half-Day')",
        (today_str,)
    ).fetchone()["c"]

    paid_total = conn.execute(
        "SELECT COALESCE(SUM(net_salary), 0) as total FROM payroll WHERE payment_status='Paid'"
    ).fetchone()["total"]
    pending_total = conn.execute(
        "SELECT COALESCE(SUM(net_salary), 0) as total FROM payroll WHERE payment_status='Pending'"
    ).fetchone()["total"]
    saved_slips_count = conn.execute(
        "SELECT COUNT(*) as c FROM payroll WHERE payment_status='Paid'"
    ).fetchone()["c"]

    dept_rows = conn.execute(
        "SELECT department, COUNT(*) as emp_count, COALESCE(SUM(basic_salary), 0) as dept_salary FROM employees GROUP BY department"
    ).fetchall()
    dept_labels = [r["department"] for r in dept_rows]
    dept_counts = [r["emp_count"] for r in dept_rows]
    dept_salaries = [round(r["dept_salary"], 2) for r in dept_rows]

    att_summary = conn.execute("""
        SELECT
            COALESCE(SUM(CASE WHEN status='Present' THEN 1 ELSE 0 END), 0) as present_c,
            COALESCE(SUM(CASE WHEN status='Half-Day' THEN 1 ELSE 0 END), 0) as half_c,
            COALESCE(SUM(CASE WHEN status='Leave' THEN 1 ELSE 0 END), 0) as leave_c,
            COALESCE(SUM(CASE WHEN status='Absent' THEN 1 ELSE 0 END), 0) as absent_c
        FROM attendance
    """).fetchone()
    att_chart_data = [
        att_summary["present_c"],
        att_summary["half_c"],
        att_summary["leave_c"],
        att_summary["absent_c"]
    ]

    month_rows = conn.execute("""
        SELECT month_year,
               COALESCE(SUM(CASE WHEN payment_status='Paid' THEN net_salary ELSE 0 END), 0) as paid_amt,
               COALESCE(SUM(CASE WHEN payment_status='Pending' THEN net_salary ELSE 0 END), 0) as pending_amt
        FROM payroll
        GROUP BY month_year
        ORDER BY month_year ASC
        LIMIT 6
    """).fetchall()
    month_labels = [r["month_year"] for r in month_rows] if month_rows else [current_month]
    month_paid = [round(r["paid_amt"], 2) for r in month_rows] if month_rows else [0]
    month_pending = [round(r["pending_amt"], 2) for r in month_rows] if month_rows else [0]

    recent_employees = conn.execute("SELECT * FROM employees ORDER BY id DESC LIMIT 5").fetchall()
    recent_paid_slips = conn.execute("""
        SELECT p.*, e.emp_code, e.full_name, e.email, e.department, e.emp_role, e.avatar_url
        FROM payroll p JOIN employees e ON p.employee_id = e.id
        WHERE p.payment_status = 'Paid'
        ORDER BY p.paid_date DESC, p.id DESC LIMIT 6
    """).fetchall()

    total_users = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
    hr_count = conn.execute("SELECT COUNT(*) as c FROM users WHERE role='HR'").fetchone()["c"]
    admin_count = conn.execute("SELECT COUNT(*) as c FROM users WHERE role='Administrator'").fetchone()["c"]
    system_users = conn.execute("SELECT id, full_name, email, phone, role, department, avatar_url, created_at FROM users ORDER BY id DESC").fetchall()

    conn.close()

    template_name = "admin_dashboard.html" if session.get("role") == "Administrator" else "hr_dashboard.html"
    return render_template(
        template_name,
        total_employees=total_employees,
        active_employees=active_employees,
        present_today=present_today,
        paid_total=paid_total,
        pending_total=pending_total,
        saved_slips_count=saved_slips_count,
        recent_employees=recent_employees,
        recent_paid_slips=recent_paid_slips,
        total_users=total_users,
        hr_count=hr_count,
        admin_count=admin_count,
        system_users=system_users,
        today_str=today_str,
        current_month=current_month,
        dept_labels=json.dumps(dept_labels),
        dept_counts=json.dumps(dept_counts),
        dept_salaries=json.dumps(dept_salaries),
        att_chart_data=json.dumps(att_chart_data),
        month_labels=json.dumps(month_labels),
        month_paid=json.dumps(month_paid),
        month_pending=json.dumps(month_pending)
    )


@app.route("/employee/portal")
@login_required
@employee_required
def employee_dashboard():
    emp_id = session.get("user_id")
    conn = get_db()
    emp = conn.execute("SELECT * FROM employees WHERE id = ?", (emp_id,)).fetchone()
    if not emp:
        conn.close()
        session.clear()
        return redirect(url_for("login"))

    my_payslips = conn.execute(
        "SELECT * FROM payroll WHERE employee_id = ? ORDER BY month_year DESC",
        (emp_id,)
    ).fetchall()

    my_attendance = conn.execute(
        "SELECT * FROM attendance WHERE employee_id = ? ORDER BY att_date DESC LIMIT 15",
        (emp_id,)
    ).fetchall()

    total_received = sum(p["net_salary"] for p in my_payslips if p["payment_status"] == "Paid")
    paid_count = sum(1 for p in my_payslips if p["payment_status"] == "Paid")

    conn.close()
    return render_template(
        "employee_portal.html",
        emp=emp,
        my_payslips=my_payslips,
        my_attendance=my_attendance,
        total_received=total_received,
        paid_count=paid_count
    )


@app.route("/employee/payslip/<int:payroll_id>")
@login_required
@employee_required
def employee_view_payslip(payroll_id):
    emp_id = session.get("user_id")
    conn = get_db()
    record = conn.execute("""
        SELECT p.*, e.emp_code, e.full_name, e.department, e.emp_role, e.bank_account, e.email, e.phone, e.joining_date, e.avatar_url
        FROM payroll p
        JOIN employees e ON p.employee_id = e.id
        WHERE p.id = ? AND p.employee_id = ?
    """, (payroll_id, emp_id)).fetchone()
    conn.close()

    if not record:
        flash("Payslip not found or unauthorized.", "danger")
        return redirect(url_for("employee_dashboard"))

    return render_template("payslip.html", p=record, is_employee_view=True)


@app.route("/employees")
@login_required
@staff_required
def employees():
    search = request.args.get("search", "").strip()
    dept_filter = request.args.get("department", "").strip()
    conn = get_db()

    query = "SELECT * FROM employees WHERE 1=1"
    params = []
    if search:
        query += " AND (full_name LIKE ? OR emp_code LIKE ? OR email LIKE ? OR emp_role LIKE ?)"
        like = f"%{search}%"
        params.extend([like, like, like, like])
    if dept_filter:
        query += " AND department = ?"
        params.append(dept_filter)

    query += " ORDER BY id DESC"
    emp_list = conn.execute(query, params).fetchall()
    conn.close()
    return render_template("employees.html", employees=emp_list, search=search, dept_filter=dept_filter)


@app.route("/employees/add", methods=["GET", "POST"])
@login_required
@staff_required
def add_employee():
    if request.method == "POST":
        emp_code = request.form.get("emp_code", "").strip().upper()
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        gender = request.form.get("gender", "").strip()
        dob = request.form.get("dob", "").strip()
        address = request.form.get("address", "").strip()
        department = request.form.get("department", "").strip()
        emp_role = request.form.get("emp_role", "").strip()
        employment_type = request.form.get("employment_type", "").strip()
        joining_date = request.form.get("joining_date", "").strip()
        basic_salary = float(request.form.get("basic_salary", 0))
        hra_percent = float(request.form.get("hra_percent", 20))
        special_allowance = float(request.form.get("special_allowance", 0))
        pf_percent = float(request.form.get("pf_percent", 5))
        bank_account = request.form.get("bank_account", "").strip()
        emergency_contact = request.form.get("emergency_contact", "").strip()
        avatar_url = request.form.get("avatar_url", "/static/images/avatar_emp1.png").strip()
        emp_password = request.form.get("emp_password", "emp123").strip() or "emp123"
        status = request.form.get("status", "Active").strip()

        conn = get_db()
        try:
            conn.execute("""
                INSERT INTO employees (
                    emp_code, full_name, email, phone, gender, dob, address,
                    department, emp_role, employment_type, joining_date,
                    basic_salary, hra_percent, special_allowance, pf_percent,
                    bank_account, emergency_contact, avatar_url, password_hash, status, added_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                emp_code, full_name, email, phone, gender, dob, address,
                department, emp_role, employment_type, joining_date,
                basic_salary, hra_percent, special_allowance, pf_percent,
                bank_account, emergency_contact, avatar_url, generate_password_hash(emp_password), status, session.get("user_name")
            ))
            conn.commit()
            flash(f"VVITU Employee ({email}) added & saved permanently!", "success")
            return redirect(url_for("employees"))
        except sqlite3.IntegrityError:
            flash("VVITU ID or Email already exists!", "danger")
        finally:
            conn.close()

    conn = get_db()
    count = conn.execute("SELECT COUNT(*) as c FROM employees").fetchone()["c"]
    conn.close()
    next_num = count + 1
    suggested_code = f"VVITUEMP{next_num:02d}"
    suggested_email = f"vvituemp{next_num:02d}@vvitu.ac.in"
    return render_template("add_employee.html", suggested_code=suggested_code, suggested_email=suggested_email)


@app.route("/employees/salary-setup/<int:emp_id>", methods=["POST"])
@login_required
@staff_required
def update_salary_structure(emp_id):
    basic_salary = float(request.form.get("basic_salary", 0))
    hra_percent = float(request.form.get("hra_percent", 20))
    special_allowance = float(request.form.get("special_allowance", 0))
    pf_percent = float(request.form.get("pf_percent", 5))
    bank_account = request.form.get("bank_account", "").strip()

    conn = get_db()
    conn.execute("""
        UPDATE employees
        SET basic_salary = ?, hra_percent = ?, special_allowance = ?, pf_percent = ?, bank_account = ?
        WHERE id = ?
    """, (basic_salary, hra_percent, special_allowance, pf_percent, bank_account, emp_id))
    conn.commit()
    conn.close()
    flash("Salary structure updated!", "success")
    return redirect(url_for("payroll"))


@app.route("/employees/role/<int:emp_id>", methods=["POST"])
@login_required
@staff_required
def update_employee_role(emp_id):
    new_department = request.form.get("department", "").strip()
    new_role = request.form.get("emp_role", "").strip()
    new_type = request.form.get("employment_type", "").strip()
    new_status = request.form.get("status", "Active").strip()

    conn = get_db()
    conn.execute(
        "UPDATE employees SET department = ?, emp_role = ?, employment_type = ?, status = ? WHERE id = ?",
        (new_department, new_role, new_type, new_status, emp_id)
    )
    conn.commit()
    conn.close()
    flash("Employee role updated!", "success")
    return redirect(url_for("roles"))


@app.route("/employees/delete/<int:emp_id>", methods=["POST"])
@login_required
@staff_required
def delete_employee(emp_id):
    next_page = request.form.get("next", "employees")
    conn = get_db()
    emp = conn.execute("SELECT emp_code, email FROM employees WHERE id = ?", (emp_id,)).fetchone()
    conn.execute("DELETE FROM employees WHERE id = ?", (emp_id,))
    conn.commit()
    conn.close()
    if emp:
        flash(f"Employee {emp['emp_code']} ({emp['email']}) deleted.", "info")
    else:
        flash("Employee deleted.", "info")
    if next_page == "roles":
        return redirect(url_for("roles"))
    return redirect(url_for("employees"))


@app.route("/roles")
@login_required
@staff_required
def roles():
    conn = get_db()
    emp_list = conn.execute("SELECT * FROM employees ORDER BY id ASC").fetchall()
    count = len(emp_list)
    conn.close()
    next_num = count + 1
    suggested_code = f"VVITUEMP{next_num:02d}"
    suggested_email = f"vvituemp{next_num:02d}@vvitu.ac.in"
    return render_template("roles.html", employees=emp_list, suggested_code=suggested_code, suggested_email=suggested_email)


@app.route("/attendance", methods=["GET", "POST"])
@login_required
@staff_required
def attendance():
    selected_date = request.args.get("date", date.today().isoformat())
    conn = get_db()

    if request.method == "POST":
        att_date = request.form.get("att_date", date.today().isoformat())
        emp_ids = request.form.getlist("emp_id")
        for eid in emp_ids:
            status = request.form.get(f"status_{eid}", "Present")
            remarks = request.form.get(f"remarks_{eid}", "").strip()
            conn.execute("""
                INSERT INTO attendance (employee_id, att_date, status, remarks, marked_by)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(employee_id, att_date)
                DO UPDATE SET status=excluded.status, remarks=excluded.remarks, marked_by=excluded.marked_by
            """, (eid, att_date, status, remarks, session.get("user_name")))
        conn.commit()
        flash(f"Attendance for {att_date} saved permanently!", "success")
        selected_date = att_date

    emp_list = conn.execute("SELECT * FROM employees WHERE status='Active' ORDER BY emp_code").fetchall()
    att_rows = conn.execute("SELECT * FROM attendance WHERE att_date = ?", (selected_date,)).fetchall()
    att_map = {row["employee_id"]: row for row in att_rows}

    history = conn.execute("""
        SELECT att_date,
               SUM(CASE WHEN status='Present' THEN 1 ELSE 0 END) as present_cnt,
               SUM(CASE WHEN status='Absent' THEN 1 ELSE 0 END) as absent_cnt,
               SUM(CASE WHEN status='Half-Day' THEN 1 ELSE 0 END) as half_cnt,
               SUM(CASE WHEN status='Leave' THEN 1 ELSE 0 END) as leave_cnt
        FROM attendance
        GROUP BY att_date
        ORDER BY att_date DESC
        LIMIT 15
    """).fetchall()

    conn.close()
    return render_template(
        "attendance.html",
        employees=emp_list,
        att_map=att_map,
        selected_date=selected_date,
        history=history
    )


@app.route("/payroll", methods=["GET", "POST"])
@login_required
@staff_required
def payroll():
    selected_month = request.args.get("month", datetime.now().strftime("%Y-%m"))
    conn = get_db()

    if request.method == "POST":
        action = request.form.get("action")

        if action == "generate":
            month_year = request.form.get("month_year", selected_month)
            working_days = int(request.form.get("working_days", 26))
            employees_list = conn.execute("SELECT * FROM employees WHERE status='Active'").fetchall()

            for emp in employees_list:
                existing_paid = conn.execute(
                    "SELECT id FROM payroll WHERE employee_id = ? AND month_year = ? AND payment_status = 'Paid'",
                    (emp["id"], month_year)
                ).fetchone()
                if existing_paid:
                    continue

                att_records = conn.execute(
                    "SELECT status FROM attendance WHERE employee_id = ? AND att_date LIKE ?",
                    (emp["id"], f"{month_year}%")
                ).fetchall()

                if att_records:
                    present_days = sum(
                        1.0 if r["status"] == "Present" else (0.5 if r["status"] == "Half-Day" else 0.0)
                        for r in att_records
                    )
                else:
                    present_days = float(working_days)

                basic = float(emp["basic_salary"])
                hra_pct = float(emp["hra_percent"] or 20.0) / 100.0
                pf_pct = float(emp["pf_percent"] or 5.0) / 100.0
                spec_allow = float(emp["special_allowance"] or 0.0)

                ratio = min(present_days / working_days, 1.0) if working_days > 0 else 1.0
                earned_basic = round(basic * ratio, 2)
                hra = round(earned_basic * hra_pct, 2)
                earned_special = round(spec_allow * ratio, 2)
                deductions = round(earned_basic * pf_pct, 2)
                net_salary = round(earned_basic + hra + earned_special - deductions, 2)

                conn.execute("""
                    INSERT INTO payroll (
                        employee_id, month_year, working_days, present_days,
                        basic_salary, hra_allowance, special_allowance, bonus,
                        deductions, net_salary, payment_status, generated_by
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, 0.0, ?, ?, 'Pending', ?)
                    ON CONFLICT(employee_id, month_year)
                    DO UPDATE SET working_days=excluded.working_days, present_days=excluded.present_days,
                                  basic_salary=excluded.basic_salary, hra_allowance=excluded.hra_allowance,
                                  special_allowance=excluded.special_allowance, deductions=excluded.deductions,
                                  net_salary=excluded.net_salary, generated_by=excluded.generated_by
                """, (
                    emp["id"], month_year, working_days, present_days,
                    earned_basic, hra, earned_special, deductions, net_salary, session.get("user_name")
                ))

            conn.commit()
            selected_month = month_year
            flash(f"Monthly salaries for {month_year} calculated & saved!", "success")

        elif action == "edit_salary":
            payroll_id = request.form.get("payroll_id")
            present_days = float(request.form.get("present_days", 26))
            basic_salary = float(request.form.get("basic_salary", 0))
            hra_allowance = float(request.form.get("hra_allowance", 0))
            special_allowance = float(request.form.get("special_allowance", 0))
            bonus = float(request.form.get("bonus", 0))
            deductions = float(request.form.get("deductions", 0))
            net_salary = round(basic_salary + hra_allowance + special_allowance + bonus - deductions, 2)

            conn.execute("""
                UPDATE payroll
                SET present_days=?, basic_salary=?, hra_allowance=?, special_allowance=?,
                    bonus=?, deductions=?, net_salary=?
                WHERE id=? AND payment_status != 'Paid'
            """, (present_days, basic_salary, hra_allowance, special_allowance, bonus, deductions, net_salary, payroll_id))
            conn.commit()
            flash("Monthly salary updated!", "success")

        elif action == "mark_paid":
            payroll_id = request.form.get("payroll_id")
            paid_today = date.today().isoformat()
            receipt_no = f"VVITU-{datetime.now().strftime('%Y%m%d')}-{int(payroll_id):04d}"
            paid_by = session.get("user_name")

            conn.execute(
                "UPDATE payroll SET payment_status = 'Paid', paid_date = ?, paid_by = ?, receipt_no = ? WHERE id = ?",
                (paid_today, paid_by, receipt_no, payroll_id)
            )
            conn.commit()

            full_rec = conn.execute("""
                SELECT p.*, e.emp_code, e.full_name, e.department, e.emp_role, e.bank_account, e.email
                FROM payroll p JOIN employees e ON p.employee_id = e.id
                WHERE p.id = ?
            """, (payroll_id,)).fetchone()

            if full_rec:
                slip_filename = save_permanent_payslip_file(full_rec)
                snapshot_json = json.dumps(dict(full_rec))
                conn.execute(
                    "UPDATE payroll SET saved_slip_file = ?, slip_snapshot = ? WHERE id = ?",
                    (slip_filename, snapshot_json, payroll_id)
                )
                conn.commit()
                flash(f"Salary Paid! Receipt {receipt_no} permanently saved for {full_rec['email']}.", "success")

    payroll_rows = conn.execute("""
        SELECT p.*, e.emp_code, e.full_name, e.department, e.emp_role, e.bank_account, e.email, e.avatar_url
        FROM payroll p
        JOIN employees e ON p.employee_id = e.id
        WHERE p.month_year = ?
        ORDER BY e.emp_code
    """, (selected_month,)).fetchall()

    all_employees = conn.execute("SELECT * FROM employees ORDER BY emp_code").fetchall()
    saved_months = conn.execute(
        "SELECT month_year, COUNT(*) as emp_cnt, SUM(net_salary) as total_paid, SUM(CASE WHEN payment_status='Paid' THEN 1 ELSE 0 END) as slips_saved FROM payroll GROUP BY month_year ORDER BY month_year DESC"
    ).fetchall()

    conn.close()
    return render_template(
        "payroll.html",
        payroll_rows=payroll_rows,
        selected_month=selected_month,
        all_employees=all_employees,
        saved_months=saved_months
    )


@app.route("/payslip/<int:payroll_id>")
@login_required
@staff_required
def payslip(payroll_id):
    conn = get_db()
    record = conn.execute("""
        SELECT p.*, e.emp_code, e.full_name, e.department, e.emp_role, e.bank_account, e.email, e.phone, e.joining_date, e.avatar_url
        FROM payroll p
        JOIN employees e ON p.employee_id = e.id
        WHERE p.id = ?
    """, (payroll_id,)).fetchone()
    conn.close()
    if not record:
        flash("Payslip not found.", "danger")
        return redirect(url_for("payroll"))
    return render_template("payslip.html", p=record, is_employee_view=False)


@app.route("/export/<string:data_type>")
@login_required
@staff_required
def export_csv(data_type):
    conn = get_db()
    output = io.StringIO()
    writer = csv.writer(output)

    if data_type == "employees":
        rows = conn.execute("SELECT emp_code, full_name, email, phone, department, emp_role, employment_type, joining_date, basic_salary, hra_percent, special_allowance, pf_percent, bank_account, status FROM employees").fetchall()
        writer.writerow(["VVITU ID", "Name", "Email", "Phone", "Department", "Role", "Type", "Joining Date", "Basic Salary", "HRA %", "Special Allowance", "PF %", "Bank Account", "Status"])
        for r in rows:
            writer.writerow(list(r))
        filename = "vvitu_employees_backup.csv"

    elif data_type == "payroll":
        rows = conn.execute("""
            SELECT p.month_year, p.receipt_no, e.emp_code, e.full_name, e.email, e.department, e.emp_role, p.working_days, p.present_days,
                   p.basic_salary, p.hra_allowance, p.special_allowance, p.bonus, p.deductions, p.net_salary, p.payment_status, p.paid_date
            FROM payroll p JOIN employees e ON p.employee_id = e.id
            ORDER BY p.month_year DESC, e.emp_code
        """).fetchall()
        writer.writerow(["Month", "Receipt No", "VVITU ID", "Name", "Email", "Department", "Role", "Working Days", "Present Days", "Earned Basic", "HRA", "Special Allowance", "Bonus", "Deductions", "Net Salary", "Status", "Paid Date"])
        for r in rows:
            writer.writerow(list(r))
        filename = "vvitu_monthly_payroll.csv"

    else:
        rows = conn.execute("""
            SELECT a.att_date, e.emp_code, e.full_name, e.department, a.status, a.remarks, a.marked_by
            FROM attendance a JOIN employees e ON a.employee_id = e.id
            ORDER BY a.att_date DESC
        """).fetchall()
        writer.writerow(["Date", "VVITU ID", "Name", "Department", "Status", "Remarks", "Marked By"])
        for r in rows:
            writer.writerow(list(r))
        filename = "vvitu_attendance_logs.csv"

    conn.close()
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )


if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="127.0.0.1", port=5000)
