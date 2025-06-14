# UDPClient.py
import socket
import sys
import os
import time
import base64 # Import base64 module for decoding

def send_and_receive(sock, message, server_address_tuple, initial_timeout_ms=1000, max_retries=5, current_server_port=None):
    encoded_message = message.encode('ascii')
    current_timeout = initial_timeout_ms
    
    target_address = (server_address_tuple[0], current_server_port) if current_server_port else server_address_tuple

    for i in range(max_retries):
        try:
            sock.settimeout(current_timeout / 1000.0)
            # print(f"[send_and_receive] Sending '{message}' to {target_address} (Timeout: {current_timeout}ms, Attempt: {i+1}/{max_retries})")
            sock.sendto(encoded_message, target_address)
            
            response_data, sender_addr = sock.recvfrom(8192) # Max UDP packet size is usually 65507 bytes. 8192 is safe for Base64 of 1000 bytes.
            response_message = response_data.decode('ascii').strip()
            # print(f"[send_and_receive] Received response: '{response_message}' from {sender_addr}")
            return response_message, sender_addr
        except socket.timeout:
            print(f"[send_and_receive] Timeout. No response from {target_address}. Retrying...")
            current_timeout *= 2
        except Exception as e:
            print(f"[send_and_receive] An unexpected error occurred: {e}. Aborting send/receive.")
            return None, None
    
    print(f"[send_and_receive] Max retries ({max_retries}) reached. Failed to get response for '{message}'.")
    return None, None

def start_client(server_host, server_port, files_list_path):
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print(f"UDP Client starting. Target server: {server_host}:{server_port}")

    if not os.path.exists("client_files"):
        os.makedirs("client_files")
        print("Created 'client_files' directory.")

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
    
    response, sender = send_and_receive(client_socket, download_message, (server_host, server_port), 
                                        initial_timeout_ms=1000, max_retries=5, current_server_port=None)

    if not response:
        print("Failed to get response from server after retries. Exiting.")
        client_socket.close()
        return

    parts = response.split(" ")
    if not parts:
        print("Received empty response after send_and_receive.")
        client_socket.close()
        return

    status = parts[0]
    resp_filename = parts[1] if len(parts) > 1 else "N/A"

    if status == "OK":
        if len(parts) >= 6 and parts[2] == "SIZE" and parts[4] == "PORT":
            try:
                file_size = int(parts[3])
                data_port = int(parts[5])
                print(f"Server confirms OK for '{resp_filename}'. Size: {file_size} bytes, Data Port: {data_port}")

                local_file_path = os.path.join("client_files", resp_filename)
                try:
                    with open(local_file_path, 'wb') as f:
                        print(f"Created local file: {local_file_path}")
                        downloaded_bytes = 0 
                        print("Download Progress: ", end="") 
                        sys.stdout.flush()

                        # --- Start of Step 15 additions ---
                        chunk_size = 1000 # Protocol states up to 1000 bytes of binary data per message
                        
                        while downloaded_bytes < file_size:
                            start_byte = downloaded_bytes
                            # Calculate end_byte (inclusive)
                            # Make sure we don't request beyond file_size - 1
                            end_byte = min(file_size - 1, start_byte + chunk_size - 1) 
                            
                            if start_byte > end_byte and downloaded_bytes < file_size: # Should not happen if loop condition is correct
                                print("\nWarning: Calculated empty range before full download. Breaking.")
                                break

                            get_message = f"FILE {resp_filename} GET START {start_byte} END {end_byte}"
                            
                            # Use the data_port provided by the server for GET requests
                            data_response, sender_addr = send_and_receive(
                                client_socket, get_message, (server_host, server_port), # server_port is the initial one, but current_server_port will override
                                initial_timeout_ms=1000, max_retries=5, current_server_port=data_port
                            )

                            if not data_response:
                                print(f"\nFailed to get data for {resp_filename} bytes {start_byte}-{end_byte}. Aborting download.")
                                # Mark as failed to avoid sending CLOSE for incomplete file
                                downloaded_bytes = -1 
                                break

                            data_parts = data_response.split(" ", 7) # Split into 7 parts plus the remaining data (DATA ...)
                            # Expected format: FILE <filename> OK START <start> END <end> DATA <encoded_data>
                            if len(data_parts) == 8 and \
                               data_parts[0] == "FILE" and data_parts[1] == resp_filename and \
                               data_parts[2] == "OK" and data_parts[3] == "START" and data_parts[5] == "END" and \
                               data_parts[7].startswith("DATA "): # Check if the last part starts with "DATA "
                                try:
                                    resp_start_byte = int(data_parts[4])
                                    resp_end_byte = int(data_parts[6])
                                    encoded_data = data_parts[7][5:].strip() # Extract Base64 string after "DATA "
                                    decoded_data = base64.b64decode(encoded_data)

                                    if resp_start_byte != start_byte or resp_end_byte != end_byte:
                                        print(f"\nWarning: Received data for unexpected range {resp_start_byte}-{resp_end_byte}, expected {start_byte}-{end_byte}. Attempting to write anyway.")
                                    
                                    # Write data to the correct position in the file
                                    f.seek(resp_start_byte)
                                    f.write(decoded_data)
                                    downloaded_bytes += len(decoded_data) # Update total downloaded bytes

                                    print("*", end="") # Print progress indicator
                                    sys.stdout.flush() # Ensure it's immediately visible

                                except (ValueError, IndexError, base64.binascii.Error) as e:
                                    print(f"\nError decoding or processing data for {resp_filename}: {e}. Aborting download.")
                                    downloaded_bytes = -1
                                    break
                            else:
                                print(f"\nInvalid data response format for {resp_filename}: {data_response}. Aborting download.")
                                downloaded_bytes = -1
                                break
                        
                        print("\nFile data transfer loop finished.") # Newline after progress stars
                        # --- End of Step 15 additions ---

                except IOError as e:
                    print(f"Error: Could not open/write to local file '{local_file_path}'. {e}")
                except Exception as e:
                    print(f"An unexpected error occurred during file transfer of '{resp_filename}': {e}")
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

