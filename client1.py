import socket
import threading
import json
import time
from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout

HOST = '127.0.0.1'
PORT = 12345
FETCH_INTERVAL = 5  # seconds between automatic fetches

def listen_server(sock):
    """Continuously listen for messages from the server and print them."""
    while True:
        try:
            data = sock.recv(1024)
            if not data:
                print("Disconnected from server.")
                break
            for line in data.decode().splitlines():
                try:
                    msg = json.loads(line)
                except Exception:
                    continue

                if msg['type'] == 'status':
                    print(f"Status update for message {msg['id']}: {msg['status']}")
                elif msg['type'] == 'message':
                    print(f"\nNew message from {msg['from']}: {msg['content']}")
        except Exception as e:
            print("Error receiving data:", e)
            break

def auto_fetch(sock):
    """Automatically send fetch requests to the server at regular intervals."""
    while True:
        try:
            fetch_msg = {"type": "fetch"}
            sock.sendall((json.dumps(fetch_msg) + "\n").encode())
        except Exception as e:
            print("Auto-fetch error:", e)
            break
        time.sleep(FETCH_INTERVAL)

def main():
    session = PromptSession()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((HOST, PORT))
    except Exception as e:
        print("Unable to connect to server:", e)
        return

    # Prompt for username
    username = session.prompt("Enter your username: ").strip()
    login = {"type": "login", "username": username}
    sock.sendall((json.dumps(login) + "\n").encode())

    # Start the background threads for listening and auto-fetching
    listener = threading.Thread(target=listen_server, args=(sock,), daemon=True)
    listener.start()
    fetcher = threading.Thread(target=auto_fetch, args=(sock,), daemon=True)
    fetcher.start()

    # Main loop: handle user commands (send or quit)
    with patch_stdout():
        while True:
            try:
                command = session.prompt("\nEnter command (send/quit): ").strip()
            except KeyboardInterrupt:
                continue
            except EOFError:
                break

            if command == "quit":
                break
            elif command.startswith("send"):
                parts = command.split(" ", 2)
                if len(parts) < 3:
                    print("Usage: send <recipient> <message>")
                    continue
                recipient = parts[1]
                content = parts[2]
                message = {"type": "send", "from": username, "to": recipient, "content": content}
                try:
                    sock.sendall((json.dumps(message) + "\n").encode())
                    print("Message sent, status: not yet delivered (pending server ack)")
                except Exception as e:
                    print("Failed to send message:", e)
            else:
                print("Unknown command. Use 'send' or 'quit'.")
    sock.close()

if __name__ == '__main__':
    main()
