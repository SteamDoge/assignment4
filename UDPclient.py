import socket
import sys
import os
import base64
import time
import math

# --- Configuration ---
CHUNK_SIZE = 1000       # Bytes of raw data expected per chunk
MAX_RETRIES = 5         # Max retransmission attempts for a chunk
INITIAL_TIMEOUT = 1.0   # Initial timeout for stop-and-wait (seconds)
TIMEOUT_MULTIPLIER = 2  # Multiplier for exponential backoff
CLIENT_FILES_DIR = 'client_files' # Directory where downloaded files are saved

# --- Helper Function to ensure directory exists ---
def ensure_dir(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)
        print(f"Created directory: {directory}")

# --- Function to send and wait for a response ---
def send_and_receive(sock, message, server_address, timeout, max_retries):
    """
    Sends a message and waits for a response with timeout and retransmissions.
    Returns (response_data, sender_address) or (None, None) on failure.
    """
    encoded_message = message.encode('utf-8')
    retries = 0
    current_timeout = timeout

    while retries < max_retries:
        try:
            sock.sendto(encoded_message, server_address)
            sock.settimeout(current_timeout)
            response_data, sender_address = sock.recvfrom(2048) # Buffer for response
            return response_data, sender_address
        except socket.timeout:
            retries += 1
            # For brevity in logs, only print first line of message if it's multi-line (e.g., REQ messages)
            log_message = message.splitlines()[0] 
            print(f"Timeout (attempt {retries}/{max_retries}) for '{log_message}'. Retrying with timeout {current_timeout * TIMEOUT_MULTIPLIER:.2f}s...")
            current_timeout *= TIMEOUT_MULTIPLIER # Exponential backoff
        except Exception as e:
            log_message = message.splitlines()[0]
            print(f"Error sending/receiving for '{log_message}': {e}")
            return None, None
    log_message = message.splitlines()[0]
    print(f"Max retries reached for '{log_message}'. Giving up.")
    return None, None

