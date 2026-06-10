"""
Herald auth — simple bearer token verification.
Token is read from HERALD_AUTH_TOKEN env var.
Set a strong random token: openssl rand -hex 32
"""

import os
import hmac

_TOKEN = os.getenv("HERALD_AUTH_TOKEN", "")


def verify_token(auth_header: str) -> bool:
    """
    Verify bearer token from Authorization header.
    Uses constant-time comparison to prevent timing attacks.
    Returns False (reject) if HERALD_AUTH_TOKEN is not set in env.
    """
    if not _TOKEN:
        # Hard fail if no token configured — don't run an open server
        return False

    if not auth_header.startswith("Bearer "):
        return False

    provided = auth_header[len("Bearer "):].strip()
    # Constant-time comparison — prevents timing oracle attacks
    return hmac.compare_digest(provided.encode(), _TOKEN.encode())
