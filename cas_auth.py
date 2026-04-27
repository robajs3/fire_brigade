# cas_auth.py
import re
import requests
from functools import wraps
from flask import session, redirect, request, url_for, current_app


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "CAS_USERNAME" not in session:
            service_url = request.url
            cas_server = current_app.config["CAS_SERVER"]
            return redirect(f"{cas_server}/login?service={service_url}")
        return f(*args, **kwargs)
    return decorated


def validate_ticket(ticket, service_url):
    cas_server = current_app.config["CAS_SERVER"]
    validate_url = (
        f"{cas_server}/serviceValidate"
        f"?ticket={ticket}&service={service_url}"
    )
    try:
        r = requests.get(validate_url, verify=False, timeout=10)
        if "<cas:authenticationSuccess>" in r.text:
            match = re.search(r"<cas:user>(.*?)</cas:user>", r.text)
            return match.group(1) if match else None
    except requests.RequestException:
        return None
    return None