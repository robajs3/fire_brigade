import os
os.environ["PATH"] = r"D:\Programs\nwrfc\nwrfcsdk\lib;" + os.environ.get("PATH", "")

import sys
sys.dont_write_bytecode = True

from flask import Flask, session, request, redirect, url_for
from config import Config

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

from flask_apscheduler import APScheduler

from flask_jwt_extended import JWTManager
from controllers.auth_mobile_controller import auth_mobile_bp

scheduler = APScheduler()


def create_app():
    app = Flask(__name__, static_url_path="/zsr/static")
    app.config.from_object(Config)
    db.init_app(app)
    
    jwt = JWTManager(app)
    app.config["JWT_TOKEN_LOCATION"] = ["cookies"]
    app.config["JWT_COOKIE_SECURE"] = False  # True na HTTPS
    app.config["JWT_COOKIE_CSRF_PROTECT"] = False
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = False  # lub timedelta(hours=8)

    app.register_blueprint(auth_mobile_bp)

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
        skip_prefixes = ["/zsr/mobile", "/zsr/static", "/zsr/api", "/zsr/cas", "/zsr/dev-login"]
        if any(request.path.startswith(p) for p in skip_prefixes):
            return
        if request.args.get("desktop") == "1":
            session["force_desktop"] = True
            return
        if request.args.get("mobile") == "1":
            session.pop("force_desktop", None)
            return redirect(url_for("mobile_controller.mobile_dashboard"))
        if session.get("force_desktop"):
            return
        ua = request.headers.get("User-Agent", "").lower()
        mobile_keywords = ["android", "iphone", "ipad", "mobile", "tablet"]
        if any(kw in ua for kw in mobile_keywords):
            return redirect(url_for("mobile_controller.mobile_dashboard"))

    with app.app_context():
        db.create_all()
        # Synchronizacja SAP przy starcie
        try:
            from services.sap_service import SAPService
            result = SAPService.sync_stock_to_catalog()
            print(f"[SAP] Synchronizacja przy starcie: "
                  f"zaktualizowano={result['updated']}, "
                  f"utworzono={result['created']}")
        except Exception as e:
            print(f"[SAP] Pominięto synchronizację przy starcie: {e}")

    # Scheduler – auto-sync co 5 minut
    app.config["SCHEDULER_API_ENABLED"] = False
    scheduler.init_app(app)

    @scheduler.task("interval", id="sap_sync", minutes=5, misfire_grace_time=60)
    def sap_sync_job():
        with app.app_context():
            try:
                from services.sap_service import SAPService
                result = SAPService.sync_stock_to_catalog()
                print(f"[SAP] Auto-sync: {result}")
            except Exception as e:
                print(f"[SAP] Błąd auto-sync: {e}")

    scheduler.start()

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5443, debug=True, ssl_context=("cert.pem", "key.pem"))