import getpass
import os
from pathlib import Path

import bcrypt
import mysql.connector
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def main():
    emp_id = input("EMP ID: ").strip()
    student_name = input("Student name: ").strip()
    password = getpass.getpass("Temporary password: ")
    if not emp_id or len(emp_id) > 50 or not student_name or len(student_name) > 120:
        raise ValueError("Enter a valid EMP ID and student name.")
    if len(password) < 8:
        raise ValueError("Password must contain at least 8 characters.")

    connection = mysql.connector.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "college_portal"),
    )
    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    try:
        cursor = connection.cursor()
        try:
            cursor.execute(
                "INSERT INTO students (emp_id, password_hash, student_name) VALUES (%s, %s, %s)",
                (emp_id, password_hash.decode("utf-8"), student_name),
            )
            connection.commit()
        finally:
            cursor.close()
    finally:
        connection.close()
    print(f"Student account created for EMP ID {emp_id}.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, mysql.connector.Error) as error:
        raise SystemExit(f"Could not create student account: {error}") from error
