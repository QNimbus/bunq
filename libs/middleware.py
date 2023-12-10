# middleware.py

# Standard library imports
import os
import ipaddress
from enum import Enum
import xml.etree.ElementTree as ET
from re import match
from io import BytesIO
from typing import Callable, Optional, Union
import json
import yaml

# Local application/library imports
from flask import Flask, Response
from werkzeug.wrappers import Request
from libs.logger import setup_logger
from libs.exceptions import InvalidIPAddressError

# Setup logging
logger = setup_logger(__name__, os.environ.get("LOG_LEVEL", "INFO"))

# Define a type for the function signature
RequestLoggerCallbackData = dict[any, any], dict[str, any]
RequestLoggerCallback = Callable[[RequestLoggerCallbackData], None]

# Define a type for the route_regex
RequestLoggerRouteRegex = Optional[Union[str, list[str]]]


class _ParserReturnType(Enum):
    """
    Enum representing the possible return types for a parser.
    """

    DICT = "dict"
    STRING = "string"
    XML = "xml"


def _parse_json(body, return_type: _ParserReturnType = _ParserReturnType.STRING) -> str | dict[str, any]:
    if return_type == _ParserReturnType.DICT:
        return json.loads(body)

    return json.dumps(json.loads(body), indent=4)


def _parse_yaml(body, return_type: _ParserReturnType = _ParserReturnType.STRING) -> str | dict[str, any]:
    if return_type == _ParserReturnType.DICT:
        return yaml.safe_load(body)

    return yaml.dump(yaml.safe_load(body), indent=4)


def _parse_xml(body, return_type: _ParserReturnType = _ParserReturnType.STRING) -> str | ET.Element:
    xml_body = ET.fromstring(body)
    if return_type == _ParserReturnType.XML:
        return xml_body

    return ET.tostring(xml_body, encoding="unicode", method="xml")


def _pretty_print_request_body(request_body: bytes) -> str:
    """
    Pretty prints the request body by trying different parsers.

    Args:
        request_body (bytes): The request body to be pretty printed.

    Returns:
        str: The pretty printed request body.

    """
    parsers = [_parse_json, _parse_yaml, _parse_xml]

    for parser in parsers:
        try:
            return parser(request_body)
        except Exception:  # pylint: disable=broad-except
            continue

    # If none of the parsers worked, return the original request body
    return request_body.decode()


def _parse_request_body(request_body: bytes) -> dict[str, any]:
    """
    Parses the request body by trying different parsers.

    Args:
        request_body (bytes): The request body to be parsed.

    Returns:
        dict[str, any]: The parsed request body.

    """
    parsers = [_parse_json, _parse_yaml, _parse_xml]

    for parser in parsers:
        try:
            return parser(request_body, return_type=_ParserReturnType.DICT)
        except Exception:  # pylint: disable=broad-except
            continue

    # If none of the parsers worked, return the original request body
    return request_body.decode()


class AllowedIPsMiddleware:  # pylint: disable=too-few-public-methods
    """
    Middleware that restricts access to the Flask app to a list of allowed IP addresses.
    Optionally, it can also consider the 'X-Forwarded-For' header when behind a trusted proxy.

    Attributes:
        app (Flask): The Flask application instance.
        allowed_ips (list[ipaddress.IPv4Address]): A list of allowed IP addresses.
        trust_proxy (bool): Whether to trust the 'X-Forwarded-For' header.
    """

    def __init__(
        self,
        app: Flask,
        allowed_ips: list[str],
        trust_proxy: bool = False,
        public_routes: list[str] = None,
    ) -> None:
        """
        Initializes the AllowedIPsMiddleware.

        Parameters:
            app (Flask): The Flask application instance.
            allowed_ips (List[str]): A list of allowed IP addresses and/or networks.
            trust_proxy (bool): Whether to trust the 'X-Forwarded-For' header.
        """
        if public_routes is None:
            public_routes = []

        self.app = app
        self.trust_proxy = trust_proxy
        self.public_routes = set(public_routes)
        self.allowed_ips: list[ipaddress.IPv4Network] = []

        for input_string in allowed_ips:
            try:
                # Try to create an IPv4Network object from the input string
                ip_network = ipaddress.IPv4Network(input_string, strict=False)
                self.allowed_ips.append(ip_network)
            except (ipaddress.AddressValueError, ipaddress.NetmaskValueError):
                try:
                    # If it's not in network notation, try creating an IPv4Address object
                    ip_address = ipaddress.IPv4Address(input_string)
                    # Convert the single IP address to a network with a netmask of /32
                    ip_network = ipaddress.IPv4Network(ip_address.exploded + "/32", strict=False)
                    self.allowed_ips.append(ip_network)
                except ipaddress.AddressValueError as exc:
                    raise InvalidIPAddressError(f"Invalid IP address: {input_string}") from exc

    def __call__(self, environ: dict[str, any], start_response: Callable) -> Callable:
        """
        Call method for the middleware.

        Parameters:
            environ (dict[str, any]): The WSGI environment.
            start_response (Callable): The start response callable in the WSGI application.

        Returns:
            Callable: The application or error response callable.

        Raises:
            InvalidIPAddressError: If an invalid IP address is encountered.
        """
        req = Request(environ)

        # Skip IP restriction check if the route is public
        if req.path in self.public_routes:
            return self.app(environ, start_response)

        # Determine the client's IP address
        if self.trust_proxy and "HTTP_X_FORWARDED_FOR" in environ:
            # Use the first IP address in 'X-Forwarded-For' header
            forwarded_for = environ["HTTP_X_FORWARDED_FOR"].split(",")[0].strip()
            ip_address_str = forwarded_for
        else:
            ip_address_str = req.remote_addr

        # Convert the IP address to a standard format for comparison
        try:
            remote_addr = ipaddress.IPv4Address(ip_address_str)
        except ipaddress.AddressValueError as exc:
            raise InvalidIPAddressError(f"Invalid IP address: {ip_address_str}") from exc

        if not self._is_ip_allowed(remote_addr):
            response = Response(status=403)  # Forbidden access
            return response(environ, start_response)

        return self.app(environ, start_response)

    def _is_ip_allowed(self, ip_address: str | ipaddress.IPv4Address) -> bool:
        """
        Check if the given IP address matches any of the IPv4Network instances in the list.

        Parameters:
            - ip_address (str or ipaddress.IPv4Address): The IP address to check.

        Returns:
            - bool: True if the IP address is in any of the networks, False otherwise.
        """
        try:
            # Convert the input IP address to an IPv4Address object if it's a string
            if isinstance(ip_address, str):
                ip_address = ipaddress.IPv4Address(ip_address)

            # Iterate through the list of networks and check if the IP is in any of them
            for network in self.allowed_ips:
                if ip_address in network:
                    return True

            # If no match is found in any network, return False
            return False

        except ipaddress.AddressValueError as exc:
            raise InvalidIPAddressError(f"Invalid IP address: {ip_address}") from exc


