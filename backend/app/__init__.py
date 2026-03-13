from flask import Flask, jsonify, render_template
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect

from .config import get_config
from .models import db

csrf = CSRFProtect()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message_category = "error"


def create_app(config_object=None):
    app = Flask(__name__, instance_relative_config=False)

    if config_object is None:
        app.config.from_object(get_config())
    else:
        app.config.from_object(config_object)

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    login_manager.init_app(app)

    from .routes.admin import admin_bp
    from .routes.auth import auth_bp
    from .routes.client import client_bp
    from .routes.public import public_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(client_bp)
    app.register_blueprint(admin_bp)

    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    @app.cli.command("init-db")
    def init_db_command():
        """Create all database tables."""
        db.create_all()
        print("Database initialized.")

    @app.shell_context_processor
    def shell_context():
        from .models import (
            AuditLog,
            ClientProfile,
            ConsultationBooking,
            ContactSubmission,
            Document,
            Filing,
            NewsletterSubscriber,
            SiteUpdate,
            User,
        )

        return {
            "db": db,
            "User": User,
            "ClientProfile": ClientProfile,
            "Filing": Filing,
            "Document": Document,
            "AuditLog": AuditLog,
            "ContactSubmission": ContactSubmission,
            "ConsultationBooking": ConsultationBooking,
            "NewsletterSubscriber": NewsletterSubscriber,
            "SiteUpdate": SiteUpdate,
        }

    @app.route("/health")
    def health_check():
        return jsonify({"status": "ok"}), 200

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(413)
    def payload_too_large(_error):
        return render_template("errors/413.html"), 413

    @app.errorhandler(500)
    def internal_error(_error):
        db.session.rollback()
        return render_template("errors/500.html"), 500

    @app.after_request
    def apply_security_headers(response):
        if not app.config.get("ENABLE_SECURITY_HEADERS", True):
            return response

        response.headers.setdefault(
            "X-Content-Type-Options", app.config.get("X_CONTENT_TYPE_OPTIONS", "nosniff")
        )
        response.headers.setdefault("X-Frame-Options", app.config.get("X_FRAME_OPTIONS", "DENY"))
        response.headers.setdefault(
            "Referrer-Policy", app.config.get("REFERRER_POLICY", "strict-origin-when-cross-origin")
        )
        response.headers.setdefault(
            "Content-Security-Policy",
            app.config.get(
                "CONTENT_SECURITY_POLICY",
                "default-src 'self'; img-src 'self' data: https:; style-src 'self' 'unsafe-inline'; script-src 'self'",
            ),
        )

        # Added for defense-in-depth in modern browsers.
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        return response

    return app
