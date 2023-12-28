# routes/__init__.py

# Standard library imports
import os
import json
import base64
from threading import Thread
from typing import Optional
from datetime import datetime

# Third-party imports
from pydantic import TypeAdapter
from jsonschema import validate
from jsonschema.exceptions import ValidationError
from flask import jsonify, render_template, redirect, url_for, make_response, request, current_app
from flask_jwt_extended import (
    create_access_token,
    set_access_cookies,
    unset_jwt_cookies,
    get_jwt,
    get_jwt_identity,
    jwt_required,
    create_refresh_token,
    set_refresh_cookies,
)

# Local application/library imports
from libs.user import User, UserConnector
from libs.payment import process_payment
from libs.redis_wrapper import RedisWrapper
from libs.utils import is_safe_url, is_valid_next_url
from libs.decorator import route
from schema.callback_model import CallbackModel

# Import logging
from libs import logger  # pylint: disable=ungrouped-imports,unused-import


@route("/health", methods=["GET"])
def health():
    """
    Handles health check requests via HTTP GET.

    Parameters:
    - None

    Returns:
    - JSON response with a success message.
    """
    return jsonify({"message": "Success"}, 200)


@route("/api/requests", methods=["GET"])
@jwt_required()
def api_requests():
    """
    Retrieves all request data from Redis and returns it as a JSON response.
    """
    try:
        page = request.args.get("page", 1, type=int)
        page_size = request.args.get("page_size", 10, type=int)

        if page < 1 or page_size < 1:
            raise ValueError("Page and page size must be positive integers.")

        # Set a maximum page_size to avoid very large requests
        max_page_size = current_app.config["MAX_PAGE_SIZE"]
        page_size = min(page_size, max_page_size)

        all_request_data = RedisWrapper.get_all_request_data()

        # Iterate over the request_data
        for _uuid, request_data in all_request_data.items():
            for key, value in request_data.items():
                # Encode the value to base64 if it is a dict so it's not displayed as a string in the HTML
                # Encode datetime objects to a string
                # Pass the rest of the values as-is
                try:
                    if isinstance(value, dict):
                        request_data[key] = base64.b64encode(json.dumps(value).encode("utf-8")).decode("utf-8")
                    elif isinstance(value, datetime):
                        request_data[key] = value.strftime("%d-%m-%Y %H:%M:%S")
                except TypeError:
                    pass

        # Apply pagination
        data_list = list(all_request_data.items())
        data_list.reverse()
        start = (page - 1) * page_size
        end = start + page_size
        page_data = data_list[start:end]

        total_items = len(all_request_data)
        total_pages = total_items // page_size + (total_items % page_size > 0)

        return jsonify({"data": page_data, "total_items": total_items, "total_pages": total_pages, "current_page": page, "page_size": page_size})
    except ValueError as error:
        logger.error(error)
        return jsonify({"message": "Internal server error"}), 500


@route("/api/requests/<request_id>", methods=["DELETE"])
@jwt_required()
def delete_request(request_id: str):
    """
    Deletes a request from Redis.

    Parameters:
    - request_id (str): The request id.

    Returns:
    - JSON response with a success message.
    """
    try:
        RedisWrapper.unlog_request(request_id=request_id)
        RedisWrapper.remove_request_data(request_id=request_id)
    except Exception as error:  # pylint: disable=broad-except
        logger.error(error)
        return jsonify({"message": "Internal server error"}), 500

    return jsonify({"message": "Success"})


@route("/replay/<request_uuid>", methods=["GET"])
@jwt_required(fresh=True)
def replay(request_uuid: str):
    """
    Handles replay requests via HTTP GET.

    Parameters:
    - request_uuid (str): The request id.

    Returns:
    - JSON response with a success message.
    """
    request_data = RedisWrapper.get_secure(request_uuid)

    user_id = int(request_data["url"].split("/")[-1])

    return jsonify({"message": "Success"})


