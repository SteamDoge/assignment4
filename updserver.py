# UDPServer.py
import socket
import sys

def start_server(port):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        server_socket.bind(('', port))
        print(f"UDP Server listening on port {port}")
    except OSError as e:
        print(f"Error: Could not bind to port {port}. {e}")
        sys.exit(1)
    # ... 后续步骤将在这里添加接收循环

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 UDPServer.py <port_number>")
        sys.exit(1)
    try:
        server_port = int(sys.argv[1])
        # Add port range validation here
        if not (1024 <= server_port <= 65535):
            raise ValueError("Port number must be between 1024 and 65535.")
    except ValueError as e:
        print(f"Invalid port number: {e}")
        sys.exit(1)
    start_server(server_port)

