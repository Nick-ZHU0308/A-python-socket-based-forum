import socket
import sys
import os
import threading
from collections import defaultdict
import time

# Global variables
CREDENTIALS_FILE = "credentials.txt"
active_users = set()
threads = defaultdict(list)  # thread_title: [creator, messages...]
uploaded_files = defaultdict(dict)  # thread_title: {filename: uploader}

def load_credentials():
    credentials = {}
    if os.path.exists(CREDENTIALS_FILE):
        with open(CREDENTIALS_FILE, 'r') as f:
            for line in f:
                if line.strip():
                    username, password = line.strip().split(' ', 1)
                    credentials[username] = password
    return credentials

def get_valid_user():
    credentials = load_credentials()
    return set(credentials.keys())

def is_valid_thread(filename):
    """验证文件是否为合法线程"""
    if filename == CREDENTIALS_FILE or not os.path.isfile(filename):
        return False
    try:
        with open(filename, 'r') as f:
            first_line = f.readline().strip()
            return first_line in get_valid_user()
    except:
        return False

def save_credentials(credentials):
    with open(CREDENTIALS_FILE, 'w') as f:
        for username, password in credentials.items():
            f.write(f"{username} {password}\n")

def handle_udp_request(data, addr, sock):
    global active_users
    
    parts = data.decode().split(' ', 1)
    if len(parts) < 1:
        return
        
    command = parts[0]
    args = parts[1] if len(parts) > 1 else ""
    
    credentials = load_credentials()
    
    if command == "LOGIN":
        print("Client authenticating...")
        username = args
        if username in active_users:
            sock.sendto(b"USER_LOGGED_IN", addr)
        elif username in credentials:
            sock.sendto(b"USER_EXISTS", addr)
        else:
            sock.sendto(b"NEW_USER", addr)
            
    elif command.startswith("PWD"):
        _, username, password = data.decode().split(' ', 2)
        if credentials.get(username) == password:
            active_users.add(username)
            sock.sendto(b"LOGIN_SUCCESS", addr)
            print(f"{username} logged in successfully")
        else:
            sock.sendto(b"INVALID_PASSWORD", addr)
            print(f"Invalid password for {username}")
            
    elif command.startswith("NEW"):
        _, username, password = data.decode().split(' ', 2)
        credentials[username] = password
        save_credentials(credentials)
        active_users.add(username)
        sock.sendto(b"ACCOUNT_CREATED", addr)
        print(f"New account created for {username}")
        
    elif command == "CRT":
        thread_title, username = args.split(' ', 1)
        if os.path.exists(thread_title):
            sock.sendto(b"Thread already exists", addr)
            print(f"Thread {thread_title} already exists")
        else:
            with open(thread_title, 'w') as f:
                f.write(f"{username}\n")
            sock.sendto(f"Thread {thread_title} created".encode(), addr)
            print(f"Thread {thread_title} created by {username}")
            
    elif command == "MSG":
        parts = args.split(' ', 2)
        if len(parts) < 3:
            sock.sendto(b"Invalid arguments", addr)
            return
            
        thread_title, username, message = parts
        if not os.path.exists(thread_title):
            sock.sendto(b"Thread does not exist", addr)
            return
            
        with open(thread_title, 'a') as f:
            message_num = sum(1 for line in open(thread_title))  # Count lines to get message number
            f.write(f"{message_num} {username}: {message}\n")
        sock.sendto(f"Message posted to {thread_title} thread".encode(), addr)
        
    elif command == "DLT":
        thread_title, message_num, username = args.split(' ', 2)
        if not os.path.exists(thread_title):
            sock.sendto(b"Thread does not exist", addr)
            return
            
        with open(thread_title, 'r') as f:
            lines = f.readlines()
            
        found = False
        new_lines = [lines[0]]  # Keep the creator line
        for line in lines[1:]:
            parts = line.split(' ', 2)
            if len(parts) >= 3 and parts[0] == message_num and parts[1] == f"{username}:":
                found = True
                continue
            new_lines.append(line)
            
        if found:
            with open(thread_title, 'w') as f:
                f.writelines(new_lines)
            sock.sendto(b"Message deleted", addr)
        else:
            sock.sendto(b"Message not found or not yours", addr)
            
    elif command == "EDT":
        parts = args.split(' ', 3)
        if len(parts) < 4:
            sock.sendto(b"Invalid arguments", addr)
            return
            
        thread_title, message_num, username, new_message = parts
        if not os.path.exists(thread_title):
            sock.sendto(b"Thread does not exist", addr)
            return
            
        with open(thread_title, 'r') as f:
            lines = f.readlines()
            
        found = False
        new_lines = []
        for line in lines:
            parts = line.split(' ', 2)
            if len(parts) >= 3 and parts[0] == message_num and parts[1] == f"{username}:":
                new_lines.append(f"{message_num} {username}: {new_message}\n")
                found = True
            else:
                new_lines.append(line)
                
        if found:
            with open(thread_title, 'w') as f:
                f.writelines(new_lines)
            sock.sendto(b"Message edited", addr)
        else:
            sock.sendto(b"Message not found or not yours", addr)

           
    # elif command == "LST":
    #     threads = [f for f in os.listdir() if os.path.isfile(f) and not f.startswith('.') and f != CREDENTIALS_FILE]
    #     if not threads:
    #         sock.sendto(b"No threads to list", addr)
    #     else:
    #         sock.sendto('\n'.join(threads).encode(), addr)

    elif command == "LST":
        all_files = os.listdir()
        valid_threads = [f for f in all_files if is_valid_thread(f)]
        if not valid_threads:
            sock.sendto(b"No threads to list", addr)
        else:
            sock.sendto('\n'.join(valid_threads).encode(), addr)
            
    elif command == "RDT":
        thread_title = args
        if not os.path.exists(thread_title):
            sock.sendto(b"Thread does not exist", addr)
            return
            
        with open(thread_title, 'r') as f:
            content = ''.join(f.readlines()[1:])  # Skip creator line
        sock.sendto(content.encode() if content else b"Thread is empty", addr)
        
    elif command == "UPD":
        parts = args.split(' ', 2)
        if len(parts) < 3:
            sock.sendto(b"Invalid arguments", addr)
            return
            
        thread_title, filename, username = parts
        if not os.path.exists(thread_title):
            sock.sendto(b"Thread does not exist", addr)
            return
            
        # Check if file already exists in thread
        with open(thread_title, 'r') as f:
            for line in f:
                if line.strip().endswith(f"uploaded {filename}"):
                    sock.sendto(b"File already exists in thread", addr)
                    return
                    
        sock.sendto(b"READY", addr)
        
    elif command == "DWN":
        thread_title, filename = args.split(' ', 1)
        server_filename = f"{thread_title}-{filename}"
        if not os.path.exists(thread_title):
            sock.sendto(b"Thread does not exist", addr)
            return
        if not os.path.exists(server_filename):
            sock.sendto(b"File does not exist in thread", addr)
            return
            
        sock.sendto(b"READY", addr)
        
    elif command == "RMV":
        thread_title, username = args.split(' ', 1)
        if not os.path.exists(thread_title):
            sock.sendto(b"Thread does not exist", addr)
            return
            
        with open(thread_title, 'r') as f:
            creator = f.readline().strip()
            
        if creator == username:
            os.remove(thread_title)
            # Remove any files associated with this thread
            for f in os.listdir():
                if f.startswith(f"{thread_title}-"):
                    os.remove(f)
            sock.sendto(b"Thread removed", addr)
        else:
            sock.sendto(b"Thread not created by you", addr)
            
    elif command == "XIT":
        username = args
        active_users.discard(username)
        sock.sendto(b"Goodbye", addr)

