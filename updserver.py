# UDPServer.py
import socket
import sys
import os # Import os for file path operations

def start_server(port):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        server_socket.bind(('', port))
        print(f"UDP Server listening on port {port}")
    except OSError as e:
        print(f"Error: Could not bind to port {port}. {e}")
        sys.exit(1)

    # Ensure 'files' directory exists for storing files
    if not os.path.exists("files"):
        os.makedirs("files")
        print("Created 'files' directory.")

    while True:
        try:
            request_data, client_address = server_socket.recvfrom(4096)
            request_message = request_data.decode('ascii').strip()
            print(f"Received request from {client_address}: {request_message}")

            # --- Start of Step 5 additions ---
            parts = request_message.split(" ")
            
            # Check for correct DOWNLOAD message format
            if len(parts) == 2 and parts[0] == "DOWNLOAD":
                filename = parts[1]
                file_path = os.path.join("files", filename) # Construct full path
                
                response_message = ""
                if os.path.exists(file_path):
                    # For now, we'll use dummy values for SIZE and PORT.
                    # Actual file size and dynamic port will be added in later steps.
                    dummy_file_size = 0 
                    dummy_data_port = 0
                    response_message = f"OK {filename} SIZE {dummy_file_size} PORT {dummy_data_port}"
                    print(f"File '{filename}' found. Sending OK to {client_address}")
                else:
                    response_message = f"ERR {filename} NOT_FOUND"
                    print(f"File '{filename}' not found. Sending ERR to {client_address}")
                
                # Send the response back to the client
                server_socket.sendto(response_message.encode('ascii'), client_address)

            else:
                print(f"Invalid request format: {request_message}. Ignoring.")
            # --- End of Step 5 additions ---

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

