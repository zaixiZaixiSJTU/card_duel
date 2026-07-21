import socket
import json
import time


def start_server():
    with socket.socket() as s:
        s.bind(('0.0.0.0', 65432))
        s.listen()
        conn, addr = s.accept()

        # 发送连接成功提示
        conn.sendall(json.dumps({
            'event': 'connection',
            'status': 'success',
            'server_time': time.ctime(),
            'client': f"{addr[0]}:{addr[1]}"
        }).encode())

        while True:
            data = conn.recv(1024)
            if not data:
                break
            print("收到:", data.decode())
            conn.sendall(b"Message received")


if __name__ == "__main__":
    start_server()