def handle_tcp_upload(client_sock, username, filename, thread_title):
    server_filename = f"{thread_title}-{filename}"
    try:
        with open(server_filename, 'wb') as f:
            while True:
                data = client_sock.recv(4096)
                if not data:
                    break
                f.write(data)
                
        # Record the upload in the thread file
        with open(thread_title, 'a') as f:
            f.write(f"{username} uploaded {filename}\n")
            
        print(f"{username} uploaded {filename} to {thread_title}")
    except Exception as e:
        print(f"File upload failed: {e}")
    finally:
        client_sock.close()

def handle_tcp_download(client_sock, filename, thread_title):
    server_filename = f"{thread_title}-{filename}"
    try:
        with open(server_filename, 'rb') as f:
            while True:
                data = f.read(4096)
                if not data:
                    break
                client_sock.sendall(data)
        print(f"{filename} downloaded from {thread_title}")
    except Exception as e:
        print(f"File download failed: {e}")
    finally:
        client_sock.close()

def tcp_server(port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('0.0.0.0', port))
    sock.listen(5)
    print(f"TCP Server started on port {port}. Waiting for clients...")
    
    while True:
        client_sock, addr = sock.accept()
        try:
            initial_data = client_sock.recv(1024).decode()
            if not initial_data:
                continue
                
            if initial_data.startswith("UPLOAD"):
                _, thread_title, filename = initial_data.split(' ', 2)
                client_sock.sendall(b"READY")
                handle_tcp_upload(client_sock, "username", filename, thread_title)
            elif initial_data.startswith("DOWNLOAD"):
                _, thread_title, filename = initial_data.split(' ', 2)
                client_sock.sendall(b"READY")
                handle_tcp_download(client_sock, filename, thread_title)
        except Exception as e:
            print(f"TCP connection error: {e}")
            client_sock.close()

def udp_server(port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('0.0.0.0', port))
    print(f"UDP Server started on port {port}. Waiting for clients...")
    
    while True:
        data, addr = sock.recvfrom(4096)
        threading.Thread(target=handle_udp_request, args=(data, addr, sock)).start()

def main():
    if len(sys.argv) != 2:
        print("Usage: python server.py server_port")
        return
        
    port = int(sys.argv[1])
    
    # Start TCP server in a separate thread
    tcp_thread = threading.Thread(target=tcp_server, args=(port,))
    tcp_thread.daemon = True
    tcp_thread.start()
    
    # Start UDP server in main thread
    udp_server(port)

if __name__ == "__main__":
    main()