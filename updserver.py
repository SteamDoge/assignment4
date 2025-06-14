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

    # --- Start of Step 3 additions ---
    while True:
        try:
            # 接收客户端的请求，缓冲区大小设置为 4096 字节
            request_data, client_address = server_socket.recvfrom(4096)
            # 将接收到的字节数据解码为 ASCII 字符串，并去除首尾空白
            request_message = request_data.decode('ascii').strip()
            print(f"Received request from {client_address}: {request_message}")

            # 在此步骤，我们只打印请求，不进行任何处理或响应
            # 后续步骤会在这里添加逻辑

        except Exception as e:
            print(f"An unexpected error occurred in main server loop: {e}")
    # --- End of Step 3 additions ---

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 UDPServer.py <port_number>")
        sys.exit(1)
    try:
        server_port = int(sys.argv[1])
        if not (1024 <= server_port <= 65535):
            raise ValueError("Port number must be between 1024 and 65535.")
    except ValueError as e:
        print(f"Invalid port number: {e}")
        sys.exit(1)
    start_server(server_port)

