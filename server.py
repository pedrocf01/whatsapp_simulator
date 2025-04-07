import socket
import threading
import json

HOST = '127.0.0.1'
PORT = 12345

# Dicionários globais para rastrear clientes online e mensagens pendentes
clientes = {}         # nome de usuário -> socket
filas_mensagem = {}   # nome de usuário -> lista de mensagens
lock = threading.Lock()

def login(conn, msg, addr):
    """Processa a mensagem de login, registra o usuário e inicializa sua fila."""
    username = msg.get('username')
    with lock:
        clientes[username] = conn
        if username not in filas_mensagem:
            filas_mensagem[username] = []
    print(f"{username} fez login a partir de {addr}")
    return username

def send(conn, msg):
    """Processa o envio de mensagens, confirma recebimento e tenta entrega imediata."""
    msg_id = msg.get('id')
    destinatario = msg.get('to')
    
    # Confirma para o remetente que o servidor recebeu a mensagem.
    ack = {"tipo": "status", "id": msg_id, "status": "✓"}
    conn.sendall((json.dumps(ack) + "\n").encode())

    # Armazena a mensagem na fila do destinatário.
    with lock:
        if destinatario not in filas_mensagem:
            filas_mensagem[destinatario] = []
        filas_mensagem[destinatario].append(msg)

    # Tenta entregar imediatamente se o destinatário estiver online.
    with lock:
        if destinatario in clientes:
            try:
                delivery_msg = {
                    "tipo": "mensagem",
                    "from": msg.get("from"),
                    "conteudo": msg.get("conteudo"),
                    "timestamp": msg.get("timestamp"),
                    "id": msg_id
                }
                clientes[destinatario].sendall((json.dumps(delivery_msg) + "\n").encode())
                # Notifica o remetente que a mensagem foi entregue.
                entregue = {"tipo": "status", "id": msg_id, "status": "✓✓"}
                conn.sendall((json.dumps(entregue) + "\n").encode())
                # Remove a mensagem da fila do destinatário.
                filas_mensagem[destinatario] = [
                    m for m in filas_mensagem[destinatario] if m.get("id") != msg_id
                ]
            except Exception as e:
                print("Erro ao entregar ao destinatário:", e)

def fetch(conn, username):
    """Processa a requisição de fetch do cliente, enviando mensagens pendentes."""
    if not username:
        return

    with lock:
        mensagens = filas_mensagem.get(username, [])
        filas_mensagem[username] = []  # Limpa a fila após a busca

    for m in mensagens:
        try:
            delivery_msg = {
                "tipo": "mensagem",
                "from": m.get("from"),
                "conteudo": m.get("conteudo"),
                "timestamp": m.get("timestamp"),
                "id": m.get("id")
            }
            conn.sendall((json.dumps(delivery_msg) + "\n").encode())
            # Notifica o remetente que a mensagem foi entregue.
            remetente = m.get("from")
            if remetente in clientes:
                status_update = {"tipo": "status", "id": m.get("id"), "status": "✓✓"}
                clientes[remetente].sendall((json.dumps(status_update) + "\n").encode())
        except Exception as e:
            print("Erro ao enviar mensagem pendente:", e)
            with lock:
                filas_mensagem[username].append(m)

def cleanup_client(username):
    global clientes
    if username:
        with lock:
            if username in clientes:
                del clientes[username]
                print(f"{username} saiu do chat.")

def handle_client(conn, addr):
    username = None
    try:
        while True:
            data = conn.recv(1024)
            if not data:
                break

            # Processa cada linha de dados (cada linha corresponde a uma mensagem JSON)
            for line in data.decode().splitlines():
                try:
                    msg = json.loads(line)
                except Exception as e:
                    continue

                tipo = msg.get('tipo')
                if tipo == 'login':
                    username = login(conn, msg, addr)
                elif tipo == 'send':
                    send(conn, msg)
                elif tipo == 'fetch':
                    fetch(conn, username)
                elif tipo == "logout":
                    username = msg.get("username")
                    cleanup_client(username)
                    username = None    
                else:
                    print("Tipo de mensagem desconhecido:", tipo)

    except Exception as e:
        print("Exceção:", e)
    finally:
        cleanup_client(username)
        conn.close()

def main():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((HOST, PORT))
    server_socket.listen()
    print("Servidor ouvindo em", HOST, PORT)
    while True:
        conn, addr = server_socket.accept()
        thread = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
        thread.start()

if __name__ == '__main__':
    main()
