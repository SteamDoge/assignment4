# UDPClient.py
import socket
import sys
import os
import time

def send_and_receive(sock, message, server_address_tuple, initial_timeout_ms=1000, max_retries=5, current_server_port=None):
    encoded_message = message.encode('ascii')
    current_timeout = initial_timeout_ms
    
    target_address = (server_address_tuple[0], current_server_port) if current_server_port else server_address_tuple

    for i in range(max_retries):
        try:
            sock.settimeout(current_timeout / 1000.0)
            # print(f"[send_and_receive] Sending '{message}' to {target_address} (Timeout: {current_timeout}ms, Attempt: {i+1}/{max_retries})")
            sock.sendto(encoded_message, target_address)
            
            response_data, sender_addr = sock.recvfrom(8192)
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

    # Ensure 'client_files' directory exists for downloaded files
    if not os.path.exists("client_files"):
        os.makedirs("client_files")
        print("Created 'client_files' directory.")

    # Read filenames to download (still processing only the first one for now)
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
    
    # Send DOWNLOAD request using the reliable send_and_receive function
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

                # --- Start of Step 12 additions ---
                local_file_path = os.path.join("client_files", resp_filename)
                try:
                    # Open file in binary write mode ('wb'), which creates/truncates it
                    with open(local_file_path, 'wb') as f:
                        print(f"Created local file: {local_file_path}")
                        downloaded_bytes = 0 # Initialize downloaded bytes counter
                        print("Download Progress: ", end="") # Prepare for progress display
                        sys.stdout.flush() # Ensure "Download Progress: " is printed immediately

                        # In future steps, we will loop here to request and receive data chunks
                        # For now, just create the file and prepare for progress display.
                        print("\nFile prepared for download. No data transfer yet.") # Indicate current state

                except IOError as e:
                    print(f"Error: Could not open/write to local file '{local_file_path}'. {e}")
                # --- End of Step 12 additions ---

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

