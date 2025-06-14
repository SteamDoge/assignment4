# UDPServer.py
import socket
import sys
import os
import threading # Import threading module
import random # Import random for port selection
import time # Import time for potential sleep

# --- Start of Step 11 additions/changes ---
def handle_file_transmission(filename, client_address):
    """
    处理特定客户端文件传输的线程函数。
    为每个客户端的下载请求创建一个新的UDP套接字。
    """
    file_path = os.path.join("files", filename) # Construct full file path

    # Attempt to bind to a random high port for this client's data transfer
    data_port = 0
    data_socket = None
    max_bind_attempts = 10 # Allow multiple attempts for port binding
    for attempt in range(max_bind_attempts):
        data_port = random.randint(50000, 51000)
        try:
            data_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            data_socket.bind(('', data_port))
            print(f"[Thread for {filename} from {client_address}] Bound to port {data_port}")
            break # Successfully bound
        except OSError as e:
            print(f"[Thread for {filename} from {client_address}] Port {data_port} already in use, trying another... (Attempt {attempt+1}/{max_bind_attempts}, {e})")
            time.sleep(0.05) # Small delay before retrying bind
    
    if not data_socket:
        print(f"[Thread for {filename} from {client_address}] Failed to bind to a port after {max_bind_attempts} attempts. Aborting file transfer for this client.")
        # Optionally send an ERR response if port binding totally fails
        return # Terminate thread

    try:
        # Get actual file size before sending OK
        file_size = os.path.getsize(file_path)

        # Send the actual OK response with the new data_port to the client
        ok_response = f"OK {filename} SIZE {file_size} PORT {data_port}"
        print(f"[Thread for {filename} from {client_address}] Sending initial OK: {ok_response}")
        data_socket.sendto(ok_response.encode('ascii'), client_address)

        # In future steps, this thread will enter a loop to receive FILE GET requests
        # For now, it just sends OK and closes the socket.
        # print(f"[Thread for {filename} from {client_address}] Initial OK sent. Thread terminating for now.")

    except FileNotFoundError: # Should ideally be caught in main thread, but for robustness
        err_msg = f"ERR {filename} NOT_FOUND"
        print(f"[Thread for {filename} from {client_address}] File not found (unexpectedly) during transfer setup: {filename}. Sending ERR.")
        data_socket.sendto(err_msg.encode('ascii'), client_address)
    except Exception as e:
        print(f"[Thread for {filename} from {client_address}] An unexpected error occurred during setup: {e}")
    finally:
        if data_socket:
            data_socket.close()
            print(f"[Thread for {filename} from {client_address}] Data socket closed.")

def start_server(port):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        server_socket.bind(('', port))
        print(f"UDP Server listening on port {port}")
    except OSError as e:
        print(f"Error: Could not bind to port {port}. {e}")
        sys.exit(1)

    if not os.path.exists("files"):
        os.makedirs("files")
        print("Created 'files' directory.")

    while True:
        try:
            request_data, client_address = server_socket.recvfrom(4096)
            request_message = request_data.decode('ascii').strip()
            print(f"Received DOWNLOAD request from {client_address}: {request_message}")

            parts = request_message.split(" ")
            
            if len(parts) == 2 and parts[0] == "DOWNLOAD":
                filename = parts[1]
                file_path = os.path.join("files", filename) 
                
                if os.path.exists(file_path):
                    print(f"File '{filename}' found. Spawning new thread for {client_address}.")
                    # --- Step 11: Start a new thread for this client's file transfer
                    # The new thread will handle its own socket binding and send the OK response
                    threading.Thread(target=handle_file_transmission, args=(filename, client_address,)).start()
                else:
                    response_message = f"ERR {filename} NOT_FOUND"
                    print(f"File '{filename}' not found. Sending ERR to {client_address}")
                    server_socket.sendto(response_message.encode('ascii'), client_address)

            else:
                print(f"Invalid request format: {request_message}. Ignoring.")

        except Exception as e:
            print(f"An unexpected error occurred in main server loop: {e}")
# --- End of Step 11 additions/changes ---

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

