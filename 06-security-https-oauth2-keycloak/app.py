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
            verify=False,
            timeout=10
        )
        response_json = response.json()

        # Log for debugging
        print(f"[{datetime.now()}] Token introspection: {json.dumps(response_json, indent=2)}")

        # Check if token is active
        if response_json.get("active", False):
            return response_json
        return None

    except requests.exceptions.RequestException as e:
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
    app.run(host='0.0.0.0', port=5000, debug=True)
