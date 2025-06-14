# UDPClient.py
import socket
import sys
import os

def start_client(server_host, server_port, files_list_path):
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print(f"UDP Client starting. Target server: {server_host}:{server_port}")

    filename_to_request = "test_file.txt" 
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
        client_socket.sendto(encoded_message, (server_host, server_port))
        print(f"Sent DOWNLOAD request for '{filename_to_request}' to {server_host}:{server_port}")

        # --- Start of Step 6 additions ---
        # 接收服务器的响应
        response_data, sender_addr = client_socket.recvfrom(4096)
        response_message = response_data.decode('ascii').strip()
        print(f"Received response from {sender_addr}: {response_message}")

        parts = response_message.split(" ")
        if not parts:
            print("Received empty response.")
            return

        status = parts[0]
        resp_filename = parts[1] if len(parts) > 1 else "N/A"

        if status == "OK":
            if len(parts) >= 6 and parts[2] == "SIZE" and parts[4] == "PORT":
                try:
                    file_size = int(parts[3])
                    data_port = int(parts[5])
                    print(f"Server confirms OK for '{resp_filename}'. Size: {file_size} bytes, Data Port: {data_port}")
                    # In future steps, we will use file_size and data_port
                except ValueError:
                    print(f"Invalid SIZE or PORT format in OK response: {response_message}")
            else:
                print(f"Invalid OK response format: {response_message}")
        elif status == "ERR":
            if len(parts) >= 3 and parts[2] == "NOT_FOUND":
                print(f"Server reported '{resp_filename}' NOT_FOUND.")
            else:
                print(f"Server reported an error for '{resp_filename}': {response_message}")
        else:
            print(f"Unknown response status: {status}")
        # --- End of Step 6 additions ---

    except Exception as e:
        print(f"Error during communication: {e}")
    finally:
        client_socket.close()
        print("Client socket closed. Exiting.")

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

