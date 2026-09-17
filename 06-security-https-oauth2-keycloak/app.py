import json
import os
from datetime import datetime

import requests
from flask import Flask, jsonify, request

app = Flask(__name__)

# Keycloak configuration (from environment variables)
KEYCLOAK_DNS = os.getenv('KEYCLOAK_DNS', 'localhost')
CLIENT_SECRET = os.getenv('CLIENT_SECRET', '')
KEYCLOAK_INTROSPECT_URL = f"https://{KEYCLOAK_DNS}:8443/realms/OAuth-Demo/protocol/openid-connect/token/introspect"
CLIENT_ID = "OAuth-Client"

# TLS verification for the Keycloak connection.
# Keycloak in this lab uses a self-signed certificate, so the system CA store
# cannot validate it. Instead of disabling verification (verify=False), which
# would let anyone on the network impersonate Keycloak and approve forged
# tokens, point KEYCLOAK_CA_BUNDLE at the certificate you generated in Task 2.
# When the variable is unset, requests falls back to the system CA store,
# which is the right default for a real CA-issued certificate.
KEYCLOAK_CA_BUNDLE = os.getenv('KEYCLOAK_CA_BUNDLE') or True
if KEYCLOAK_CA_BUNDLE is not True and not os.path.isfile(KEYCLOAK_CA_BUNDLE):
    raise SystemExit(
        f"KEYCLOAK_CA_BUNDLE is set to {KEYCLOAK_CA_BUNDLE!r} but no such file exists. "
        "Point it at the certificate generated in Task 2, for example: "
        "export KEYCLOAK_CA_BUNDLE=$HOME/keycloak_certs/tls.crt"
    )

def verify_token(token):
    """
    Verify token using Keycloak introspection endpoint.

    Args:
        token (str): JWT token to verify

    Returns:
        dict: Token information if valid, None if invalid
    """
    data = {
        "token": token,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    try:
        response = requests.post(
            KEYCLOAK_INTROSPECT_URL,
            data=data,
            headers=headers,
            verify=KEYCLOAK_CA_BUNDLE,
            timeout=10
        )
        response_json = response.json()

        # Log for debugging
        print(f"[{datetime.now()}] Token introspection: {json.dumps(response_json, indent=2)}")

        # Check if token is active
        if response_json.get("active", False):
            return response_json
        return None

    except (requests.exceptions.RequestException, OSError) as e:
        # OSError covers CA bundle problems raised before the request is sent.
        print(f"Error connecting to Keycloak: {e}")
        return None

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "OAuth Protected API"
    })

@app.route('/secure-data', methods=['GET'])
def secure_data():
    """
    OAuth 2.0 protected endpoint.
    Requires valid JWT token in Authorization header.
    """
    auth_header = request.headers.get('Authorization')

    if not auth_header:
        return jsonify({
            "error": "Missing Authorization header",
            "message": "Include 'Authorization: Bearer <token>' header"
        }), 401

    # Extract token from "Bearer <token>"
    try:
        token = auth_header.split(" ")[1]
    except IndexError:
        return jsonify({
            "error": "Invalid Authorization header format",
            "message": "Use format 'Bearer <token>'"
        }), 401

    # Verify token with Keycloak
    token_info = verify_token(token)

    if token_info:
        return jsonify({
            "message": "Secure Data Access Granted",
            "user": token_info.get("username", "unknown"),
            "client": token_info.get("client_id", "unknown"),
            "expires_at": token_info.get("exp", "unknown"),
            "data": {
                "sensitive_info": "This is protected data",
                "user_permissions": ["read", "write"],
                "timestamp": datetime.now().isoformat()
            }
        })
    else:
        return jsonify({
            "error": "Invalid or expired token",
            "message": "Token validation failed"
        }), 403

@app.route('/public-data', methods=['GET'])
def public_data():
    """Public endpoint (no authentication required)."""
    return jsonify({
        "message": "Public data access",
        "data": "This data is publicly accessible",
        "timestamp": datetime.now().isoformat()
    })

if __name__ == '__main__':
    print("Starting Flask API...")
    print(f"Keycloak URL: {KEYCLOAK_INTROSPECT_URL}")
    print(f"Client ID: {CLIENT_ID}")
    print(f"CA bundle: {'system CA store' if KEYCLOAK_CA_BUNDLE is True else KEYCLOAK_CA_BUNDLE}")
    # The Werkzeug debugger exposes an interactive Python console on any
    # unhandled exception, so it must never be on by default. Set
    # FLASK_DEBUG=1 explicitly to enable it on a private lab instance.
    app.run(host='0.0.0.0', port=5000, debug=os.getenv('FLASK_DEBUG', '0') == '1')
