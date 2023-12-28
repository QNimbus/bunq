# auth.py

# Standard library imports
from datetime import datetime, timezone

# Third-party imports
from flask import Response, current_app, jsonify, make_response, redirect, request, url_for
from flask_jwt_extended import unset_jwt_cookies, create_access_token, get_jwt, get_jwt_identity, set_access_cookies

# Local application/library imports
from libs.decorator import after_request as after_request_decorator
from libs.utils import are_urls_equal, is_safe_url, is_valid_next_url

# Import logger
from libs import logger  # pylint: disable=ungrouped-imports,unused-import


def expired_token_callback(expired_token_header: dict, _expired_token_payload: dict):
    """
    Callback function to handle expired tokens.

    Args:
        expired_token_header (dict): The expired token.
        _expired_token_payload (dict): The payload of the expired token.

    Returns:
        flask.Response: The response object with appropriate status code, message, and headers.
    """
    token_type = expired_token_header["typ"]
    redirect_when_token_is_expired = current_app.config["REDIRECT_WHEN_TOKEN_IS_EXPIRED"] if "REDIRECT_WHEN_TOKEN_IS_EXPIRED" in current_app.config else False

    if not redirect_when_token_is_expired:
        response = jsonify({"msg": "Token has expired"})
        response.headers["Token-Expired"] = token_type
        return response, 401

    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or "application/json" in request.headers.get("Accept", "") or any(request.path.startswith(path) for path in ["/api/", "/token/"]):
        response = jsonify({"msg": "Token has expired"})
        response.headers["Token-Expired"] = token_type
        return response, 401

    # Determine redirect URL
    redirect_url = request.args.get("next") or url_for("main")
    if not is_safe_url(target=redirect_url, request=request, require_https=True) or not is_valid_next_url(redirect_url):
        redirect_url = url_for("main")

    # Compare request.url and redirect_url to avoid infinite redirects
    # This can happen in when the following is true:
    # - 'redirect_url' is to an endpoint that has 'jwt_required(optional=True)'
    # ---- AND ----
    # - The JWT cookies are not yet expired, but the access token _is_ expired
    # This should normally not happend if the Cookie expires is set to a value lower or equal to the access token expiry
    if are_urls_equal(request.url, redirect_url):
        response = jsonify({"msg": "Token has expired"})
        response.headers["Token-Expired"] = token_type
        unset_jwt_cookies(response)
        return response, 401

    response = make_response(redirect(redirect_url))
    response.headers["Token-Expired"] = token_type
    return response


def missing_token_callback(reason: str):
    """
    Callback function for handling missing token error.

    Args:
        reason (str): The reason for the missing token.

    Returns:
        tuple: A tuple containing the response and status code.
    """
    redirect_when_token_is_missing = current_app.config["REDIRECT_WHEN_TOKEN_IS_MISSING"] if "REDIRECT_WHEN_TOKEN_IS_MISSING" in current_app.config else False

    if not redirect_when_token_is_missing:
        response = jsonify({"msg": reason})
        return response, 401

    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or "application/json" in request.headers.get("Accept", "") or any(request.path.startswith(path) for path in ["/api/", "/token/"]):
        response = jsonify({"msg": reason})
        return response, 401

    # Determine redirect URL
    redirect_url = request.args.get("next") or url_for("main")
    if not is_safe_url(target=redirect_url, request=request, require_https=True) or not is_valid_next_url(redirect_url):
        redirect_url = url_for("main")

    # Compare request.url and redirect_url to avoid infinite redirects
    # This can happen in when the following is true:
    # - 'redirect_url' is to an endpoint that has 'jwt_required()'
    # ---- AND ----
    # - The JWT cookies are (still missing))
    if are_urls_equal(request.url, redirect_url):
        response = jsonify({"msg": reason})
        return response, 401

    response = make_response(redirect(redirect_url))
    return response


@after_request_decorator
def refresh_expiring_jwts(response: Response) -> Response:
    """
    Refreshes expiring JWTs by checking the expiration timestamp of the current JWT.
    If the JWT is expiring within the next 10 minutes, a new access token is created
    and set as a cookie in the response.

    Args:
        response (Response): The original response object.

    Returns:
        Response: The updated response object.
    """
    try:
        exp_timestamp = get_jwt()["exp"]
        now = datetime.now(timezone.utc)
        target_timestamp = datetime.timestamp(now + current_app.config["JWT_ACCESS_TOKEN_EXPIRES"] * 0.3)
        if target_timestamp > exp_timestamp:
            access_token = create_access_token(identity=get_jwt_identity())
            # Set the JWT cookies
            access_token_cookie_max_age = current_app.config["JWT_ACCESS_TOKEN_EXPIRES"].total_seconds() - 1
            set_access_cookies(response, access_token, max_age=access_token_cookie_max_age)
        return response
    except (RuntimeError, KeyError):
        # Case where there is not a valid JWT. Just return the original response
        return response