class RequestLoggerMiddleware:  # pylint: disable=too-few-public-methods
    """
    Middleware class for logging incoming requests.

    Args:
        app (callable): The WSGI application.
        callback (Optional[CallbackFunction], None]]): Optional callback function to handle the request.
        route_regex (Optional[RouteRegex]): Optional regular expression or list of regular expressions representing routes for which to log requests. Default is None (logs all requests).

    """

    def __init__(self, app, callback: Optional[RequestLoggerCallback] = None, route_regex: Optional[RequestLoggerRouteRegex] = None):
        self.app = app
        self.callback = callback

        if isinstance(route_regex, str):
            self.route_regex = [route_regex]
        else:
            self.route_regex = route_regex

    def __call__(self, environ: dict, start_response: callable):
        """
        Call method to handle the incoming request.

        Args:
            environ (dict): The WSGI environment dictionary.
            start_response (callable): The WSGI start_response function.

        Returns:
            iterable: The response from the WSGI application.

        """
        # Return early if the route is not in the list of routes to log
        path_info = environ.get("PATH_INFO")
        if self.route_regex is not None and not any(match(route, path_info) for route in self.route_regex):
            return self.app(environ, start_response)

        # Get the HTTP method
        request_method = environ["REQUEST_METHOD"]

        # Get request URL
        request_url = f"{environ['wsgi.url_scheme']}://{environ['HTTP_HOST']}{environ['PATH_INFO']}"

        # Get request query string
        request_query_string = environ["QUERY_STRING"]

        # Get request cookies
        request_cookies = {k: v for k, v in environ.items() if k.startswith("HTTP_COOKIE")}

        # Get request client ip address
        request_client_ip = environ.get("HTTP_X_FORWARDED_FOR", environ.get("REMOTE_ADDR"))

        # Get request headers
        request_headers = {k[5:]: v for k, v in environ.items() if k.startswith("HTTP_")}

        # Get request body
        request_body_size = int(environ.get("CONTENT_LENGTH", 0))
        request_body = environ["wsgi.input"].read(request_body_size)

        # Reset wsgi.input for further reading
        environ["wsgi.input"] = BytesIO(request_body)

        # Constrcut request_data dictionary
        request_data: RequestLoggerCallbackData = {
            "method": request_method,
            "url": request_url,
            "query_string": request_query_string,
            "cookies": request_cookies,
            "client_ip": request_client_ip,
            "headers": request_headers,
            "body": _parse_request_body(request_body),
        }

        # Call the callback with the headers and body, or log them
        if self.callback and callable(self.callback):
            self.callback(environ, request_data)
        else:
            print(f"Request received:\nHeaders - {request_headers}\nBody -\n{_pretty_print_request_body(request_body)}")

        return self.app(environ, start_response)


class DebugLogMiddleware:  # pylint: disable=too-few-public-methods
    """
    Middleware to log the request information.
    """

    def __init__(self, app: Flask) -> None:
        self.app = app

    def __call__(self, environ: dict[str, any], start_response: Callable) -> Callable:
        """
        Log the request information.

        :param environ: The WSGI environment.
        :param start_response: The WSGI start_response callable.
        :return: The response from the Flask application.
        """
        req = Request(environ)

        # Log the request method and URL
        logger.debug(f"Request Method: {req.method}")
        logger.debug(f"Request URL: {req.url}")

        # Log request headers
        logger.debug("Request Headers:")
        for key, value in req.headers.items():
            logger.debug(f"{key}: {value}")

        # Log request body
        request_body_size = int(environ.get("CONTENT_LENGTH", 0))
        request_body = environ["wsgi.input"].read(request_body_size)
        logger.debug("Request Body:")
        logger.debug(_pretty_print_request_body(request_body))

        # Reset wsgi.input for further reading
        environ["wsgi.input"] = BytesIO(request_body)

        return self.app(environ, start_response)
