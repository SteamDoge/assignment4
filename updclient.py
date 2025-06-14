# UDPClient.py
import socket
import sys
import os
import time # Import time for potential sleep in future exponential backoff

def send_and_receive(sock, message, server_address, timeout_ms=1000): # --- Step 8: Add timeout_ms parameter
    """
    发送消息并等待响应 (带超时)。
    Args:
        sock (socket.socket): 用于发送和接收的UDP套接字。
        message (str): 要发送的ASCII消息。
        server_address (tuple): (server_host, server_port) 服务器地址。
        timeout_ms (int): 超时时间（毫秒）。
    Returns:
        tuple: (response_message_str, sender_address_tuple) 如果成功，否则 (None, None)。
    """
    encoded_message = message.encode('ascii')
    try:
        sock.settimeout(timeout_ms / 1000.0) # --- Step 8: Set socket timeout (in seconds)
        print(f"[send_and_receive] Sending '{message}' to {server_address} (Timeout: {timeout_ms}ms)")
        sock.sendto(encoded_message, server_address)
        
        response_data, sender_addr = sock.recvfrom(8192)
        response_message = response_data.decode('ascii').strip()
        print(f"[send_and_receive] Received response: '{response_message}' from {sender_addr}")
        return response_message, sender_addr
    except socket.timeout: # --- Step 8: Handle timeout exception
        print(f"[send_and_receive] Timeout. No response from {server_address}.")
        return None, None
    except Exception as e:
        print(f"[send_and_receive] Error during send/receive: {e}")
        return None, None

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
    
    # --- Start of Step 8 change ---
    # Pass an initial timeout value (e.g., 1000 ms)
    response, sender = send_and_receive(client_socket, download_message, (server_host, server_port), timeout_ms=1000)
    # --- End of Step 8 change ---

    if not response:
        print("No response received from server (possibly due to timeout). Exiting.")
        return

    parts = response.split(" ")
    if not parts:
        print("Received empty response after send_and_receive.")
        return

    status = parts[0]
    resp_filename = parts[1] if len(parts) > 1 else "N/A"

    if status == "OK":
        if len(parts) >= 6 and parts[2] == "SIZE" and parts[4] == "PORT":
            try:
                file_size = int(parts[3])
                data_port = int(parts[5])
                print(f"Server confirms OK for '{resp_filename}'. Size: {file_size} bytes, Data Port: {data_port}")
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

