# UDPServer.py
import socket
import sys
import os
import threading
import random
import time
import base64

def handle_file_transmission(filename, client_address):
    file_path = os.path.join("files", filename)

    data_port = 0
    data_socket = None
    max_bind_attempts = 10
    for attempt in range(max_bind_attempts):
        data_port = random.randint(50000, 51000)
        try:
            data_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            data_socket.bind(('', data_port))
            print(f"[Thread for {filename} from {client_address}] Bound to port {data_port}")
            break
        except OSError as e:
            print(f"[Thread for {filename} from {client_address}] Port {data_port} already in use, trying another... ({e})")
            time.sleep(0.05)
    
    if not data_socket:
        print(f"[Thread for {filename} from {client_address}] Failed to bind to a port. Aborting.")
        return

    try:
        file_size = os.path.getsize(file_path)
        ok_response = f"OK {filename} SIZE {file_size} PORT {data_port}"
        print(f"[Thread for {filename} from {client_address}] Sending initial OK: {ok_response}")
        data_socket.sendto(ok_response.encode('ascii'), client_address)

        with open(file_path, 'rb') as f:
            while True:
                data_socket.settimeout(30)
                try:
                    request_data, addr = data_socket.recvfrom(4096)
                    request_message = request_data.decode('ascii').strip()
                    # print(f"[Thread for {filename} from {client_address}] Received request: {request_message}")

                    parts = request_message.split(" ")
                    if len(parts) >= 3 and parts[0] == "FILE" and parts[1] == filename and parts[2] == "GET":
                        if len(parts) == 7 and parts[3] == "START" and parts[5] == "END":
                            try:
                                start_byte = int(parts[4])
                                end_byte = int(parts[6])

                                if start_byte < 0 or start_byte >= file_size or end_byte < start_byte or end_byte >= file_size:
                                    print(f"[Thread for {filename} from {client_address}] Invalid byte range requested: {start_byte}-{end_byte}. Ignoring.")
                                    continue

                                f.seek(start_byte)
                                chunk_size = end_byte - start_byte + 1
                                file_chunk = f.read(chunk_size)

                                encoded_data = base64.b64encode(file_chunk).decode('ascii')
                                
                                # --- Start of Step 14 additions ---
                                response_to_client = f"FILE {filename} OK START {start_byte} END {end_byte} DATA {encoded_data}"
                                print(f"[Thread for {filename} from {client_address}] Sending data chunk ({len(file_chunk)} bytes) from {start_byte}-{end_byte}.")
                                data_socket.sendto(response_to_client.encode('ascii'), client_address)
                                # --- End of Step 14 additions ---

                            except ValueError:
                                print(f"[Thread for {filename} from {client_address}] Invalid START/END byte values in GET request: {request_message}. Ignoring.")
                        else:
                            print(f"[Thread for {filename} from {client_address}] Malformed GET request: {request_message}. Ignoring.")
                    elif len(parts) == 3 and parts[0] == "FILE" and parts[1] == filename and parts[2] == "CLOSE":
                        # This will be handled in a later step
                        print(f"[Thread for {filename} from {client_address}] Received CLOSE request (will handle later).")
                        break
                    else:
                        print(f"[Thread for {filename} from {client_address}] Unrecognized FILE command or malformed request: {request_message}. Ignoring.")

                except socket.timeout:
                    print(f"[Thread for {filename} from {client_address}] Timeout waiting for client request. Terminating thread.")
                    break
                except Exception as e:
                    print(f"[Thread for {filename} from {client_address}] An error occurred in data transfer loop: {e}")
                    break

    except FileNotFoundError:
        err_msg = f"ERR {filename} NOT_FOUND"
        print(f"[Thread for {filename} from {client_address}] File not found during transfer attempt: {filename}. Sending ERR.")
        data_socket.sendto(err_msg.encode('ascii'), client_address)
    except Exception as e:
        print(f"[Thread for {filename} from {client_address}] An unexpected error occurred: {e}")
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
                    threading.Thread(target=handle_file_transmission, args=(filename, client_address,)).start()
                else:
                    response_message = f"ERR {filename} NOT_FOUND"
                    print(f"File '{filename}' not found. Sending ERR to {client_address}")
                    server_socket.sendto(response_message.encode('ascii'), client_address)

            else:
                print(f"Invalid request format: {request_message}. Ignoring.")

        except Exception as e:
            print(f"An unexpected error occurred in main server loop: {e}")

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

