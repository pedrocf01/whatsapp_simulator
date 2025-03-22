import socket
import threading
import json

HOST = '127.0.0.1'
PORT = 12345

# Global dictionaries to track online clients and pending messages
clients = {}         # username -> socket
message_queues = {}  # username -> list of messages
lock = threading.Lock()
message_id_counter = 0

def handle_client(conn, addr):
    global message_id_counter
    username = None
    try:
        while True:
            data = conn.recv(1024)
            if not data:
                break
            # Process each JSON message (one per line)
            for line in data.decode().splitlines():
                try:
                    msg = json.loads(line)
                except Exception as e:
                    print("Error decoding message:", e)
                    continue

                if msg['type'] == 'login':
                    username = msg['username']
                    with lock:
                        clients[username] = conn
                        if username not in message_queues:
                            message_queues[username] = []
                    print(f"{username} logged in from {addr}")

                elif msg['type'] == 'send':
                    # Assign a unique id to the message
                    with lock:
                        message_id_counter += 1
                        msg_id = message_id_counter
                    msg['id'] = msg_id
                    recipient = msg['to']

                    # Acknowledge to sender that the message has been received by the server.
                    ack = {"type": "status", "id": msg_id, "status": "server"}
                    conn.sendall((json.dumps(ack) + "\n").encode())

                    # Store message in recipient's queue
                    with lock:
                        if recipient not in message_queues:
                            message_queues[recipient] = []
                        message_queues[recipient].append(msg)

                    # If the recipient is online, try to deliver immediately.
                    with lock:
                        if recipient in clients:
                            try:
                                clients[recipient].sendall(
                                    (json.dumps({
                                        "type": "message",
                                        "from": msg["from"],
                                        "content": msg["content"],
                                        "id": msg_id
                                    }) + "\n").encode()
                                )
                                # Notify the sender that the message was delivered.
                                delivered = {"type": "status", "id": msg_id, "status": "delivered"}
                                conn.sendall((json.dumps(delivered) + "\n").encode())
                                # Remove the message from the queue now that it has been sent.
                                message_queues[recipient] = [
                                    m for m in message_queues[recipient] if m["id"] != msg_id
                                ]
                            except Exception as e:
                                print("Error delivering to recipient:", e)

                elif msg['type'] == 'fetch':
                    # Client requests any pending messages
                    with lock:
                        queue = message_queues.get(username, [])
                        message_queues[username] = []  # clear the queue after fetching
                    for m in queue:
                        try:
                            conn.sendall(
                                (json.dumps({
                                    "type": "message",
                                    "from": m["from"],
                                    "content": m["content"],
                                    "id": m["id"]
                                }) + "\n").encode()
                            )
                            # Notify the sender that the message has been delivered.
                            sender = m["from"]
                            if sender in clients:
                                status_update = {"type": "status", "id": m["id"], "status": "delivered"}
                                clients[sender].sendall((json.dumps(status_update) + "\n").encode())
                        except Exception as e:
                            # If sending fails, re-queue the message.
                            with lock:
                                message_queues[username].append(m)
    except Exception as e:
        print("Exception:", e)
    finally:
        if username:
            with lock:
                if username in clients:
                    del clients[username]
        conn.close()
        print(f"{username} disconnected.")

def main():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((HOST, PORT))
    server_socket.listen()
    print("Server listening on", HOST, PORT)
    while True:
        conn, addr = server_socket.accept()
        thread = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
        thread.start()

if __name__ == '__main__':
    main()
