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
    # --- Step 19: Robust port binding attempt ---
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
        # If port binding completely fails, cannot communicate, so no ERR response to client.
        return # Terminate thread

    try:
        # --- Step 19: Check file existence again within thread for robustness ---
        if not os.path.exists(file_path):
            err_msg = f"ERR {filename} NOT_FOUND"
            print(f"[Thread for {filename} from {client_address}] File '{filename}' not found (unexpectedly at data transfer stage). Sending ERR.")
            data_socket.sendto(err_msg.encode('ascii'), client_address)
            return # Exit thread if file not found

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
                    
                    if len(parts) >= 3 and parts[0] == "FILE" and parts[1] == filename:
                        command = parts[2]
                        
                        if command == "GET":
                            if len(parts) == 7 and parts[3] == "START" and parts[5] == "END":
                                try:
                                    start_byte = int(parts[4])
                                    end_byte = int(parts[6])

                                    # --- Step 19: More robust range validation ---
                                    if start_byte < 0 or start_byte >= file_size or \
                                       end_byte < start_byte or end_byte >= file_size:
                                        print(f"[Thread for {filename} from {client_address}] Invalid byte range requested: {start_byte}-{end_byte}. Ignoring.")
                                        # Optionally send a specific error for bad range
                                        continue

                                    f.seek(start_byte)
                                    chunk_size = end_byte - start_byte + 1
                                    file_chunk = f.read(chunk_size)

                                    encoded_data = base64.b64encode(file_chunk).decode('ascii')
                                    
                                    response_to_client = f"FILE {filename} OK START {start_byte} END {end_byte} DATA {encoded_data}"
                                    print(f"[Thread for {filename} from {client_address}] Sending data chunk ({len(file_chunk)} bytes) from {start_byte}-{end_byte}.")
                                    data_socket.sendto(response_to_client.encode('ascii'), client_address)

                                except ValueError:
                                    print(f"[Thread for {filename} from {client_address}] Invalid START/END byte values in GET request: {request_message}. Ignoring.")
                                except Exception as e: # Catch any other errors during file read/encoding
                                    print(f"[Thread for {filename} from {client_address}] Error processing GET request: {e}. Ignoring.")
                            else:
                                print(f"[Thread for {filename} from {client_address}] Malformed GET request: {request_message}. Ignoring.")
                        
                        elif command == "CLOSE":
                            if len(parts) == 3:
                                close_response = f"FILE {filename} CLOSE_OK"
                                print(f"[Thread for {filename} from {client_address}] Received CLOSE request. Sending CLOSE_OK.")
                                data_socket.sendto(close_response.encode('ascii'), client_address)
                                break
                            else:
                                print(f"[Thread for {filename} from {client_address}] Malformed CLOSE request: {request_message}. Ignoring.")
                        else:
                            print(f"[Thread for {filename} from {client_address}] Unrecognized FILE command: {command}. Ignoring.")
                    else:
                        print(f"[Thread for {filename} from {client_address}] Malformed request or incorrect filename: {request_message}. Ignoring.")

                except socket.timeout:
                    print(f"[Thread for {filename} from {client_address}] Timeout waiting for client request. Terminating thread.")
                    break
                # --- Step 19: Catch general exceptions in the thread loop ---
                except Exception as e:
                    print(f"[Thread for {filename} from {client_address}] An unexpected error occurred in data transfer loop: {e}. Terminating thread.")
                    break
        # --- End of Step 19 additions/changes for thread loop ---

    except IOError as e: # Catch errors when opening the file for reading (e.g., permissions)
        err_msg = f"ERR {filename} SERVER_FILE_ERROR"
        print(f"[Thread for {filename} from {client_address}] IO Error opening file '{filename}': {e}. Sending ERR.")
        data_socket.sendto(err_msg.encode('ascii'), client_address)
    except Exception as e: # Catch any other unexpected errors during thread initialization
        print(f"[Thread for {filename} from {client_address}] An unexpected error occurred during thread setup: {e}")
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
                    # --- Step 19: More robust file existence check for main thread ---
                    if os.path.isfile(file_path): # Ensure it's a file, not a directory
                        print(f"File '{filename}' found. Spawning new thread for {client_address}.")
                        threading.Thread(target=handle_file_transmission, args=(filename, client_address,)).start()
                    else:
                        response_message = f"ERR {filename} NOT_A_FILE"
                        print(f"Path '{filename}' exists but is not a file. Sending ERR to {client_address}")
                        server_socket.sendto(response_message.encode('ascii'), client_address)
                else:
                    response_message = f"ERR {filename} NOT_FOUND"
                    print(f"File '{filename}' not found. Sending ERR to {client_address}")
                    server_socket.sendto(response_message.encode('ascii'), client_address)

            else:
                print(f"Invalid request format: {request_message}. Ignoring.")

        # --- Step 19: Catch general exceptions in main server loop ---
        except Exception as e:
            print(f"An unexpected error occurred in main server loop: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 UDPserver.py <port_number>")
        sys.exit(1)
    try:
        server_port = int(sys.argv[1])
        if not (1024 <= server_port <= 65535):
            raise ValueError("Port number must be between 1024 and 65535.")
    except ValueError as e:
        print(f"Invalid port number: {e}")
        sys.exit(1)
    start_server(server_port)

