import common
import threading
import socket
import turtle
import pynput
from pynput import keyboard
import ipaddress


def removeprefix(str, prefix):
    i = str.find(prefix)
    if i != 0:
        return str
    return str[len(prefix):]

def crear_tortuga():
    t = turtle.Turtle(visible=False)
    t.shape("turtle")
    t.penup()
    return t

dir_to_angle = {'N': 90, 'E': 0, 'S': 270, 'W': 180}
colors = ['red', 'blue', 'yellow', 'green', 'orange', 'black']

port_udp = None
last_timestamp = None
servidor_skt = None

world_cond = threading.Condition()
control_cond = threading.Condition()
dibujar_cond = threading.Condition()

datos_lock = common.RWLock()
x = 0
y = 0
estado = 'IDLE'
vecinos = []

dir = None
dir_lock = common.RWLock()
dir_cond = threading.Condition()

def control():
    with control_cond:
        control_cond.wait()
    while True:
        if salir:
            break
        with dir_cond:
            dir_cond.wait()
        dir_lock.acquire_read()
        if dir == 'up':
            servidor_skt.send('GO N\n'.encode('utf-8'))
        elif dir == 'down':
            servidor_skt.send('GO S\n'.encode('utf-8'))
        elif dir == 'right':
            servidor_skt.send('GO E\n'.encode('utf-8'))
        else:
            servidor_skt.send('GO W\n'.encode('utf-8'))
        dir_lock.release_read()

def world():
    with world_cond:
        world_cond.wait()
    skt = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    skt.bind((host, int(port_udp)))
    while True:
        if salir:
            break
        msg, _ = skt.recvfrom(1024) #y si hay fragmentacion del payload de udp (!?)
        msg = msg.decode('utf-8')
        guardar_datos(msg)

def guardar_datos(msg):
    global last_timestamp
    global x
    global y
    global estado
    global vecinos

    lineas = msg.split('\n')[:-1]
    curr_timestamp = float(removeprefix(lineas[0], 'WORLD '))

    if last_timestamp != None and curr_timestamp <= last_timestamp:
        return

    last_timestamp = curr_timestamp

    datos_lock.acquire_write()

    datos_player = removeprefix(lineas[1], 'PLAYER ').split(' ')
    x = float(datos_player[0])
    y = float(datos_player[1])
    estado = datos_player[2]

    vecinos = []
    for linea in lineas[2:]:
        tmp = linea.split(' ')
        datos_vecino = []

        nickname = ' '.join(tmp[:-3])

        datos_vecino.append(nickname)
        datos_vecino.append(float(tmp[-3]))
        datos_vecino.append(float(tmp[-2]))
        datos_vecino.append(tmp[-1])

        print(datos_vecino)

        vecinos.append(datos_vecino)

    datos_lock.release_write()

    with dibujar_cond:
        dibujar_cond.notify()

def esperar_ok(skt):
    expected = 'OK\n'.encode('utf-8')
    data = skt.recv(len(expected),socket.MSG_PEEK)
    if expected == data:
        skt.recv(len(expected))
        return True
    else:
        return False

def on_press_helper(str):
    global dir
    dir_lock.acquire_read()
    if dir == str:
        dir_lock.release_read()
        return
    else:
        dir_lock.release_read()
    dir_lock.acquire_write()
    dir = str
    dir_lock.release_write()
    with dir_cond:
        dir_cond.notify()

def on_press(key):
    if key == keyboard.Key.up:
        on_press_helper('up')
    elif key == keyboard.Key.down:
        on_press_helper('down')
    elif key == keyboard.Key.left:
        on_press_helper('left')
    elif key == keyboard.Key.right:
        on_press_helper('right')

def on_release(key):
    global salir
    if key == keyboard.Key.esc:
        salir = True
        with world_cond:
            world_cond.notifyAll()
        with control_cond:
            control_cond.notifyAll()
        with dibujar_cond:
            dibujar_cond.notifyAll()
        with dir_cond:
            dir_cond.notifyAll()





