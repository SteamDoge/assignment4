# UDPClient.py
import socket
import sys
import os
import time

# --- Start of Step 10 additions/changes ---
def send_and_receive(sock, message, server_address_tuple, initial_timeout_ms=1000, max_retries=5, current_server_port=None):
    """
    可靠地发送消息并等待响应。
    如果超时，则重传并指数级增加超时时间。
    Args:
        sock (socket.socket): 用于发送和接收的UDP套接字。
        message (str): 要发送的ASCII消息。
        server_address_tuple (tuple): (server_host, server_initial_port) 服务器的初始地址。
        initial_timeout_ms (int): 初始超时时间（毫秒）。
        max_retries (int): 最大重试次数。
        current_server_port (int): 如果客户端收到OK响应后切换了端口，这里可以更新。
                                   在DOWNLOAD阶段，此参数为None。
                                   在GET/CLOSE阶段，此参数应为服务器分配的新端口。
    Returns:
        tuple: (response_message_str, sender_address_tuple) 如果成功，否则 (None, None)。
    """
    encoded_message = message.encode('ascii')
    current_timeout = initial_timeout_ms
    
    # Determine the actual target address based on current_server_port
    target_address = (server_address_tuple[0], current_server_port) if current_server_port else server_address_tuple

    for i in range(max_retries):
        try:
            sock.settimeout(current_timeout / 1000.0) # Convert ms to seconds
            print(f"[send_and_receive] Sending '{message}' to {target_address} (Timeout: {current_timeout}ms, Attempt: {i+1}/{max_retries})")
            sock.sendto(encoded_message, target_address)
            
            response_data, sender_addr = sock.recvfrom(8192)
            response_message = response_data.decode('ascii').strip()
            print(f"[send_and_receive] Received response: '{response_message}' from {sender_addr}")
            return response_message, sender_addr
        except socket.timeout:
            print(f"[send_and_receive] Timeout. No response from {target_address}. Retrying...")
            current_timeout *= 2 # Exponential backoff: double the timeout
        except Exception as e:
            print(f"[send_and_receive] An unexpected error occurred: {e}. Aborting send/receive.")
            return None, None
    
    print(f"[send_and_receive] Max retries ({max_retries}) reached. Failed to get response for '{message}'.")
    return None, None
# --- End of Step 10 additions/changes ---

def start_client(server_host, server_port, files_list_path):
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print(f"UDP Client starting. Target server: {server_host}:{server_port}")

    # For this step, we'll still only process the first file for simplicity
    # In later steps, we'll loop through all files in files_list_path
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
    
    # --- Start of Step 10 changes ---
    # First call to send_and_receive for DOWNLOAD, no current_server_port needed (uses initial server_port)
    response, sender = send_and_receive(client_socket, download_message, (server_host, server_port), 
                                        initial_timeout_ms=1000, max_retries=5, current_server_port=None)
    # --- End of Step 10 changes ---

    if not response:
        print("Failed to get response from server after retries. Exiting.")
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
                # Now, data_port holds the new port server wants us to use for file transfer
                # In next steps, we will actually use this data_port
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