@route("/callback/<int:user_id>", methods=["POST"])
def callback(user_id: int):
    """
    Handles callbacks from another application via HTTP POST.

    Parameters:
    - user (str): The name of the user.

    Returns:
    - JSON response with a success message if the request is valid and from an allowed IP.
    - JSON response with an error message if the request is invalid or the schema does not match.
    """
    request_id = request.environ.get("request_id", None)

    if request_id is None:
        raise RuntimeError(f"Request id not set in request: {request}")

    # Get request_log from Redis. If it does not exist, throw an error
    current_request = RedisWrapper.get_request_data(request_id=request_id)

    if current_request is None:
        raise RuntimeError(f"Request id not found in request_log: {request_id}")

    # Return 400 if the request is not JSON
    if not request.is_json:
        response_message = {"message": "Missing JSON in request"}
        current_request["response"] = response_message

        # Register the response in a separate thread
        Thread(target=RedisWrapper.set_request_data, kwargs={"request_id": request_id, "data": current_request}).start()

        logger.info(f"[/callback/{user_id}] Invalid request: {request}")
        return jsonify(response_message), 400

    # Fetch all available user ids from the app session
    keys = current_app.config["BUNQ_CONFIGS"].keys() if "BUNQ_CONFIGS" in current_app.config else []

    if user_id not in keys:
        response_message = {"message": "Invalid user"}
        current_request["response"] = response_message

        # Register the response in a separate thread
        Thread(target=RedisWrapper.set_request_data, kwargs={"request_id": request_id, "data": current_request}).start()

        logger.info(f"[/callback/{user_id}] Invalid user id: {user_id}")
        return jsonify(response_message), 400

    try:
        request_data = request.get_json()
        request_schema = current_app.config["CALLBACK_SCHEMA"]

        # Validate the request data against the schema
        validate(instance=request_data, schema=request_schema)

        # Log the json data
        # callback_logger.info(json.dumps(request_data))

        callback_data = TypeAdapter(CallbackModel).validate_python(request_data)
        event_type = callback_data.NotificationUrl.event_type

        # Dictionary to simulate a switch/case structure
        switcher = {
            "PAYMENT_CREATED": process_payment,
            "PAYMENT_RECEIVED": process_payment,
            "MUTATION_CREATED": process_payment,
            "MUTATION_RECEIVED": process_payment,
            "CARD_PAYMENT_ALLOWED": None,
            "CARD_TRANSACTION_NOT_ALLOWED": None,
            "REQUEST_INQUIRY_CREATED": None,
            "REQUEST_INQUIRY_ACCEPTED": None,
            "REQUEST_INQUIRY_REJECTED": None,
            "REQUEST_RESPONSE_CREATED": None,
            "REQUEST_RESPONSE_ACCEPTED": None,
            "REQUEST_RESPONSE_REJECTED": None,
        }

        # Get the function from switcher dictionary
        handler = switcher.get(event_type.value, None)

        # Execute the handler function if it exists and pass the data object
        if handler is not None and callback_data is not None:
            current_request["processed"] = True
            current_request["event"] = event_type.value

            # Register the response in a separate thread
            Thread(target=RedisWrapper.set_request_data, kwargs={"request_id": request_id, "data": current_request}).start()
            Thread(
                target=handler, kwargs={"app_context": current_app.app_context(), "user_id": user_id, "request_id": request.request_id, "event_type": event_type, "callback_data": callback_data}
            ).start()
        else:
            logger.info(f"[/callback/{user_id}] Unregistered event type {event_type.value}")

        return jsonify({"message": "Success"})
    except ValidationError:
        # Log the failed callback json data
        # failed_callback_logger.info(json.dumps(request_data))

        logger.info(f"[/callback/{user_id}] Schema mismatch: {request}")

        # Return HTTP 400 if the callback data did not match the schema
        return jsonify({"message": "Schema mismatch"}), 400


@route("/", methods=["GET"])
@jwt_required(optional=True)
def main():
    """
    Returns the main page.

    Returns:
        HTML response with the main page.
    """
    user_connector: UserConnector = current_app.config["USER_CONNECTOR"]
    user: User = user_connector.get_user(get_jwt_identity()) if get_jwt_identity() else None

    next_url = request.args.get("next", "/")
    is_valid_next_url(next_url)

    return render_template("main.html", user=user, next="/requests")


