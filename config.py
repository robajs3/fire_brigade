# config.py
import os
import secrets


class Config:
    APPLICATION_ROOT = "/Sp"
    SECRET_KEY = os.environ.get("SECRET_KEY", secrets.token_hex(32))

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "postgresql://postgres:admin@127.0.0.1:5432/fire_brigade_db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_size": 15,
        "max_overflow": 5,
        "pool_timeout": 30,
        "pool_recycle": 600,
    }

    CAS_SERVER = "https://nxcas2.rokita.com.pl:8443/cas"