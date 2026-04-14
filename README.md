# 🗂️ TaskAPI — Secure REST API with JWT & Role-Based Access

A production-ready Flask REST API featuring user authentication, role-based access control (RBAC), and full task CRUD — with a React frontend.

---

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- pip

### 1. Clone & install

```bash
git clone https://github.com/YOUR_USERNAME/taskapi.git
cd taskapi
pip install -r requirements.txt
```

### 2. Run the backend

```bash
python app.py
```

Server starts at `http://127.0.0.1:5000`

### 3. Open the frontend

Open `frontend/index.html` in your browser (double-click or use Live Server in VS Code).

> **Default admin credentials:** `admin` / `admin123`

---

## 📁 Project Structure

```
taskapi/
├── app.py                  # Main Flask application
├── requirements.txt        # Python dependencies
├── frontend/
│   └── index.html          # React frontend (single file, CDN-based)
├── docs/
│   └── openapi.json        # OpenAPI 3.0 / Swagger spec
└── README.md
```

---

## 🔑 Authentication

All protected routes require a JWT in the Authorization header:

```
Authorization: Bearer <your_token>
```

Tokens are issued on login and expire in **2 hours**.

---

## 📡 API Reference (`/api/v1`)

### Auth

| Method | Endpoint    | Auth | Description              |
|--------|-------------|------|--------------------------|
| POST   | /signup     | ❌   | Register new user        |
| POST   | /login      | ❌   | Login, receive JWT       |
| GET    | /me         | ✅   | Get current user profile |

### Tasks

| Method | Endpoint          | Auth | Description                         |
|--------|-------------------|------|-------------------------------------|
| GET    | /tasks            | ✅   | Get tasks (admin sees all)          |
| POST   | /tasks            | ✅   | Create a task                       |
| GET    | /tasks/:id        | ✅   | Get single task                     |
| PUT    | /tasks/:id        | ✅   | Update task                         |
| DELETE | /tasks/:id        | ✅   | Delete task                         |

### Admin Only

| Method | Endpoint              | Auth  | Description          |
|--------|-----------------------|-------|----------------------|
| GET    | /admin/users          | Admin | List all users       |
| DELETE | /admin/users/:id      | Admin | Delete user + tasks  |

---

## 🔒 Security Practices

- **Password hashing** via `werkzeug` (PBKDF2-SHA256)
- **JWT** with expiry and role claim embedded
- **Rate limiting** on login: 5 failed attempts → 5-minute lockout
- **Input sanitization** via `bleach` on all user-submitted strings
- **Authorization checks** on every task endpoint — users can only access their own data
- **Proper HTTP status codes** (400, 401, 403, 404, 409, 429, 500)

---

## 👥 Roles

| Role  | Can Do                                                  |
|-------|---------------------------------------------------------|
| user  | CRUD on own tasks                                       |
| admin | CRUD on ALL tasks, view/delete all users                |

---

## 📄 API Documentation

The full OpenAPI 3.0 spec is in `docs/openapi.json`.

**To view interactively:**
1. Go to [https://editor.swagger.io](https://editor.swagger.io)
2. Click **File → Import file** and upload `docs/openapi.json`

---

## 📦 Database Schema

```
User
├── id          INTEGER PK
├── username    VARCHAR(100) UNIQUE NOT NULL
├── password    VARCHAR(200) NOT NULL  -- bcrypt hashed
└── role        VARCHAR(20) DEFAULT 'user'

Task
├── id          INTEGER PK
├── title       VARCHAR(200) NOT NULL
├── description VARCHAR(500)
├── completed   BOOLEAN DEFAULT false
├── user_id     INTEGER FK → User.id
└── created_at  DATETIME DEFAULT now()
```

---

## 📈 Scalability Notes

### Current Architecture
- SQLite for local dev → swap to **PostgreSQL** for production (change `SQLALCHEMY_DATABASE_URI`)
- In-memory login rate limiting → replace with **Redis** for multi-instance support

### Scaling Path

| Concern | Solution |
|---|---|
| Database | PostgreSQL + connection pooling (pgBouncer) |
| Caching | Redis (rate limiting, session caching) |
| Multiple instances | Stateless JWT means horizontal scaling works out of the box |
| Microservices | Auth service and Task service can be split with an API Gateway |
| Load balancing | Nginx or AWS ALB in front of Gunicorn workers |
| Container deployment | Dockerize with `docker-compose` (Flask + Postgres + Redis) |
| Background jobs | Celery + Redis for async tasks (email, notifications) |
| Monitoring | Sentry for error tracking, Prometheus + Grafana for metrics |

### Production Checklist
- [ ] Replace `SECRET_KEY` with env variable (`os.environ.get("SECRET_KEY")`)
- [ ] Switch SQLite → PostgreSQL
- [ ] Run with `gunicorn app:app -w 4`
- [ ] Add HTTPS (Let's Encrypt / AWS ACM)
- [ ] Set `debug=False`
- [ ] Add request logging middleware

---

## 🛠️ Built With

- **Flask** — web framework
- **Flask-SQLAlchemy** — ORM
- **Flask-CORS** — cross-origin resource sharing
- **PyJWT** — JWT tokens
- **Werkzeug** — password hashing
- **Bleach** — HTML sanitization
- **React** (CDN) — frontend UI