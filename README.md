# Attendance App

A small Flask application for tracking attendance for the "Practical Digital Marketing" program.

## Features

- Manage groups, students, class days
- Take attendance and view scores
- CSV export of scores
- Simple password based login

## Local Development

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export ADMIN_PASSWORD=admin123
flask --app app run
```

The app uses SQLite by default and creates `instance/app.db` automatically.

## Docker

```bash
docker build -t attendance-app .
docker run -p 8080:8080 -e ADMIN_PASSWORD=admin123 attendance-app
```

## Fly.io Deployment

1. Install [flyctl](https://fly.io/docs/flyctl/).
2. Create an app and Postgres instance if needed.
3. Set secrets:
   ```bash
   fly secrets set ADMIN_PASSWORD=yourpassword
   fly secrets set DATABASE_URL=postgresql://...
   ```
4. Add GitHub repository secrets `FLY_API_TOKEN`, `ADMIN_PASSWORD`, `DATABASE_URL`.
5. Push to `main` to trigger deployment.

## Usage

1. Log in using the password.
2. Create a group with start and end dates.
3. Add students and class days.
4. Record attendance and view scores or download the CSV export.
