import sys
sys.dont_write_bytecode = True
from flask import Flask, session, request, redirect, url_for
from config import Config
from waitress import serve
from models.user_model import db, User
from models.firefighter_model import Firefighter
from models.item_model import Item
from controllers.dashboard_controller import dashboard_bp
from controllers.user_controller import user_bp
from controllers.firefighter_controller import firefighter_bp
from controllers.item_controller import item_bp
from controllers.notification_controller import notification_bp
from controllers.mobile_controller import mobile_bp
from controllers.catalog_controller import catalog_bp
from controllers.log_controller import log_bp


def create_app():
    app = Flask(__name__, static_url_path="/Sp/static")
    app.config.from_object(Config)
    db.init_app(app)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(firefighter_bp)
    app.register_blueprint(item_bp)
    app.register_blueprint(notification_bp)
    app.register_blueprint(mobile_bp)
    app.register_blueprint(catalog_bp)
    app.register_blueprint(log_bp)

    @app.context_processor
    def inject_user():
        from services.user_service import UserService
        cas_username = session.get("CAS_USERNAME")
        user = None
        if cas_username:
            user = UserService.get_user_by_cas_username(cas_username)
        return {"user": user, "userCAS": user}

    @app.before_request
    def redirect_mobile():
        # Nie przekierowuj tych ścieżek nigdy
        skip_prefixes = ["/Sp/mobile", "/Sp/static", "/Sp/api", "/Sp/cas", "/Sp/dev-login"]
        if any(request.path.startswith(p) for p in skip_prefixes):
            return

        # Użytkownik kliknął "pełny widok" – zapisz w sesji i nie przekierowuj
        if request.args.get("desktop") == "1":
            session["force_desktop"] = True
            return

        # Użytkownik kliknął "widok mobilny" – wyczyść flagę i przekieruj na mobile
        if request.args.get("mobile") == "1":
            session.pop("force_desktop", None)
            return redirect(url_for("mobile_controller.mobile_dashboard"))

        # Jeśli użytkownik wybrał desktop – nie przekierowuj
        if session.get("force_desktop"):
            return

        # Wykryj urządzenie mobilne i przekieruj
        ua = request.headers.get("User-Agent", "").lower()
        mobile_keywords = ["android", "iphone", "ipad", "mobile", "tablet"]
        if any(kw in ua for kw in mobile_keywords):
            return redirect(url_for("mobile_controller.mobile_dashboard"))

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=True)