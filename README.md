# College Student Portal

The portal uses a Python/Flask backend, MySQL database, and Angular frontend. Node.js and npm provide the Angular development server and production build. Students sign in with their EMP ID and password, update contact details, and view their own published results.

## Requirements

- Python 3.10 or newer
- Node.js 20.19 or newer
- MySQL 8 or compatible

## Setup

1. Copy `.env.example` to `.env`. Set `DB_PASSWORD` to your MySQL root password and replace `SECRET_KEY` with a random value of at least 32 characters. Keep `.env` private; it is ignored by git.
2. Run `schema.sql` using MySQL to create the database and tables.
3. Install backend dependencies:

   ```powershell
   py -m venv .venv
   .venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

4. Create a student account:

   ```powershell
   python scripts\create_student.py
   ```

   Enter the EMP ID, name, and a temporary password when prompted. The password is stored as a bcrypt hash.
5. Install and start the Angular frontend:

   ```powershell
   npm install
   npm start
   ```

   Open `http://localhost:4200`. The Angular development server proxies `/api` requests to Flask at `http://127.0.0.1:5000`.
6. In a separate terminal with the Python environment activated, start Flask:

   ```powershell
   python app.py
   ```

   For a production build, run `npm run build`, then start Flask. Flask serves the compiled Angular app from `dist/portal/browser`.

The backend defaults to MySQL at `127.0.0.1:3306`, user `root`, database `college_portal`. Configure credentials only in `.env`.

## API

- `POST /api/auth/login` — authenticate with `{ "empId": "...", "password": "..." }`
- `POST /api/auth/logout` — clear the sign-in cookie
- `GET /api/student/me` — retrieve the signed-in student's profile
- `PUT /api/student/profile` — update `email`, `phone`, and `address`
- `GET /api/student/results` — retrieve results for the signed-in student
- `GET /api/health` — database health check

The student ID is taken from the signed-in HTTP-only token, never from browser-supplied profile or result requests. Login attempts are rate limited. Configure `RATELIMIT_STORAGE_URI` to use shared storage such as Redis when deploying multiple backend workers.

To enter results, insert rows into `results` with the matching student table `id`. Students cannot edit academic results through this portal.
