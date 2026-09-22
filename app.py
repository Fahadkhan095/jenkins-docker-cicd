import os
from functools import wraps

from flask import Flask, jsonify, redirect, render_template, request, session, url_for

from db import IntegrityError, PLACEHOLDER, get_connection, init_db, insert_employee

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")

# Demo credentials only — replace with a real user store before shipping this.
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("logged_in"):
            if request.path.startswith("/employees"):
                return jsonify({"error": "Unauthorized"}), 401
            return redirect(url_for("login_page"))
        return view(*args, **kwargs)

    return wrapped


def row_to_dict(row):
    return {"id": row["id"], "name": row["name"], "role": row["role"], "department": row["department"], "email": row["email"]}


# ---------- Pages ----------

@app.route("/")
def index():
    if session.get("logged_in"):
        return redirect(url_for("dashboard"))
    return redirect(url_for("login_page"))


@app.route("/login", methods=["GET"])
def login_page():
    if session.get("logged_in"):
        return redirect(url_for("dashboard"))
    return render_template("login.html")


@app.route("/login", methods=["POST"])
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        session["logged_in"] = True
        session["username"] = username
        return redirect(url_for("dashboard"))
    return render_template("login.html", error="That username or password isn't right."), 401


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))


@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", username=session.get("username"))


# ---------- Health check ----------

@app.route("/health")
def health():
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        conn.close()
        db_status = "connected"
        status_code = 200
    except Exception as exc:  # noqa: BLE001
        db_status = f"error: {exc}"
        status_code = 503
    return jsonify({"status": "ok" if status_code == 200 else "error", "database": db_status}), status_code


# ---------- Employee API ----------

def _validate_payload(data):
    fields = ["name", "role", "department", "email"]
    missing = [f for f in fields if not str(data.get(f, "")).strip()]
    if missing:
        return f"Missing required field(s): {', '.join(missing)}"
    email = data["email"].strip()
    if "@" not in email or "." not in email.split("@")[-1]:
        return "Enter a valid email address."
    return None


@app.route("/employees", methods=["GET"])
@login_required
def list_employees():
    search = request.args.get("search", "").strip()
    conn = get_connection()
    cur = conn.cursor()
    if search:
        like = f"%{search}%"
        match_op = "ILIKE" if PLACEHOLDER == "%s" else "LIKE"  # Postgres: case-insensitive ILIKE; SQLite: LIKE + COLLATE
        collate = "" if PLACEHOLDER == "%s" else " COLLATE NOCASE"
        cur.execute(
            f"""
            SELECT * FROM employees
            WHERE name {match_op} {PLACEHOLDER}{collate} OR role {match_op} {PLACEHOLDER}{collate}
               OR department {match_op} {PLACEHOLDER}{collate} OR email {match_op} {PLACEHOLDER}{collate}
            ORDER BY id
            """,
            (like, like, like, like),
        )
    else:
        cur.execute("SELECT * FROM employees ORDER BY id")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify([row_to_dict(r) for r in rows])


@app.route("/employees", methods=["POST"])
@login_required
def create_employee():
    data = request.get_json(silent=True) or {}
    error = _validate_payload(data)
    if error:
        return jsonify({"error": error}), 400

    conn = get_connection()
    try:
        new_id = insert_employee(
            conn, data["name"].strip(), data["role"].strip(), data["department"].strip(), data["email"].strip()
        )
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM employees WHERE id = {PLACEHOLDER}", (new_id,))
        new_row = cur.fetchone()
        cur.close()
        return jsonify(row_to_dict(new_row)), 201
    except IntegrityError:
        conn.rollback()
        return jsonify({"error": "An employee with that email already exists."}), 409
    finally:
        conn.close()


@app.route("/employees/<int:employee_id>", methods=["PUT"])
@login_required
def update_employee(employee_id):
    data = request.get_json(silent=True) or {}
    error = _validate_payload(data)
    if error:
        return jsonify({"error": error}), 400

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM employees WHERE id = {PLACEHOLDER}", (employee_id,))
    existing = cur.fetchone()
    if not existing:
        cur.close()
        conn.close()
        return jsonify({"error": "Employee not found."}), 404

    try:
        cur.execute(
            f"""UPDATE employees SET name = {PLACEHOLDER}, role = {PLACEHOLDER},
                department = {PLACEHOLDER}, email = {PLACEHOLDER} WHERE id = {PLACEHOLDER}""",
            (data["name"].strip(), data["role"].strip(), data["department"].strip(), data["email"].strip(), employee_id),
        )
        conn.commit()
        cur.execute(f"SELECT * FROM employees WHERE id = {PLACEHOLDER}", (employee_id,))
        updated_row = cur.fetchone()
        return jsonify(row_to_dict(updated_row))
    except IntegrityError:
        conn.rollback()
        return jsonify({"error": "An employee with that email already exists."}), 409
    finally:
        cur.close()
        conn.close()


@app.route("/employees/<int:employee_id>", methods=["DELETE"])
@login_required
def delete_employee(employee_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM employees WHERE id = {PLACEHOLDER}", (employee_id,))
    existing = cur.fetchone()
    if not existing:
        cur.close()
        conn.close()
        return jsonify({"error": "Employee not found."}), 404
    cur.execute(f"DELETE FROM employees WHERE id = {PLACEHOLDER}", (employee_id,))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"message": "Employee deleted."})


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True, port=5000)
