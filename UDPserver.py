import socket
import threading
import os
import base64
import math
import time
import sys

# --- Configuration ---
SERVER_HOST = '0.0.0.0' # Listen on all available interfaces
CHUNK_SIZE = 1000       # Bytes of raw data per chunk
MAX_RETRIES = 5         # Max retransmission attempts for client
INITIAL_TIMEOUT = 1     # Initial timeout for client's stop-and-wait
FILES_DIR = 'files'     # Directory where files are stored on server
CLIENT_FILES_DIR = 'client_files' # Not used by server, but good to define if needed later

# --- Helper Function to ensure directory exists ---
def ensure_dir(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)
        print(f"Created directory: {directory}")

# --- File Transfer Handler for a single client/file ---
def handle_file_transfer(data_socket, client_address, filename, file_size):
    """
    Handles the reliable transfer of a single file to a specific client.
    This runs in a new thread for each file download.
    """
    print(f"[Thread {threading.get_ident()}] Handling transfer of '{filename}' to {client_address} via port {data_socket.getsockname()[1]}")

    file_path = os.path.join(FILES_DIR, filename)
    current_offset = 0 # Keep track of the current byte offset in the file

    try:
        with open(file_path, 'rb') as f:
            while current_offset < file_size:
                # 1. Receive client's request for the next chunk
                try:
                    # Expecting "REQ <filename> START <start_byte> END <end_byte>"
                    request_data, _ = data_socket.recvfrom(2048) # Sufficient buffer for request
                    request_msg = request_data.decode('utf-8').strip()
                    parts = request_msg.split()

                    if len(parts) == 6 and parts[0] == "REQ" and parts[1] == filename and parts[2] == "START" and parts[4] == "END":
                        req_start_byte = int(parts[3])
                        req_end_byte = int(parts[5])
                        
                        # Basic validation: requested chunk must match what we expect to send next
                        if req_start_byte != current_offset:
                            print(f"[Thread {threading.get_ident()}] Warning: Client requested offset {req_start_byte}, but expected {current_offset}. Retransmitting previous chunk if needed.")
                            # For simple stop-and-wait, we might just re-send the expected chunk.
                            # In a more complex ARQ, we'd need sequence numbers to handle out-of-order/duplicates.
                            # For now, we'll try to serve the requested chunk.

                        # Read the chunk from the file
                        f.seek(req_start_byte)
                        chunk = f.read(req_end_byte - req_start_byte + 1)
                        
                        # Base64 encode the chunk
                        encoded_chunk = base64.b64encode(chunk).decode('utf-8')
                        
                        # Construct the response packet
                        response_msg = f"DATA {filename} START {req_start_byte} END {req_end_byte} {encoded_chunk}"
                        
                        data_socket.sendto(response_msg.encode('utf-8'), client_address)
                        print(f"[Thread {threading.get_ident()}] Sent chunk {req_start_byte}-{req_end_byte} for '{filename}'.")
                        
                        # Only advance offset if we sent the expected chunk
                        if req_start_byte == current_offset:
                           current_offset += len(chunk)
                    else:
                        print(f"[Thread {threading.get_ident()}] Received invalid request: {request_msg}")
                        # Optionally send an error back, or just ignore
                        
                except socket.timeout:
                    print(f"[Thread {threading.get_ident()}] Socket timeout waiting for client's REQ. Client might have disconnected or timed out.")
                    break # Exit loop if client stops responding
                except ValueError as e:
                    print(f"[Thread {threading.get_ident()}] Error parsing client request: {e}. Request was: {request_msg}")
                    break
                except Exception as e:
                    print(f"[Thread {threading.get_ident()}] An unexpected error occurred during chunk transfer: {e}")
                    break

            # After sending all chunks, send FILE CLOSE confirmation
            if current_offset >= file_size:
                close_msg = f"FILE {filename} CLOSE_OK"
                data_socket.sendto(close_msg.encode('utf-8'), client_address)
                print(f"[Thread {threading.get_ident()}] Finished sending all chunks for '{filename}'. Sent CLOSE_OK.")
            else:
                print(f"[Thread {threading.get_ident()}] Transfer of '{filename}' did not complete. Sent {current_offset}/{file_size} bytes.")

    except FileNotFoundError:
        error_msg = f"ERR {filename} NOT_FOUND"
        data_socket.sendto(error_msg.encode('utf-8'), client_address)
        print(f"[Thread {threading.get_ident()}] Error: File '{filename}' not found for transfer.")
    except Exception as e:
        print(f"[Thread {threading.get_ident()}] An error occurred while opening or reading file '{filename}': {e}")
    finally:
        data_socket.close()
        print(f"[Thread {threading.get_ident()}] Data socket for '{filename}' closed.")

