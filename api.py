import logging
import json
import numpy as np
from datetime import datetime
from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sklearn.tree import DecisionTreeRegressor
from starlette.concurrency import run_in_threadpool

from database import engine, Base, get_db, SessionLocal
from models import VehiculoDB, HistorialViajesDB, TelemetriaBusDB, AlertaDB, UsuarioDB, RutaDB
import schemas

logging.basicConfig(level=logging.INFO)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Transporte OS Risaralda Pro", version="7.0")

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

ws_manager = ConnectionManager()

@app.websocket("/ws/telemetria_ingesta")
async def websocket_telemetria(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            
            def sync_db_ops():
                db = SessionLocal() 
                try:
                    vehiculo_id = payload.get("vehiculo_id")
                    if not vehiculo_id: return None

                    vehiculo = db.query(VehiculoDB).filter(VehiculoDB.id == vehiculo_id).first()
                    if not vehiculo: return None

                    registro = db.query(TelemetriaBusDB).filter(TelemetriaBusDB.vehiculo_id == vehiculo_id).first()
                    if not registro:
                        registro = TelemetriaBusDB(
                            vehiculo_id=vehiculo_id,
                            latitud=payload.get("latitud"),
                            longitud=payload.get("longitud"),
                            velocidad_kmh=payload.get("velocidad_kmh"),
                            nivel_energia=payload.get("nivel_energia"),
                            pasajeros_a_bordo=payload.get("pasajeros_a_bordo")
                        )
                        db.add(registro)
                    else:
                        registro.latitud = payload.get("latitud")
                        registro.longitud = payload.get("longitud")
                        registro.velocidad_kmh = payload.get("velocidad_kmh")
                        registro.nivel_energia = payload.get("nivel_energia")
                        registro.pasajeros_a_bordo = payload.get("pasajeros_a_bordo")

                    if registro.velocidad_kmh > 80.0:
                        db.add(AlertaDB(vehiculo_id=vehiculo_id, tipo_alerta="EXCESO_VELOCIDAD", descripcion=f"Velocidad: {registro.velocidad_kmh:.1f} km/h"))
                    if registro.nivel_energia < 15.0:
                        tipo = "BATERIA_BAJA" if vehiculo.tipo_motor == "Electrico" else "COMBUSTIBLE_BAJO"
                        db.add(AlertaDB(vehiculo_id=vehiculo_id, tipo_alerta=tipo, descripcion=f"Nivel crítico: {registro.nivel_energia:.1f}%"))

                    db.commit()
                    return vehiculo_id
                except Exception as e:
                    db.rollback()
                    return None
                finally:
                    db.close() 

            v_id = await run_in_threadpool(sync_db_ops)
            
            if v_id:
                await ws_manager.broadcast(json.dumps({"status": "updated", "vehiculo_id": v_id}))
            
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)

@app.post("/incidentes")
def crear_incidente(vehiculo_id: int, descripcion: str, db: Session = Depends(get_db)):
    vehiculo = db.query(VehiculoDB).filter(VehiculoDB.id == vehiculo_id).first()
    if not vehiculo:
        raise HTTPException(status_code=404, detail="Vehículo no encontrado")
    
    incidente = AlertaDB(vehiculo_id=vehiculo_id, tipo_alerta="INCIDENTE_VIAL", descripcion=descripcion)
    db.add(incidente)
    db.commit()
    return {"status": "Incidente reportado exitosamente"}

@app.get("/incidentes/activos")
def obtener_incidentes_activos(db: Session = Depends(get_db)):
    alertas = db.query(AlertaDB).filter(AlertaDB.tipo_alerta == "INCIDENTE_VIAL").order_by(AlertaDB.fecha.desc()).limit(3).all()
    return [{"id": a.id, "vehiculo_id": a.vehiculo_id, "descripcion": a.descripcion, "hora": a.fecha.strftime("%H:%M:%S")} for a in alertas]

@app.get("/pasajeros/bloqueados")
def obtener_pasajeros_bloqueados(db: Session = Depends(get_db)):
    usuarios_morosos = db.query(UsuarioDB).filter(UsuarioDB.deuda >= 90000).order_by(UsuarioDB.deuda.desc()).limit(6).all()
    resultado = []
    for u in usuarios_morosos:
        resultado.append({
            "Pasajero": u.nombre,
            "Deuda Actual": f"${u.deuda:,.0f} COP",
            "Estado": "🚫 RECHAZADO",
            "Acción": "Tarjeta NFC Suspendida temporalmente"
        })
    return resultado

