import socket
from prescient.core.logger import logger

def export_to_termbin(log_data: str) -> str | None:
    """
    Pipes text data to termbin.com via raw TCP socket and returns the URL.
    Does not rely on the system 'nc' command.
    """
    try:
        host = "termbin.com"
        port = 9999

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(5.0)
            s.connect((host, port))

            # Sending log data
            s.sendall(log_data.encode("utf-8"))

            # EOF for ending the transmission
            s.shutdown(socket.SHUT_WR)

            # Termbin's response
            response = s.recv(1024).decode("utf-8").strip().rsplit('\x00')
            if response.startswith("http"):
                logger.info(f"Successfully exported logs to {response}")
                return response
            else:
                logger.error(f"Unexpected response from termbin: {response}")
                return None
    
    except socket.timeout:
        logger.warning("Connection to termbin.com timed out (likely offline).")
        return None
    except Exception as e:
        logger.error(f"Failed to connect to termbin: {e}")
        return None
    