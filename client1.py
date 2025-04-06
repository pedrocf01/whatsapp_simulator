import socket
import threading
import json
import datetime
import time
import uuid
from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout

HOST = '127.0.0.1'
PORT = 12345
INTERVALO_FETCH = 2  # segundos entre fetches automáticos

# Dicionário para armazenar mensagens enviadas com seus status
msg_enviadas = {}

# Evento para sinalizar parada de threads
parar_evento = threading.Event()

def listen_server(sock):
    """Escuta mensagens do servidor e atualiza o status interno das mensagens enviadas"""
    while not parar_evento.is_set():
        try:
            data = sock.recv(1024)
            if not data:
                print("Desconectado do servidor.")
                break
            for line in data.decode().splitlines():
                try:
                    msg = json.loads(line)
                except Exception:
                    continue

                if msg['tipo'] == 'status':
                    msg_id = msg.get('id')
                    if msg_id and msg_id in msg_enviadas:
                        # Atualiza o status da mensagem enviada
                        msg_enviadas[msg_id]['status'] = msg.get('status')
                        print(f"Atualização de status da mensagem {msg_id}: {msg.get('status')}")
                    else:
                        print(f"Status recebido para mensagem desconhecida: {msg.get('status')}")
                elif msg['tipo'] == 'mensagem':
                    print(f"\n{msg['from'].capitalize()}: {msg['conteudo']} - {msg['timestamp']}")
        except OSError as e:
            if parar_evento.is_set():
                break
            print("Erro ao receber dados:", e)
            break
        except Exception as e:
            print("Erro na thread de escuta:", e)
            break

def auto_fetch(sock):
    """Envia automaticamente solicitações de busca ao servidor no intervalo estabelecido"""
    time.sleep(INTERVALO_FETCH)
    while True:
        try:
            fetch_msg = {"tipo": "fetch"}
            sock.sendall((json.dumps(fetch_msg) + "\n").encode())
        except Exception as e:
            print("Erro na busca automática:", e)
            break

def processar_comandos(sock, username, session):
    """Processa comandos digitado pelo usuário."""
    while True:
            try:
                comando = session.prompt("\n(send/quit): ").strip()
            except KeyboardInterrupt:
                continue
            except EOFError:
                break

            if comando == "quit":
                logout = {"tipo": "logout", "username": username}
                sock.sendall((json.dumps(logout) + "\n").encode())
                parar_evento.set()  # Sinaliza para as threads pararem
                time.sleep(1)       # Aguarda threads terminarem
                sock.shutdown(socket.SHUT_RDWR)
                break
            elif comando.startswith("send"):
                partes = comando.split(" ", 2)
                if len(partes) < 3:
                    print("Uso: send <destinatário> <mensagem>")
                    continue
                destinatario = partes[1]
                conteudo = partes[2]
                timestamp = datetime.datetime.now().strftime("%H:%M")
                # Gera um ID único para a mensagem
                msg_id = str(uuid.uuid4())
                mensagem = {"tipo": "send", "id": msg_id, "from": username, "to": destinatario, "conteudo": conteudo, 'timestamp': timestamp}
                try:
                    sock.sendall((json.dumps(mensagem) + "\n").encode())
                    # Armazena a mensagem com status inicial "pendente"
                    msg_enviadas[msg_id] = {
                        "to": destinatario,
                        "conteudo": conteudo,
                        "status": "pendente",
                        "timestamp": time.time()
                    }
                    print(f"⧖")
                except Exception as e:
                    print("Falha ao enviar mensagem:", e)
            else:
                print("Comando desconhecido. Use 'send' ou 'quit'.")

def main():
    session = PromptSession()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((HOST, PORT))
    except Exception as e:
        print("Não foi possível conectar ao servidor:", e)
        return

    # Solicita o nome de usuário
    username = session.prompt("Digite seu nome de usuário: ").strip()
    login = {"tipo": "login", "username": username}
    sock.sendall((json.dumps(login) + "\n").encode())

    # Inicia as threads para escuta e busca automática
    listener = threading.Thread(target=listen_server, args=(sock,), daemon=True)
    listener.start()
    fetcher = threading.Thread(target=auto_fetch, args=(sock,), daemon=True)
    fetcher.start()

    # Loop principal: comandos do usuário (enviar ou sair)
    with patch_stdout():
        processar_comandos(sock, username, session)
    sock.close()

if __name__ == '__main__':
    main()