# --- Main Client Logic ---
def run_client(server_host, server_port, files_list_path):
    ensure_dir(CLIENT_FILES_DIR) # Ensure the client_files directory exists

    # The main_client_socket will only be used to get the server_address initially, 
    # not for sending/receiving as we'll use per-file sockets.
    # We still need it to define server_address for initial connections.
    server_address = (server_host, server_port)

    # Read files to download
    files_to_download = []
    try:
        with open(files_list_path, 'r') as f:
            for line in f:
                filename = line.strip()
                if filename: # Ignore empty lines
                    files_to_download.append(filename)
    except FileNotFoundError:
        print(f"Error: Files list '{files_list_path}' not found.")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading files list '{files_list_path}': {e}")
        sys.exit(1)

    if not files_to_download:
        print("No files listed in files.txt to download. Exiting.")
        sys.exit(0)

    print(f"Starting download of {len(files_to_download)} files from {server_host}:{server_port}")

    for filename in files_to_download:
        print(f"\n--- Attempting to download: {filename} ---")
        
        # --- MODIFICATION START ---
        # Create a new socket for *each* initial DOWNLOAD handshake.
        # This isolates responses for each file, preventing old messages from interfering.
        initial_handshake_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Bind to a random available port to ensure a clean slate for this specific handshake.
        initial_handshake_socket.bind(('', 0)) 
        # --- MODIFICATION END ---

        # Step 1: Send DOWNLOAD request to main server port
        download_request = f"DOWNLOAD {filename}"
        
        # Use the NEWLY created initial_handshake_socket for this specific download request
        response_data, _ = send_and_receive(initial_handshake_socket, download_request, server_address, INITIAL_TIMEOUT, MAX_RETRIES)

        # --- MODIFICATION START ---
        # Close the socket immediately after getting the response for this handshake.
        initial_handshake_socket.close() 
        # --- MODIFICATION END ---

        if response_data is None:
            print(f"Failed to get DOWNLOAD response for '{filename}'. Skipping to next file.")
            continue # Move to next file
        
        response_msg = response_data.decode('utf-8').strip()
        parts = response_msg.split()

        if len(parts) == 6 and parts[0] == "OK" and parts[1] == filename and parts[2] == "SIZE" and parts[4] == "PORT":
            try:
                file_size = int(parts[3])
                data_port = int(parts[5])
                print(f"Server confirms OK for '{filename}'. Size: {file_size} bytes, Data Port: {data_port}")

                # Step 2: Initiate file transfer on the new data port
                data_server_address = (server_host, data_port)
                # Create a new socket for data transfer for this file.
                # This socket will be used for all chunk requests and responses for the current file.
                data_transfer_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                # Client's data socket doesn't need to bind to a specific port for outgoing messages.
                # It will automatically be assigned an ephemeral port.
                
                output_file_path = os.path.join(CLIENT_FILES_DIR, filename)
                current_offset = 0
                
                print(f"Created local file: {output_file_path}")
                print("Download Progress: ", end='', flush=True)

                try:
                    with open(output_file_path, 'wb') as f:
                        while current_offset < file_size:
                            # Calculate the end byte for the current chunk
                            chunk_end_byte = min(current_offset + CHUNK_SIZE - 1, file_size - 1)
                            
                            # Handle case of 0-byte file (file_size=0) or last chunk where no more data
                            if file_size == 0 or chunk_end_byte < current_offset: 
                                break 
                            
                            # Send REQ for the next chunk
                            chunk_request = f"REQ {filename} START {current_offset} END {chunk_end_byte}"
                            chunk_response_data, _ = send_and_receive(data_transfer_socket, chunk_request, data_server_address, INITIAL_TIMEOUT, MAX_RETRIES)

                            if chunk_response_data is None:
                                print(f"\nFailed to receive chunk for offset {current_offset}. Aborting download of '{filename}'.")
                                break # Break from inner while loop

                            chunk_response_msg = chunk_response_data.decode('utf-8').strip()
                            chunk_parts = chunk_response_msg.split(' ', 5) # Split into 5 parts, the last one being the base64 data

                            if len(chunk_parts) == 6 and chunk_parts[0] == "DATA" and \
                               chunk_parts[1] == filename and chunk_parts[2] == "START" and \
                               chunk_parts[4] == "END":
                                
                                try:
                                    received_start_byte = int(chunk_parts[3])
                                    # The last part includes "END <end_byte> <base64_data>"
                                    # We need to split that again to get just the end_byte
                                    end_byte_str, encoded_chunk = chunk_parts[5].split(' ', 1) 
                                    received_end_byte = int(end_byte_str)
                                except ValueError:
                                    print(f"\nError parsing chunk start/end bytes for '{filename}'. Skipping this chunk.")
                                    continue # Skip to next iteration, possibly re-requesting same chunk

                                if received_start_byte == current_offset:
                                    try:
                                        decoded_chunk = base64.b64decode(encoded_chunk)
                                        # Ensure we don't write beyond file size if chunk is malformed
                                        if current_offset + len(decoded_chunk) > file_size:
                                            decoded_chunk = decoded_chunk[:file_size - current_offset] # Truncate if too long
                                        
                                        f.seek(current_offset) # Seek to the correct position
                                        f.write(decoded_chunk)
                                        current_offset += len(decoded_chunk)
                                        print("*", end='', flush=True) # Print progress indicator
                                    except Exception as e:
                                        print(f"\nError decoding or writing chunk for '{filename}': {e}. Skipping this chunk.")
                                else:
                                    print(f"\nWarning: Received out-of-order chunk for '{filename}'. Expected offset {current_offset}, got {received_start_byte}. Retrying current chunk.")
                                    # If out-of-order, don't advance offset. Next iteration will re-request current_offset.
                            elif chunk_parts[0] == "FILE" and chunk_parts[1] == filename and chunk_parts[2] == "CLOSE_OK":
                                # This can happen if the server already finished sending and client was late with a REQ
                                # or if the file was very small and server sent CLOSE_OK immediately after the only chunk.
                                print("\nServer sent CLOSE_OK prematurely (or file was fully downloaded).")
                                break # Exit the chunk loop if server says it's done
                            elif chunk_parts[0] == "ERR" and chunk_parts[1] == filename and chunk_parts[2] == "NOT_FOUND":
                                print(f"\nServer reported '{filename}' not found during data transfer. Aborting.")
                                break
                            else:
                                print(f"\nReceived unexpected data packet format for '{filename}': {chunk_response_msg}")
                                # Decide whether to retry or abort
                                break # Abort for now

                        # After the loop, send FILE CLOSE and wait for confirmation
                        # Only send if we managed to initiate download and not if the file size was 0
                        if file_size > 0 and current_offset >= file_size: 
                            print("\nFile data transfer loop finished successfully.")
                            # Send final FILE CLOSE request
                            close_request = f"FILE {filename} CLOSE"
                            final_response_data, _ = send_and_receive(data_transfer_socket, close_request, data_server_address, INITIAL_TIMEOUT, MAX_RETRIES)

                            if final_response_data is None:
                                print(f"Warning: Did not receive final CLOSE_OK for '{filename}'.")
                            else:
                                final_response_msg = final_response_data.decode('utf-8').strip()
                                if final_response_msg == f"FILE {filename} CLOSE_OK":
                                    print(f"Successfully downloaded '{filename}'. Received CLOSE_OK.")
                                else:
                                    print(f"Received unexpected final response: {final_response_msg}")
                        elif file_size == 0 and current_offset == 0:
                            print("\nFile was 0 bytes, no data transfer needed. Treated as successful.")
                            # For 0-byte files, we don't need to send CLOSE. Server likely sent CLOSE_OK immediately.
                        else:
                            print(f"\nDownload of '{filename}' incomplete. Received {current_offset}/{file_size} bytes.")

                except FileNotFoundError:
                    print(f"\nError: Could not create local file '{output_file_path}'. Check permissions or path.")
                except Exception as e:
                    print(f"\nAn error occurred during file transfer for '{filename}': {e}")
                finally:
                    data_transfer_socket.close() # Close the data transfer socket for this file
                    print(f"Data transfer socket for '{filename}' closed.")

            except ValueError as e:
                print(f"Error parsing server OK response: {e}. Response was: {response_msg}")
            except Exception as e:
                print(f"An unexpected error occurred after receiving OK response for '{filename}': {e}")

        elif len(parts) == 3 and parts[0] == "ERR" and parts[1] == filename and parts[2] == "NOT_FOUND":
            print(f"Server reported '{filename}' NOT_FOUND. Skipping to next file.")
        else:
            print(f"Received unexpected initial response from server: {response_msg}. Skipping to next file.")
            
    print("\nAll downloads attempted. Client exiting.")

# --- Entry Point ---
if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python3 UDPClient.py <server_hostname> <server_port_number> <files_list.txt>")
        sys.exit(1)

    SERVER_HOST = sys.argv[1]
    try:
        SERVER_PORT = int(sys.argv[2])
        if not (1024 <= SERVER_PORT <= 65535):
            raise ValueError("Server port number must be between 1024 and 65535.")
    except ValueError as e:
        print(f"Error: Invalid server port number. {e}")
        sys.exit(1)
    
    FILES_LIST_PATH = sys.argv[3]

    print(f"UDP Client starting. Target server: {SERVER_HOST}:{SERVER_PORT} with file list {FILES_LIST_PATH}")

    run_client(SERVER_HOST, SERVER_PORT, FILES_LIST_PATH)

