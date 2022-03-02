import socket
import threading
import time
import math
import common
import ipaddress

jugadores_lock = common.RWLock()
actualizar_cond = threading.Condition()
jugadores = {}

v = 1
dt_sim = 0.01
dt_send = 0.1
start_time = time.time()
radio = None

PORT = 2021

def handle_msg(ctx, msg, conn, addr):
    msg = msg[:-1].decode('utf-8')
    if msg.startswith('PLAYER '):
        username = msg[len('PLAYER '):]
        if len(username) == 0:
            conn.send('FAIL username vacio\n'.encode('utf-8'))
            return False
        jugadores_lock.acquire_read()
        if username in jugadores:
            conn.send('FAIL username repetido\n'.encode('utf-8'))
            jugadores_lock.release_read()
            return False
        jugadores_lock.release_read()
        ctx['username'] = username
        conn.send('OK\n'.encode('utf-8'))
        return True
    elif msg.startswith('LISTEN '):
        portnumber_str = msg[len('LISTEN '):]
        if len(portnumber_str) == 0:
            conn.send('FAIL portnumber vacio\n'.encode('utf-8'))
            return False
        portnumber = None
        try:
            portnumber = int(portnumber_str)
        except ValueError:
            conn.send('FAIL puerto no es un numero\n'.encode('utf-8'))
            return False
        if portnumber < 1 or portnumber > 65535:
            conn.send('FAIL portnumber no valido\n'.encode('utf-8'))
            return False
        jugadores_lock.acquire_write()
        username = ctx['username']
        jugadores[username] = common.Jugador(ctx['username'])
        jugadores[username].portnumber = portnumber
        jugadores[username].addr = addr
        jugadores_lock.release_write()
        conn.send('OK\n'.encode('utf-8'))
        return True
    elif msg.startswith('GO'):
        dir = msg[len('GO '):]
        if len(dir) != 1:
            conn.send('FAIL direccion tamaño invalido\n'.encode('utf-8'))
            return False
        if ctx['username'] == None:
            conn.send('FAIL usuario no logeado\n'.encode('utf-8'))
            return False
        if not (dir == 'N' or dir == 'S' or dir == 'W' or dir == 'E'):
            conn.send('FAIL direccion invalida\n'.encode('utf-8'))
            return False
        jugadores_lock.acquire_write()
        jugadores[ctx['username']].estado = dir
        jugadores_lock.release_write()
        return True
    else:
        conn.send('FAIL mensaje no reconocido\n'.encode('utf-8'))
        return False

def handle_conn(conn, addr):
    ctx = {}
    msg = b''
    while True:
        data = conn.recv(1024) #obtener largo de data recibido 
        if not data:
            if 'username' in ctx:
                jugadores_lock.acquire_write()
                del jugadores[ctx['username']]
                jugadores_lock.release_write()
                with actualizar_cond:
                    actualizar_cond.notify()
            break
        msg += data
        index = data.find('\n'.encode('utf-8'))
        if index != -1:
            recv = msg[:index + 1]
            print(recv)
            msg = msg[index + 1:]
            if not handle_msg(ctx, recv, conn, addr):
                conn.close()
                break
            msg = b''

def movimiento():
    while True:
        jugadores_lock.acquire_write()
        actualizar = False
        for p in jugadores.values():
            if p.estado == 'N':
                if p.y < 50:
                    p.y += v*dt_sim
                    actualizar = True
            elif p.estado == 'S':
                if p.y > -50:
                    p.y -= v*dt_sim
                    actualizar = True
            elif p.estado == 'E':
                if p.x < 50:
                    p.x += v*dt_sim
                    actualizar = True
            elif p.estado == 'W':
                if p.x > -50:
                    p.x -= v*dt_sim
                    actualizar = True
        jugadores_lock.release_write()
        if actualizar:
            with actualizar_cond:
                actualizar_cond.notify()
        time.sleep(dt_sim)

def FindCloserThan(p, players, distancia):
    res = []
    nick = p.nickname
    x = p.x
    y = p.y
    for jugador in players.values():
        if math.sqrt((jugador.x-x)**2 + (jugador.y-y)**2) <= distancia and jugador.nickname != nick:
            res.append(jugador)
    return res

def BuildMessage(p, time, vecinos):
    res = "WORLD " + str(time) + "\n" + "PLAYER " + str(p.x) + " " + str(p.y) + " " + str(p.estado) + "\n"
    for jugador in vecinos:
        res+= jugador.nickname + " " + str(jugador.x) + " " + str(jugador.y) + " " + str(jugador.estado) + "\n"
    return res

def funcionVecinos():
    skt = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    while True:
        with actualizar_cond:
            actualizar_cond.wait()
        jugadores_lock.acquire_read()
        for p in jugadores.values():
            if not hasattr(p, 'addr'):
                continue
            listaVecinos = FindCloserThan(p, jugadores, radio)
            mensaje = BuildMessage(p, (time.time() - start_time), listaVecinos)
            skt.sendto(mensaje.encode('utf-8'), (p.addr[0], p.portnumber))
        jugadores_lock.release_read()
        time.sleep(dt_send)

def main():
    global host
    global radio

    while True:
        try:
            host = input('Ingrese la IP del servidor (127.0.0.1 por defecto): ')
            if host == '':
                host = '127.0.0.1'
                break
            ipaddress.ip_address(host)
            break
        except ValueError:
            print('Por favor ingrese una direccion IP valida. ')
    
    while True:
        try:
            radio = input('Ingrese el radio de vision de los jugadores (15 por defecto): ')
            if radio == '':
                radio = 15
                break
            radio = float(radio)
            break
        except ValueError:
            print("Por favor ingrese un radio valido. ")     

    threading.Thread(target=movimiento).start()
    threading.Thread(target=funcionVecinos).start()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, PORT))
        s.listen()
        while True:
            conn, addr = s.accept()
            threading.Thread(target=handle_conn, args=(conn, addr)).start()

if __name__ == '__main__':
    main()
