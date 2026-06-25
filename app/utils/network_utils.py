# utils/network_utils.py
"""
Network related utilities.
"""

import socket

from app.core.config import settings

def get_local_ip_address(logger):
    """
    Get local machine IP address.
    """

    socket_connection = socket.socket(
        socket.AF_INET,
        socket.SOCK_DGRAM,
    )

    try:
        socket_connection.connect((settings.IP_ADDRESS, 80))

        ip_address = socket_connection.getsockname()[0]

        return ip_address

    except Exception as e:
        logger.exception(e)
        return ""

    finally:
        socket_connection.close()