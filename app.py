import hmac
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path

import bcrypt
import jwt
import mysql.connector
from dotenv import load_dotenv
from flask import Flask, current_app, g, jsonify, request, send_from_directory
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from mysql.connector.pooling import MySQLConnectionPool
from werkzeug.exceptions import HTTPException


ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

secret_key = os.getenv("SECRET_KEY", "")
if len(secret_key) < 32:
    raise RuntimeError("SECRET_KEY must be configured with at least 32 characters.")

COOKIE_NAME = "student_portal_token"
CSRF_COOKIE_NAME = "XSRF-TOKEN"
CSRF_HEADER_NAME = "X-XSRF-TOKEN"
COOKIE_MAX_AGE = 8 * 60 * 60
BUILD_DIR = ROOT / "dist" / "portal" / "browser"

app = Flask(__name__, static_folder=None)
app.config["SECRET_KEY"] = secret_key
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Strict"
app.config["SESSION_COOKIE_SECURE"] = os.getenv("FLASK_DEBUG", "0") != "1"

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri=os.getenv("RATELIMIT_STORAGE_URI", "memory://"),
)

database_pool = MySQLConnectionPool(
    pool_name="student_portal",
    pool_size=5,
    host=os.getenv("DB_HOST", "127.0.0.1"),
    port=int(os.getenv("DB_PORT", "3306")),
    user=os.getenv("DB_USER", "root"),
    password=os.getenv("DB_PASSWORD", ""),
    database=os.getenv("DB_NAME", "college_portal"),
)


def get_connection():
    return database_pool.get_connection()


def run_query(sql, parameters=(), fetch=False):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(sql, parameters)
        if fetch:
            return cursor.fetchall()
        connection.commit()
        return cursor.rowcount
    finally:
        cursor.close()
        connection.close()


def student_required(handler):
    @wraps(handler)
    def wrapped(*args, **kwargs):
        token = request.cookies.get(COOKIE_NAME)
        if not token:
            return jsonify(error="Please sign in to continue."), 401
        try:
            payload = jwt.decode(token, secret_key, algorithms=["HS256"])
            student_id = int(payload["sub"])
            if student_id < 1:
                raise ValueError("Invalid student ID.")
        except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
            response = jsonify(error="Your session has expired. Please sign in again.")
            response.delete_cookie(COOKIE_NAME, path="/", samesite="Strict")
            return response, 401

        g.student_id = student_id
        return handler(*args, **kwargs)

    return wrapped


def set_login_cookie(response, student_id):
    token = jwt.encode(
        {
            "sub": str(student_id),
            "exp": datetime.now(timezone.utc) + timedelta(seconds=COOKIE_MAX_AGE),
        },
        secret_key,
        algorithm="HS256",
    )
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        secure=app.config["SESSION_COOKIE_SECURE"],
        samesite="Strict",
        path="/",
    )


@app.post("/api/auth/login")
@limiter.limit("10 per 15 minutes")
def login():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Enter your EMP ID and password."), 400
    emp_id = data.get("empId")
    password = data.get("password")
    if (
        not isinstance(emp_id, str)
        or not isinstance(password, str)
        or not emp_id.strip()
        or len(emp_id) > 50
        or not password
        or len(password) > 200
    ):
        return jsonify(error="Enter your EMP ID and password."), 400

    rows = run_query(
        "SELECT id, password_hash FROM students WHERE emp_id = %s LIMIT 1",
        (emp_id.strip(),),
        fetch=True,
    )
    student = rows[0] if rows else None
    password_matches = student is not None and bcrypt.checkpw(
        password.encode("utf-8"),
        student["password_hash"].encode("utf-8"),
    )
    if not password_matches:
        return jsonify(error="EMP ID or password is incorrect."), 401

    response = jsonify(message="Signed in successfully.")
    set_login_cookie(response, student["id"])
    return response


@app.post("/api/auth/logout")
def logout():
    response = jsonify(message="Signed out successfully.")
    response.delete_cookie(COOKIE_NAME, path="/", samesite="Strict")
    return response