# --- Main Server Logic ---
def run_server(server_port):
    ensure_dir(FILES_DIR) # Ensure the files directory exists

    main_server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        main_server_socket.bind((SERVER_HOST, server_port))
        print(f"UDP Server listening on {SERVER_HOST}:{server_port}")
    except socket.error as e:
        print(f"Error: Could not bind to port {server_port}. Reason: {e}")
        print("Please check if the port is already in use or if you have sufficient permissions.")
        sys.exit(1) # Exit if cannot bind

    while True:
        try:
            # Main socket listens for initial DOWNLOAD requests
            data, client_address = main_server_socket.recvfrom(1024) # Small buffer for initial request
            message = data.decode('utf-8').strip()
            print(f"Received message from {client_address}: {message}")

            parts = message.split()
            if len(parts) == 2 and parts[0] == "DOWNLOAD":
                filename = parts[1]
                file_path = os.path.join(FILES_DIR, filename)

                if os.path.exists(file_path) and os.path.isfile(file_path):
                    file_size = os.path.getsize(file_path)
                    
                    # Create a new UDP socket for this specific file transfer
                    data_transfer_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    # Bind to an ephemeral (random available) port
                    data_transfer_socket.bind((SERVER_HOST, 0)) 
                    data_port = data_transfer_socket.getsockname()[1] # Get the assigned port number

                    # Send OK response to client
                    ok_response = f"OK {filename} SIZE {file_size} PORT {data_port}"
                    main_server_socket.sendto(ok_response.encode('utf-8'), client_address)
                    print(f"Sent OK for '{filename}' (Size: {file_size}, Data Port: {data_port}) to {client_address}")

                    # Start a new thread to handle the file transfer
                    # Pass the *new* data_transfer_socket to the thread
                    thread = threading.Thread(target=handle_file_transfer, 
                                              args=(data_transfer_socket, client_address, filename, file_size))
                    thread.daemon = True # Allow main program to exit even if threads are running
                    thread.start()
                    print(f"Started new thread (ID: {thread.ident}) for '{filename}'.")

                else:
                    error_response = f"ERR {filename} NOT_FOUND"
                    main_server_socket.sendto(error_response.encode('utf-8'), client_address)
                    print(f"Sent ERR NOT_FOUND for '{filename}' to {client_address}")
            else:
                print(f"Received unknown command: {message} from {client_address}")

        except KeyboardInterrupt:
            print("\nServer shutting down...")
            break
        except Exception as e:
            print(f"An unexpected error occurred in main server loop: {e}")
            # Continue listening or decide to break based on error severity

    main_server_socket.close()
    print("Main server socket closed. Server gracefully stopped.")

# --- Entry Point ---
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 UDPServer.py <port_number>")
        sys.exit(1)
    
    try:
        port = int(sys.argv[1])
        if not (1024 <= port <= 65535): # Standard port range
            raise ValueError("Port number must be between 1024 and 65535.")
    except ValueError as e:
        print(f"Error: Invalid port number. {e}")
        sys.exit(1)

    run_server(port)

