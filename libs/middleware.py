# middleware.py

# Standard library imports
import os
import ipaddress
from typing import Callable, Any

# Local application/library imports
from flask import Flask, Response
from werkzeug.wrappers import Request
from libs.log import setup_logger, setup_logger_with_rotating_file_handler
from libs.exceptions import InvalidIPAddressError

# Setup logging
logger = setup_logger(__name__, os.environ.get("LOG_LEVEL", "INFO"))


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

    def __call__(self, environ: dict[str, Any], start_response: Callable) -> Callable:
        """
        Call method for the middleware.

        Parameters:
            environ (dict[str, Any]): The WSGI environment.
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

class DebugLogMiddleware:  # pylint: disable=too-few-public-methods
    """
    Middleware to log the request information.
    """

    def __init__(self, app: Flask) -> None:
        self.app = app

    def __call__(self, environ: dict[str, Any], start_response: Callable) -> Callable:
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

        return self.app(environ, start_response)