@app.get("/pasajeros/activos")
def obtener_pasajeros_activos(db: Session = Depends(get_db)):
    viajes = db.query(HistorialViajesDB).order_by(HistorialViajesDB.fecha.desc()).limit(50).all()
    resultado = []
    for v in viajes:
        u = db.query(UsuarioDB).filter(UsuarioDB.id == v.usuario_id).first()
        r = db.query(RutaDB).filter(RutaDB.id == v.ruta_id).first()
        resultado.append({
            "Pasajero": u.nombre if u else "Anónimo",
            "Ruta": r.nombre if r else "Desconocida",
            "Bus_ID": v.vehiculo_id,
            "Hora_Abordaje": v.fecha.strftime("%H:%M:%S")
        })
    return resultado

@app.get("/usuarios/deudas")
def obtener_deudas(db: Session = Depends(get_db)):
    usuarios = db.query(UsuarioDB).filter(UsuarioDB.deuda > 0).order_by(UsuarioDB.deuda.desc()).all()
    return [{"Usuario": u.nombre, "Deuda_Pendiente": f"${u.deuda:,.0f}"} for u in usuarios]

@app.post("/telemetria/{vehiculo_id}")
async def actualizar_gps(vehiculo_id: int, gps: schemas.TelemetriaIn, db: Session = Depends(get_db)):
    vehiculo = db.query(VehiculoDB).filter(VehiculoDB.id == vehiculo_id).first()
    if not vehiculo:
        raise HTTPException(status_code=404, detail="Vehículo no registrado")
        
    registro = db.query(TelemetriaBusDB).filter(TelemetriaBusDB.vehiculo_id == vehiculo_id).first()
    if not registro:
        registro = TelemetriaBusDB(vehiculo_id=vehiculo_id, **gps.dict())
        db.add(registro)
    else:
        for key, value in gps.dict().items():
            setattr(registro, key, value)
    
    if gps.velocidad_kmh > 80.0:
        alerta = AlertaDB(vehiculo_id=vehiculo_id, tipo_alerta="EXCESO_VELOCIDAD", descripcion=f"Velocidad: {gps.velocidad_kmh:.1f} km/h")
        db.add(alerta)
        
    if gps.nivel_energia < 15.0:
        tipo = "BATERIA_BAJA" if vehiculo.tipo_motor == "Electrico" else "COMBUSTIBLE_BAJO"
        alerta = AlertaDB(vehiculo_id=vehiculo_id, tipo_alerta=tipo, descripcion=f"Nivel crítico: {gps.nivel_energia:.1f}%")
        db.add(alerta)

    db.commit()
    return {"status": "Procesado"}

@app.get("/telemetria")
def obtener_flota_gps(db: Session = Depends(get_db)):
    registros = db.query(TelemetriaBusDB).all()
    resultado = []
    for r in registros:
        v = db.query(VehiculoDB).filter(VehiculoDB.id == r.vehiculo_id).first()
        resultado.append({
            "vehiculo_id": r.vehiculo_id, "placa": v.placa if v else "S/P",
            "tipo_motor": v.tipo_motor if v else "Desconocido", "lat": r.latitud, "lon": r.longitud, 
            "vel": r.velocidad_kmh, "bateria_gasolina": r.nivel_energia, "pasajeros": r.pasajeros_a_bordo
        })
    return resultado

@app.get("/ia/prediccion/{ruta_id}")
def predecir_demanda(ruta_id: int, hora_inicio: int = 0, hora_fin: int = 23, db: Session = Depends(get_db)):
    viajes = db.query(HistorialViajesDB).filter(HistorialViajesDB.ruta_id == ruta_id).all()
    if len(viajes) < 5:
        raise HTTPException(status_code=400, detail="Faltan datos históricos para la IA.")
    
    conteo_por_hora = {}
    for v in viajes:
        hora = v.fecha.hour
        conteo_por_hora[hora] = conteo_por_hora.get(hora, 0) + 1
        
    X = np.array(list(conteo_por_hora.keys())).reshape(-1, 1)
    y = np.array(list(conteo_por_hora.values()))
    
    modelo = DecisionTreeRegressor(max_depth=4)
    modelo.fit(X, y)
    
    horas_a_evaluar = list(range(hora_inicio, hora_fin + 1)) if hora_inicio <= hora_fin else list(range(hora_inicio, 24)) + list(range(0, hora_fin + 1))
    pasajeros_totales = 0
    desglose = {}
    
    for h in horas_a_evaluar:
        pred = int(abs(modelo.predict([[h]])[0]))
        pasajeros_totales += pred
        desglose[f"{h}:00"] = pred
    
    return {"ruta_id": ruta_id, "rango": f"{hora_inicio}:00 a {hora_fin}:00", "pasajeros_esperados": pasajeros_totales, "desglose": desglose}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)