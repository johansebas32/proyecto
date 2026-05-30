import asyncio
import json
import random
import math

import websockets
from sqlalchemy.orm import Session

from database import SessionLocal
from models import RutaDB

# ==================================================
# CONFIGURACIÓN
# ==================================================

TOTAL_BUSES = 200

WS_URL = "ws://127.0.0.1:8000/ws/telemetria_ingesta"

# ==================================================
# CARGAR RUTAS
# ==================================================

db: Session = SessionLocal()

rutas = db.query(RutaDB).all()

if not rutas:
    raise Exception(
        "No existen rutas. Ejecuta seed.py primero."
    )

# ==================================================
# UTILIDADES MATEMÁTICAS
# ==================================================

def distancia(p1, p2):

    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]

    return math.sqrt(dx * dx + dy * dy)


def interpolar(p1, p2, t):

    lon = p1[0] + (p2[0] - p1[0]) * t
    lat = p1[1] + (p2[1] - p1[1]) * t

    return lat, lon


def velocidad_objetivo():

    r = random.random()

    if r < 0.10:
        return random.uniform(5, 15)

    if r < 0.50:
        return random.uniform(20, 35)

    return random.uniform(35, 60)


# ==================================================
# ESTADO DE FLOTA
# ==================================================

estado_flota = {}

for bus_id in range(1, TOTAL_BUSES + 1):

    ruta = rutas[(bus_id - 1) % len(rutas)]

    path = json.loads(
        ruta.geometria_ruta
    )

    estado_flota[bus_id] = {

        "ruta_id": ruta.id,

        "path": path,

        "segmento": 0,

        "progreso": random.random(),

        "velocidad":

            random.uniform(
                20,
                45
            ),

        "energia":

            random.uniform(
                60,
                100
            ),

        "pasajeros":

            random.randint(
                5,
                60
            )
    }

print(
    f"🚌 Simulador iniciado con {TOTAL_BUSES} buses"
)

# ==================================================
# ESTADO SALUD
# ==================================================

def calcular_estado_salud(
    velocidad,
    energia
):

    if energia < 15:
        return "ROJO"

    if velocidad < 5:
        return "AMARILLO"

    return "VERDE"


# ==================================================
# MOVIMIENTO
# ==================================================

def avanzar_bus(bus):

    path = bus["path"]

    seg = bus["segmento"]

    prog = bus["progreso"]

    velocidad = bus["velocidad"]

    objetivo = velocidad_objetivo()

    velocidad += (
        objetivo - velocidad
    ) * 0.10

    bus["velocidad"] = velocidad

    avance = velocidad / 4000

    prog += avance

    while prog >= 1.0:

        prog -= 1.0

        seg += 1

        if seg >= len(path) - 1:
            seg = 0

    bus["segmento"] = seg
    bus["progreso"] = prog

    p1 = path[seg]
    p2 = path[seg + 1]

    lat, lon = interpolar(
        p1,
        p2,
        prog
    )

    return (
        lat,
        lon,
        velocidad
    )


# ==================================================
# LOOP PRINCIPAL
# ==================================================

async def ejecutar():

    while True:

        try:

            async with websockets.connect(
                WS_URL
            ) as websocket:

                print(
                    "✅ Conectado a FastAPI"
                )

                while True:

                    for bus_id, bus in estado_flota.items():

                        lat, lon, velocidad = avanzar_bus(
                            bus
                        )

                        energia = bus["energia"]

                        consumo = (
                            velocidad / 1000
                        )

                        energia -= consumo

                        if energia <= 5:

                            energia = 100

                        bus["energia"] = energia

                        pasajeros = bus["pasajeros"]

                        if random.random() < 0.05:

                            pasajeros += random.randint(
                                -4,
                                6
                            )

                            pasajeros = max(
                                0,
                                min(
                                    80,
                                    pasajeros
                                )
                            )

                        bus["pasajeros"] = pasajeros

                        salud = calcular_estado_salud(
                            velocidad,
                            energia
                        )

                        payload = {

                            "vehiculo_id":
                                bus_id,

                            "latitud":
                                round(
                                    lat,
                                    6
                                ),

                            "longitud":
                                round(
                                    lon,
                                    6
                                ),

                            "velocidad_kmh":
                                round(
                                    velocidad,
                                    2
                                ),

                            "nivel_energia":
                                round(
                                    energia,
                                    2
                                ),

                            "pasajeros_a_bordo":
                                pasajeros
                        }

                        await websocket.send(
                            json.dumps(payload)
                        )

                        await asyncio.sleep(
                            0.003
                        )

                    print(
                        "📡 Telemetría enviada"
                    )

                    await asyncio.sleep(
                        1
                    )

        except Exception as e:

            print(
                f"⚠️ Error WS: {e}"
            )

            await asyncio.sleep(
                3
            )


# ==================================================
# START
# ==================================================

if __name__ == "__main__":

    asyncio.run(
        ejecutar()
    )