def main():
    global host
    global port_udp
    global servidor_skt
    global salir
    
    
    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    worldThread = threading.Thread(target=world)
    controlThread = threading.Thread(target=control)
    salir = False
    print("Bienvenido a Tortugas Pescadoras v1.7.2, para comenzar a jugar siga los pasos detallados a continuación: ")


    error = True
    while error:
        error = False
        servidor_skt = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        while True: 
            try:
                ip = input('Indique direccion IP del servidor: ')
                ipaddress.ip_address(ip)
            except ValueError:
                print('Por favor ingrese una dirección IP válida. ')
                continue
            try: 
                servidor_skt.connect((ip, 2021))
                break
            except ConnectionRefusedError:
                print('No hay un servidor en esa dirección IP. ')
        
        nickname = input('Nickname de su tortuga: ')
        servidor_skt.send(('PLAYER ' + nickname + '\n').encode('utf-8'))

        if not esperar_ok(servidor_skt):
            error = True
            username_vacio = 'FAIL username vacio\n'.encode('utf-8')
            username_repetido = 'FAIL username repetido\n'.encode('utf-8')
            if servidor_skt.recv(len(username_vacio),socket.MSG_PEEK) == username_vacio:
                print('El username no puede ser vacio\n')
                servidor_skt.recv(len(username_vacio))
            elif servidor_skt.recv(len(username_repetido),socket.MSG_PEEK) == username_repetido:
                print('El username ingresado no esta disponible\n')
                servidor_skt.recv(len(username_repetido))
            servidor_skt.close()
        
        if not error:
            while True:
                try:
                    host = input('Indique su direccion IP: ')
                    ipaddress.ip_address(host)
                    break
                except ValueError:
                    print('Por favor ingrese una dirección IP válida. ')
            port_udp = input('Puerto udp: ')
            servidor_skt.send(('LISTEN ' + port_udp + '\n').encode('utf-8'))
            if not esperar_ok(servidor_skt):
                error = True
                puerto_vacio = 'FAIL portnumber vacio\n'.encode('utf-8')
                puerto_noes_numero = 'FAIL puerto no es un numero\n'.encode('utf-8')
                puerto_invalido = 'FAIL portnumber no valido\n'.encode('utf-8')
                if servidor_skt.recv(len(puerto_vacio),socket.MSG_PEEK) == puerto_vacio:
                    print('El puerto no puede ser vacio\n')
                    servidor_skt.recv(len(puerto_vacio))
                elif servidor_skt.recv(len(puerto_noes_numero),socket.MSG_PEEK) == puerto_noes_numero:
                    print('El puerto debe ser un numero\n')
                    servidor_skt.recv(len(puerto_noes_numero))
                elif servidor_skt.recv(len(puerto_invalido),socket.MSG_PEEK) == puerto_invalido:
                    print('El puerto ingresado no es valido\n')
                    servidor_skt.recv(len(puerto_invalido))
                servidor_skt.close()

        if error:
            respuesta = input('¿Desea intentarlo de nuevo? [y/n] ')
            while respuesta != 'y' and respuesta != 'n':
                respuesta = input('Por favor ingrese una de las dos opciones ("y" o "n") ')
            if respuesta == 'n':
                return

    listener.start()
    worldThread.start() 
    controlThread.start()

    with world_cond:
        world_cond.notify()

    with control_cond:
        control_cond.notify()

    screen = turtle.Screen()
    screen.setup(width=1000, height=1000)
    screen.setworldcoordinates(-50, -50, 50, 50)

    jugador_turtle = crear_tortuga()
    jugador_turtle.color('green')
    jugador_turtle.showturtle()

    vecinos_viejos = {}
    vecinos_nuevos = {}

    print("Para salir del juego presione Escape.")

    while True:
        if salir:
            worldThread.join()
            controlThread.join()
            servidor_skt.close()
            return
            
        with dibujar_cond:
            dibujar_cond.wait()

        datos_lock.acquire_read()

        jugador_turtle.goto(x, y)
        if estado != 'IDLE':
            jugador_turtle.tiltangle(dir_to_angle[estado])

        vecinos_nuevos = {}

        for i in range(len(vecinos)):
            vecino = vecinos[i]
            nickname = vecino[0]
            vecino_x = vecino[1]
            vecino_y = vecino[2]
            est = vecino[3]

            if not nickname in vecinos_viejos:
                vecino_turtle = crear_tortuga()
                vecino_turtle.goto(vecino_x, vecino_y)
                if est != 'IDLE':
                    vecino_turtle.tiltangle(dir_to_angle[est])
                vecino_turtle.color(colors[i % len(colors)])
                vecino_turtle.showturtle()
                vecinos_nuevos[nickname] = vecino_turtle
            else:
                vecino_turtle = vecinos_viejos[nickname]
                vecino_turtle.goto(vecino_x, vecino_y)
                if est != 'IDLE':
                    vecino_turtle.tiltangle(dir_to_angle[est])
                vecinos_nuevos[nickname] = vecino_turtle

        to_remove = []

        for nickname in vecinos_viejos:
            if not nickname in vecinos_nuevos:
                vecinos_viejos[nickname].clear()
                vecinos_viejos[nickname].hideturtle()
                to_remove.append(nickname)

        for nickname in to_remove:
            del vecinos_viejos[nickname]

        vecinos_viejos = vecinos_nuevos

        datos_lock.release_read()
        


if __name__ == '__main__':
    main()