@route("/requests", methods=["GET"])
@jwt_required()
def requests():
    """
    Handles request log requests via HTTP GET.

    Parameters:
    - None

    Returns:
    - HTML response with a list of request ids.
    """
    user_connector: UserConnector = current_app.config["USER_CONNECTOR"]
    user: User = user_connector.get_user(get_jwt_identity())

    return render_template("requests.html", user=user)


@route("/login", methods=["POST"])
def login():
    """
    Authenticates the user's credentials and generates an access token if the credentials are valid.

    Returns:
        If the credentials are valid, returns a JSON response containing the access token with a status code of 200.
        If the request is missing JSON or the username/password is missing, returns a JSON response with an error message and a status code of 400.
        If the username/password is incorrect, returns a JSON response with an error message and a status code of 401.
    """
    if not request.is_json:
        return jsonify({"msg": "Missing JSON in request"}), 400

    username = request.json.get("username", None)
    password = request.json.get("password", None)

    if not username or not password:
        return jsonify({"msg": "Missing username or password"}), 400

    # This should check your user's credentials from the database
    user_connector: UserConnector = current_app.config["USER_CONNECTOR"]
    user: Optional[User] = user_connector.authenticate(username, password)

    if user:
        # Create tokens
        access_token = create_access_token(identity=user.id)
        refresh_token = create_refresh_token(identity=user.id)

        # Determine redirect URL
        redirect_url = request.json.get("next") or request.args.get("next") or url_for("main")
        if not is_safe_url(target=redirect_url, request=request, require_https=True):
            redirect_url = url_for("main")

        # Create a redirect response
        response = make_response(redirect(redirect_url))

        # Set the JWT cookies
        access_token_cookie_max_age = current_app.config["JWT_ACCESS_TOKEN_EXPIRES"].total_seconds() - 1
        refresh_token_cookie_max_age = current_app.config["JWT_REFRESH_TOKEN_EXPIRES"].total_seconds() - 1
        set_access_cookies(response, access_token, max_age=access_token_cookie_max_age)
        set_refresh_cookies(response, refresh_token, max_age=refresh_token_cookie_max_age)

        return response

    return jsonify({"msg": "Bad username or password"}), 401


@route("/token/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    """
    Refreshes the JWT token for the current user.

    Returns:
        response (flask.Response): The response object with the refreshed token.
    """
    user_connector: UserConnector = current_app.config["USER_CONNECTOR"]
    user: Optional[User] = user_connector.get_user(get_jwt_identity())

    if not user:
        response = jsonify({"msg": "User not found"})
        unset_jwt_cookies(response)
        return response, 404

    new_token = create_access_token(identity=user.id, fresh=False)

    response = jsonify({"msg": "Token refreshed"})
        
    # Set the JWT cookies
    access_token_cookie_max_age = current_app.config["JWT_ACCESS_TOKEN_EXPIRES"].total_seconds() - 1
    set_access_cookies(response, new_token, max_age=access_token_cookie_max_age)
    
    return response, 200


@route("/logout", methods=["DELETE"])
@jwt_required()
def logout():
    """
    Logs out the user by unsetting the JWT cookie.

    Returns:
        JSON response with a success message.
    """
    jwt_payload = get_jwt()

    # Add the token to the Redis blocklist
    RedisWrapper.revoke_token(jwt_payload=jwt_payload, expires=jwt_payload["exp"] - jwt_payload["iat"])

    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or "application/json" in request.headers.get("Accept", ""):
        response = jsonify({"msg": "Logged out, access token revoked"})
        unset_jwt_cookies(response)
        return response, 200

    # Determine redirect URL
    redirect_url = request.args.get("next") or url_for("main")
    if not is_safe_url(target=redirect_url, request=request, require_https=True):
        redirect_url = url_for("main")

    response = make_response(redirect(redirect_url))
    unset_jwt_cookies(response)
    return response