@app.get("/api/student/me")
@student_required
def get_student():
    rows = run_query(
        """
        SELECT emp_id AS empId, student_name AS studentName, department, program,
               academic_year AS academicYear, email, phone, address
        FROM students WHERE id = %s LIMIT 1
        """,
        (g.student_id,),
        fetch=True,
    )
    if not rows:
        response = jsonify(error="Student account was not found. Please sign in again.")
        response.delete_cookie(COOKIE_NAME, path="/", samesite="Strict")
        return response, 401
    return jsonify(student=rows[0])


@app.put("/api/student/profile")
@student_required
def update_profile():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Enter valid profile details."), 400
    fields = ("email", "phone", "address")
    values = {}
    for field in fields:
        value = data.get(field)
        if not isinstance(value, str):
            return jsonify(error=f"Enter a valid {field}."), 400
        values[field] = value.strip()

    if (
        len(values["email"]) > 254
        or len(values["phone"]) > 30
        or len(values["address"]) > 500
    ):
        return jsonify(error="One or more profile fields are too long."), 400
    email = values["email"]
    if email and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        return jsonify(error="Enter a valid email address."), 400

    updated = run_query(
        "UPDATE students SET email = %s, phone = %s, address = %s WHERE id = %s",
        (values["email"], values["phone"], values["address"], g.student_id),
    )
    if not updated:
        exists = run_query(
            "SELECT id FROM students WHERE id = %s LIMIT 1",
            (g.student_id,),
            fetch=True,
        )
        if not exists:
            return jsonify(error="Student account was not found."), 404
    return jsonify(message="Profile updated successfully.")


@app.get("/api/student/results")
@student_required
def get_results():
    rows = run_query(
        """
        SELECT course_code AS courseCode, course_name AS courseName, semester,
               academic_year AS academicYear, grade, published_at AS publishedAt
        FROM results
        WHERE student_id = %s
        ORDER BY published_at DESC, course_code ASC
        """,
        (g.student_id,),
        fetch=True,
    )
    return jsonify(results=rows)


@app.get("/api/health")
def health():
    try:
        rows = run_query("SELECT 1 AS healthy", fetch=True)
    except mysql.connector.Error:
        current_app.logger.exception("Database health check failed.")
        return jsonify(status="error", database="unavailable"), 503
    return jsonify(status="ok" if rows else "error")


@app.errorhandler(429)
def too_many_requests(_error):
    return jsonify(error="Too many login attempts. Please try again later."), 429


@app.before_request
def validate_csrf_token():
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return None
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME, "")
    header_token = request.headers.get(CSRF_HEADER_NAME, "")
    if not cookie_token or not header_token or not hmac.compare_digest(cookie_token, header_token):
        return jsonify(error="Your request could not be verified. Refresh the page and try again."), 403
    return None


@app.after_request
def issue_csrf_cookie(response):
    if not request.cookies.get(CSRF_COOKIE_NAME):
        response.set_cookie(
            CSRF_COOKIE_NAME,
            secrets.token_urlsafe(32),
            httponly=False,
            secure=app.config["SESSION_COOKIE_SECURE"],
            samesite="Strict",
            path="/",
        )
    return response


@app.errorhandler(Exception)
def handle_unexpected_error(error):
    if isinstance(error, HTTPException):
        return jsonify(error=error.description), error.code
    current_app.logger.exception("Request failed.")
    return jsonify(error="An unexpected server error occurred."), 500


@app.get("/", defaults={"path": ""})
@app.get("/<path:path>")
def angular_app(path):
    if path == "api" or path.startswith("api/"):
        return jsonify(error="API endpoint not found."), 404
    requested_file = BUILD_DIR / path
    if path and requested_file.is_file():
        return send_from_directory(BUILD_DIR, path)
    index_path = BUILD_DIR / "index.html"
    if not index_path.is_file():
        return jsonify(error="Angular frontend is not built. Run npm run build."), 503
    return send_from_directory(BUILD_DIR, "index.html")


if __name__ == "__main__":
    app.run(
        host=os.getenv("FLASK_HOST", "127.0.0.1"),
        port=int(os.getenv("FLASK_PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG", "0") == "1",
    )
