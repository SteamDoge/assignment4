# UDPClient.py
import socket
import sys
import os # Import os for file path operations (needed for files_list.txt later)

def start_client(server_host, server_port, files_list_path):
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print(f"UDP Client starting. Target server: {server_host}:{server_port}")

    # --- Start of Step 4 additions ---
    # Simplified: For this step, we'll just pick a dummy filename or the first from the list
    filename_to_request = "test_file.txt" # You can change this to a real file in your 'files/' directory
    
    # In future steps, we will read from files_list_path, but for now, hardcode or pick first
    try:
        with open(files_list_path, 'r') as f:
            filenames = [line.strip() for line in f if line.strip()]
            if filenames:
                filename_to_request = filenames[0]
            else:
                print(f"Warning: {files_list_path} is empty, using default 'test_file.txt'.")
    except FileNotFoundError:
        print(f"Error: File list '{files_list_path}' not found. Using default 'test_file.txt'.")

    download_message = f"DOWNLOAD {filename_to_request}"
    encoded_message = download_message.encode('ascii')

    try:
        # 发送 DOWNLOAD 请求到服务器的主端口
        client_socket.sendto(encoded_message, (server_host, server_port))
        print(f"Sent DOWNLOAD request for '{filename_to_request}' to {server_host}:{server_port}")
    except Exception as e:
        print(f"Error sending DOWNLOAD request: {e}")
    finally:
        # 在此步骤，客户端发送后即关闭套接字并退出
        client_socket.close()
        print("Client socket closed. Exiting.")
    # --- End of Step 4 additions ---


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python3 UDPClient.py <hostname> <port_number> <files_list.txt>")
        sys.exit(1)
    server_hostname = sys.argv[1]
    try:
        server_port = int(sys.argv[2])
        if not (1024 <= server_port <= 65535):
            raise ValueError("Port number must be between 1024 and 65535.")
    except ValueError as e:
        print(f"Invalid port number: {e}")
        sys.exit(1)
    files_list_file = sys.argv[3]
    start_client(server_hostname, server_port, files_list_file)

