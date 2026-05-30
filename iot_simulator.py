import time
import requests
import random
import asyncio
import websockets
import json

# Coordenadas de los paraderos clave en Risaralda
PARADEROS = [
    (4.7915, -75.7310), # Cuba
    (4.8135, -75.6942), # Centro
    (4.7945, -75.6885), # UTP
    (4.8174, -75.6898), # Dosquebradas
    (4.8707, -75.6231)  # Santa Rosa
]

estado_flota = {}
for i in range(1, 151):
    estado_flota[i] = {
        "bateria_gasolina": random.uniform(20.0, 100.0), 
        "lat": random.uniform(4.75, 4.90), 
        "lon": random.uniform(-75.80, -75.60),
        "target": random.choice(PARADEROS) # NUEVO: Objetivo asignado en lugar de azar
    }

print("📡 Satélite de Telemetría Direccional (150 Buses) Activado...")

async def enviar_telemetria_ws():
    uri = "ws://127.0.0.1:8000/ws/telemetria_ingesta"
    
    while True:
        try:
            async with websockets.connect(uri) as websocket:
                print("✅ Conectado al Gestor WebSocket del Servidor Central")
                while True:
                    for v in range(1, 151):
                        # NUEVO: Lógica matemática para rastreo fluido hacia el objetivo
                        t_lat, t_lon = estado_flota[v]["target"]
                        c_lat = estado_flota[v]["lat"]
                        c_lon = estado_flota[v]["lon"]
                        
                        step = 0.0003 # Velocidad de avance vectorial
                        dir_lat = t_lat - c_lat
                        dir_lon = t_lon - c_lon
                        dist = (dir_lat**2 + dir_lon**2)**0.5
                        
                        if dist < step:
                            # Al llegar a la parada, buscar un nuevo destino
                            estado_flota[v]["target"] = random.choice(PARADEROS)
                        else:
                            # Moverse directamente hacia la parada
                            estado_flota[v]["lat"] += (dir_lat / dist) * step
                            estado_flota[v]["lon"] += (dir_lon / dist) * step
                        
                        estado_flota[v]["bateria_gasolina"] -= random.uniform(0.1, 0.5)
                        if estado_flota[v]["bateria_gasolina"] < 5.0: 
                            estado_flota[v]["bateria_gasolina"] = 100.0 
                            
                        datos = {
                            "vehiculo_id": v,
                            "latitud": estado_flota[v]["lat"], 
                            "longitud": estado_flota[v]["lon"],
                            "velocidad_kmh": random.uniform(30, 60),
                            "nivel_energia": estado_flota[v]["bateria_gasolina"],
                            "pasajeros_a_bordo": random.randint(10, 80)
                        }
                        
                        await websocket.send(json.dumps(datos))
                        await asyncio.sleep(0.01) 
                        
                    print(f"🔄 Enjambre sincronizado direccionalmente via WS.")
                    await asyncio.sleep(2)
        except Exception as e:
            print(f"⚠️ Conexión WebSocket perdida. Reintentando en 3s... Error: {e}")
            await asyncio.sleep(3)

if __name__ == "__main__":
    asyncio.run(enviar_telemetria_ws())