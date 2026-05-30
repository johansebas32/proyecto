import asyncio
import json
import random
import math

import websockets
from sqlalchemy.orm import Session

from database import SessionLocal
from models import RutaDB

# ==========================================
# CONFIGURACIÓN
# ==========================================

TOTAL_BUSES = 200
WS_URL = "ws://127.0.0.1:8000/ws/telemetria_ingesta"

# ==========================================
# CARGAR RUTAS
# ==========================================

db: Session = SessionLocal()

rutas = db.query(RutaDB).all()

if not rutas:
    raise Exception(
        "No existen rutas. Ejecuta seed.py primero."
    )

# ==========================================
# FUNCIONES MATEMÁTICAS
# ==========================================

def distancia(p1, p2):
    """
    Distancia euclidiana
    """

    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]

    return math.sqrt(dx * dx + dy * dy)


def interpolar_vectorial(p1, p2, t):
    """
    Álgebra lineal:
    P(t)=P1+t(P2-P1)
    """

    lon = p1[0] + t * (p2[0] - p1[0])
    lat = p1[1] + t * (p2[1] - p1[1])

    return lat, lon


def calcular_velocidad_realista(hora):

    if 6 <= hora <= 8:
        return random.uniform(8, 25)

    if 17 <= hora <= 19:
        return random.uniform(5, 22)

    return random.uniform(25, 65)


def calcular_salud(velocidad, energia):

    if energia < 15:
        return "ROJO"

    if velocidad < 10:
        return "AMARILLO"

    return "VERDE"


# ==========================================
# CREAR FLOTA
# ==========================================

estado_flota = {}

for bus_id in range(1, TOTAL_BUSES + 1):

    ruta = rutas[(bus_id - 1) % len(rutas)]

    path = json.loads(
        ruta.geometria_ruta
    )

    estado_flota[bus_id] = {
        "ruta_id": ruta.id,
        "ruta_nombre": ruta.nombre,
        "path": path,
        "segmento": 0,
        "progreso": random.random(),
        "energia": random.uniform(60, 100),
        "pasajeros": random.randint(10, 60)
    }

print(
    f"🚌 {TOTAL_BUSES} buses inicializados"
)

# ==========================================
# MOVIMIENTO VECTORIAL
# ==========================================

def avanzar_bus(bus):

    path = bus["path"]

    seg = bus["segmento"]
    prog = bus["progreso"]

    prog += random.uniform(
        0.01,
        0.05
    )

    if prog >= 1.0:

        prog = 0.0
        seg += 1

        if seg >= len(path) - 1:
            seg = 0

    bus["segmento"] = seg
    bus["progreso"] = prog

    p1 = path[seg]
    p2 = path[seg + 1]

    lat, lon = interpolar_vectorial(
        p1,
        p2,
        prog
    )

    return lat, lon

# ==========================================
# LOOP PRINCIPAL
# ==========================================

async def ejecutar():

    while True:

        try:

            async with websockets.connect(
                WS_URL
            ) as websocket:

                print(
                    "✅ Conectado al servidor"
                )

                while True:

                    hora_actual = (
                        asyncio.get_event_loop()
                        .time()
                    )

                    for bus_id, bus in estado_flota.items():

                        lat, lon = avanzar_bus(bus)

                        velocidad = (
                            calcular_velocidad_realista(
                                random.randint(0, 23)
                            )
                        )

                        energia = bus["energia"]

                        energia -= random.uniform(
                            0.02,
                            0.12
                        )

                        if energia <= 5:

                            energia = random.uniform(
                                85,
                                100
                            )

                        bus["energia"] = energia

                        pasajeros = bus["pasajeros"]

                        pasajeros += random.randint(
                            -3,
                            3
                        )

                        pasajeros = max(
                            0,
                            min(
                                pasajeros,
                                80
                            )
                        )

                        bus["pasajeros"] = pasajeros

                        salud = calcular_salud(
                            velocidad,
                            energia
                        )

                        payload = {

                            "vehiculo_id": bus_id,

                            "latitud": lat,
                            "longitud": lon,

                            "velocidad_kmh": velocidad,

                            "nivel_energia": energia,

                            "pasajeros_a_bordo": pasajeros,

                            "estado_salud": salud
                        }

                        await websocket.send(
                            json.dumps(payload)
                        )

                        await asyncio.sleep(
                            0.002
                        )

                    print(
                        "📡 Telemetría enviada"
                    )

                    await asyncio.sleep(
                        1
                    )

        except Exception as e:

            print(
                f"⚠️ Error: {e}"
            )

            await asyncio.sleep(
                3
            )

# ==========================================
# START
# ==========================================

if __name__ == "__main__":

    asyncio.run(
        ejecutar()
    )