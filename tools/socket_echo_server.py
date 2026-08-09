"""Small framed-JSON echo server for transport debugging."""

import socket
import time

from card_duel.network.protocol import DEFAULT_PORT, PROTOCOL_VERSION
from card_duel.network.transport import receive_json, send_json


def start_server(port=DEFAULT_PORT):
    with socket.socket() as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("0.0.0.0", port))
        server.listen()
        connection, address = server.accept()
        with connection:
            send_json(
                connection,
                {
                    "type": "welcome",
                    "protocol_version": PROTOCOL_VERSION,
                    "status": "success",
                    "server_time": time.ctime(),
                    "client": f"{address[0]}:{address[1]}",
                },
            )
            while True:
                try:
                    message = receive_json(connection.recv)
                except ConnectionError:
                    break
                print("收到:", message)
                send_json(connection, {"type": "echo", "payload": message})


if __name__ == "__main__":
    start_server()
