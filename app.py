from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import datetime
import time
import bleach
from functools import wraps

app = Flask(__name__)
CORS(app)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tasks.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = "change-this-in-production-use-env-variable"

login_attempts = {}
db = SQLAlchemy(app)


# ==================== MODELS ====================

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="user")  # "user" or "admin"
    tasks = db.relationship('Task', backref='owner', lazy=True)

    def to_dict(self):
        return {"id": self.id, "username": self.username, "role": self.role}


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.String(500), default="")
    completed = db.Column(db.Boolean, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "completed": self.completed,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat()
        }


with app.app_context():
    db.create_all()
    # Create default admin if not exists
    if not User.query.filter_by(username="admin").first():
        admin = User(
            username="admin",
            password=generate_password_hash("admin123"),
            role="admin"
        )
        db.session.add(admin)
        db.session.commit()


# ==================== AUTH DECORATORS ====================

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Authorization token required"}), 401
        try:
            token = auth_header.split(" ")[1]
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            request.user_id = data["user_id"]
            request.user_role = data["role"]
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Authorization token required"}), 401
        try:
            token = auth_header.split(" ")[1]
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            if data.get("role") != "admin":
                return jsonify({"error": "Admin access required"}), 403
            request.user_id = data["user_id"]
            request.user_role = data["role"]
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401
        return f(*args, **kwargs)
    return decorated


# ==================== AUTH ROUTES (/api/v1) ====================

@app.route("/api/v1/signup", methods=["POST"])
def signup():
    """
    Register a new user.
    Body: { "username": str, "password": str, "role": "user"|"admin" (optional) }
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    username = bleach.clean(data.get("username", "").strip())
    password = data.get("password", "")
    role = data.get("role", "user")

    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400

    if len(username) < 3 or len(username) > 50:
        return jsonify({"error": "Username must be 3–50 characters"}), 400

    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    if role not in ["user", "admin"]:
        role = "user"

    if User.query.filter_by(username=username).first():
        return jsonify({"error": "Username already taken"}), 409

    new_user = User(
        username=username,
        password=generate_password_hash(password),
        role=role
    )
    db.session.add(new_user)
    db.session.commit()

    return jsonify({"message": "User created successfully", "user": new_user.to_dict()}), 201


@app.route("/api/v1/login", methods=["POST"])
def login():
    """
    Login and receive a JWT token.
    Body: { "username": str, "password": str }
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400

    # Rate limiting
    attempt = login_attempts.get(username, {"count": 0, "blocked_until": 0})
    if attempt["count"] >= 5 and time.time() < attempt["blocked_until"]:
        wait = int(attempt["blocked_until"] - time.time())
        return jsonify({"error": f"Too many attempts. Try again in {wait}s"}), 429

    user = User.query.filter_by(username=username).first()

    if not user or not check_password_hash(user.password, password):
        attempt["count"] += 1
        if attempt["count"] >= 5:
            attempt["blocked_until"] = time.time() + 300
        login_attempts[username] = attempt
        return jsonify({"error": "Invalid credentials"}), 401

    login_attempts.pop(username, None)

    token = jwt.encode({
        "user_id": user.id,
        "role": user.role,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=2)
    }, app.config['SECRET_KEY'], algorithm="HS256")

    return jsonify({
        "message": "Login successful",
        "token": token,
        "user": user.to_dict()
    }), 200


@app.route("/api/v1/me", methods=["GET"])
@login_required
def get_me():
    """Get current user profile."""
    user = User.query.get(request.user_id)
    return jsonify({"user": user.to_dict()}), 200


# ==================== TASK ROUTES (/api/v1/tasks) ====================

@app.route("/api/v1/tasks", methods=["POST"])
@login_required
def create_task():
    """
    Create a new task for the logged-in user.
    Body: { "title": str, "description": str (optional) }
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    title = bleach.clean(data.get("title", "").strip())
    description = bleach.clean(data.get("description", "").strip())

    if not title:
        return jsonify({"error": "Title is required"}), 400
    if len(title) > 200:
        return jsonify({"error": "Title too long (max 200 chars)"}), 400

    task = Task(title=title, description=description, user_id=request.user_id)
    db.session.add(task)
    db.session.commit()

    return jsonify({"message": "Task created", "task": task.to_dict()}), 201


@app.route("/api/v1/tasks", methods=["GET"])
@login_required
def get_tasks():
    """Get all tasks for the current user. Admins can see all tasks."""
    if request.user_role == "admin":
        tasks = Task.query.all()
    else:
        tasks = Task.query.filter_by(user_id=request.user_id).all()

    return jsonify({"tasks": [t.to_dict() for t in tasks]}), 200


@app.route("/api/v1/tasks/<int:task_id>", methods=["GET"])
@login_required
def get_task(task_id):
    """Get a single task by ID."""
    task = Task.query.get(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404
    if task.user_id != request.user_id and request.user_role != "admin":
        return jsonify({"error": "Unauthorized"}), 403
    return jsonify({"task": task.to_dict()}), 200


@app.route("/api/v1/tasks/<int:task_id>", methods=["PUT"])
@login_required
def update_task(task_id):
    """
    Update a task.
    Body: { "title": str (opt), "description": str (opt), "completed": bool (opt) }
    """
    task = Task.query.get(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404
    if task.user_id != request.user_id and request.user_role != "admin":
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    if "title" in data:
        title = bleach.clean(data["title"].strip())
        if not title or len(title) > 200:
            return jsonify({"error": "Invalid title"}), 400
        task.title = title

    if "description" in data:
        task.description = bleach.clean(data["description"].strip())

    if "completed" in data:
        if not isinstance(data["completed"], bool):
            return jsonify({"error": "completed must be boolean"}), 400
        task.completed = data["completed"]

    db.session.commit()
    return jsonify({"message": "Task updated", "task": task.to_dict()}), 200


@app.route("/api/v1/tasks/<int:task_id>", methods=["DELETE"])
@login_required
def delete_task(task_id):
    """Delete a task."""
    task = Task.query.get(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404
    if task.user_id != request.user_id and request.user_role != "admin":
        return jsonify({"error": "Unauthorized"}), 403

    db.session.delete(task)
    db.session.commit()
    return jsonify({"message": "Task deleted"}), 200


# ==================== ADMIN ROUTES ====================

@app.route("/api/v1/admin/users", methods=["GET"])
@admin_required
def get_all_users():
    """Admin only: list all users."""
    users = User.query.all()
    return jsonify({"users": [u.to_dict() for u in users]}), 200


@app.route("/api/v1/admin/users/<int:user_id>", methods=["DELETE"])
@admin_required
def delete_user(user_id):
    """Admin only: delete a user and their tasks."""
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    if user.id == request.user_id:
        return jsonify({"error": "Cannot delete yourself"}), 400

    Task.query.filter_by(user_id=user_id).delete()
    db.session.delete(user)
    db.session.commit()
    return jsonify({"message": f"User {user.username} deleted"}), 200


# ==================== HEALTH CHECK ====================

@app.route("/api/v1/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "version": "1.0"}), 200


# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({"error": "Method not allowed"}), 405

@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    app.run(debug=True)