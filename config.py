import os
import secrets
from dotenv import load_dotenv

load_dotenv()

class Config:
    APPLICATION_ROOT = "/zsr"
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

    SAP_WERK  = os.environ.get("SAP_WERK",  "1005")
    SAP_LGORT = os.environ.get("SAP_LGORT", "S032")
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-jwt-secret")

    @classmethod
    def get_sap_config(cls):
        return {
            "user":   os.environ.get("SAP_USER"),
            "passwd": os.environ.get("SAP_PASSWORD"),
            "ashost": os.environ.get("SAP_HOST"),
            "sysnr":  os.environ.get("SAP_SYSNR", "06"),
            "client": os.environ.get("SAP_CLIENT", "200"),
            "lang":   "PL",
        }
    
    
        # PE1 (produkcyjny) – odkomentuj gdy przejdziesz na prod
    # SAP_CONFIG = {
    #     "user":   "",
    #     "passwd": "",
    #     "ashost": "bdvlspe1a1.rokita.com.pl",
    #     "sysnr":  "04",
    #     "client": "100",
    #     "lang":   "PL",
    # }