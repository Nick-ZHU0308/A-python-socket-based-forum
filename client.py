import socket
import sys
import os
import time

# Global variables
USERNAME = ""
SERVER_PORT = 0
SERVER_ADDR = ('127.0.0.1', SERVER_PORT)

def send_udp_message(sock, message, server_addr):
    max_attempts = 3
    timeout = 2  # seconds
    
    for attempt in range(max_attempts):
        try:
            sock.sendto(message.encode(), server_addr)
            sock.settimeout(timeout)
            response, _ = sock.recvfrom(4096)
            return response.decode()
        except socket.timeout:
            print("Timeout, retrying...")
            continue
    return None

def tcp_upload_file(filename, thread_title, server_addr):
    try:
        with open(filename, 'rb') as file:
            file_data = file.read()
    except FileNotFoundError:
        print(f"File {filename} not found")
        return

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(server_addr)
        sock.sendall(f"UPLOAD {thread_title} {filename}".encode())
        
        # Wait for server ready signal
        response = sock.recv(1024).decode()
        if response != "READY":
            print("Server not ready for upload")
            return
            
        sock.sendall(file_data)
        print(f"{filename} uploaded to {thread_title} thread")
    except Exception as e:
        print(f"Upload failed: {e}")
    finally:
        sock.close()

def tcp_download_file(filename, thread_title, server_addr):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(server_addr)
        sock.sendall(f"DOWNLOAD {thread_title} {filename}".encode())
        
        with open(filename, 'wb') as file:
            while True:
                data = sock.recv(4096)
                if not data:
                    break
                file.write(data)
                
        print(f"{filename} successfully downloaded")
    except Exception as e:
        print(f"Download failed: {e}")
    finally:
        sock.close()

def authenticate(sock, server_addr):
    global USERNAME
    
    while True:
        username = input("Enter username: ")
        response = send_udp_message(sock, f"LOGIN {username}", server_addr)
        
        if not response:
            print("Server not responding")
            continue
            
        if response == "USER_EXISTS":
            password = input("Enter password: ")
            response = send_udp_message(sock, f"PWD {username} {password}", server_addr)
            
            if response == "LOGIN_SUCCESS":
                USERNAME = username
                print("Welcome to the forum")
                return
            else:
                print("Invalid password")
                
        elif response == "USER_LOGGED_IN":
            print("User already logged in")
            continue
            
        elif response == "NEW_USER":
            password = input("New user, enter password: ")
            response = send_udp_message(sock, f"NEW {username} {password}", server_addr)
            
            if response == "ACCOUNT_CREATED":
                USERNAME = username
                print("Account created. Welcome to the forum")
                return
            else:
                print("Account creation failed")
                continue

def main():
    global SERVER_PORT, SERVER_ADDR
    
    if len(sys.argv) != 2:
        print("Usage: python client.py server_port")
        return
        
    SERVER_PORT = int(sys.argv[1])
    SERVER_ADDR = ('127.0.0.1', SERVER_PORT)
    
    # Create UDP socket
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_sock.settimeout(5)
    
    # Authenticate
    authenticate(udp_sock, SERVER_ADDR)
    
    # Command loop
    while True:
        print("\nEnter one of the following commands: CRT, MSG, DLT, EDT, LST, RDT, UPD, DWN, RMV, XIT")
        command = input("> ").strip().upper()
        
        if not command:
            continue
            
        parts = command.split()
        cmd = parts[0]
        
        try:
            if cmd == "CRT" and len(parts) == 2:
                thread_title = parts[1]
                response = send_udp_message(udp_sock, f"CRT {thread_title} {USERNAME}", SERVER_ADDR)
                print(response if response else "No response from server")
                
            elif cmd == "MSG" and len(parts) >= 3:
                thread_title = parts[1]
                message = ' '.join(parts[2:])
                response = send_udp_message(udp_sock, f"MSG {thread_title} {message} {USERNAME}", SERVER_ADDR)
                print(response if response else "No response from server")
                
            elif cmd == "DLT" and len(parts) == 3:
                thread_title = parts[1]
                message_num = parts[2]
                response = send_udp_message(udp_sock, f"DLT {thread_title} {message_num} {USERNAME}", SERVER_ADDR)
                print(response if response else "No response from server")
                
            elif cmd == "EDT" and len(parts) >= 4:
                thread_title = parts[1]
                message_num = parts[2]
                new_message = ' '.join(parts[3:])
                response = send_udp_message(udp_sock, f"EDT {thread_title} {message_num} {new_message} {USERNAME}", SERVER_ADDR)
                print(response if response else "No response from server")
                
            elif cmd == "LST" and len(parts) == 1:
                response = send_udp_message(udp_sock, "LST", SERVER_ADDR)
                print(response if response else "No response from server")
                
            elif cmd == "RDT" and len(parts) == 2:
                thread_title = parts[1]
                response = send_udp_message(udp_sock, f"RDT {thread_title}", SERVER_ADDR)
                print(response if response else "No response from server")
                
            elif cmd == "UPD" and len(parts) == 3:
                thread_title = parts[1]
                filename = parts[2]
                
                if not os.path.exists(filename):
                    print(f"File {filename} not found")
                    continue
                    
                response = send_udp_message(udp_sock, f"UPD {thread_title} {filename} {USERNAME}", SERVER_ADDR)
                
                if response == "READY":
                    tcp_upload_file(filename, thread_title, SERVER_ADDR)
                else:
                    print(response if response else "No response from server")
                    
            elif cmd == "DWN" and len(parts) == 3:
                thread_title = parts[1]
                filename = parts[2]
                response = send_udp_message(udp_sock, f"DWN {thread_title} {filename}", SERVER_ADDR)
                
                if response == "READY":
                    tcp_download_file(filename, thread_title, SERVER_ADDR)
                else:
                    print(response if response else "No response from server")
                    
            elif cmd == "RMV" and len(parts) == 2:
                thread_title = parts[1]
                response = send_udp_message(udp_sock, f"RMV {thread_title} {USERNAME}", SERVER_ADDR)
                print(response if response else "No response from server")
                
            elif cmd == "XIT" and len(parts) == 1:
                response = send_udp_message(udp_sock, f"XIT {USERNAME}", SERVER_ADDR)
                print(response if response else "No response from server")
                if response and response == "Goodbye":
                    break
                    
            else:
                print("Invalid command or arguments")
                
        except Exception as e:
            print(f"Error: {e}")
            
    udp_sock.close()

if __name__ == "__main__":
    main()