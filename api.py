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
from models import VehiculoDB, HistorialViajesDB, TelemetriaBusDB, AlertaDB, UsuarioDB, RutaDB, ParadaDB, RutaParadaDB
from graph_engine import GrafoMetropolitano
from route_optimizer import AsignadorRutasInteligente
import schemas

logging.basicConfig(level=logging.INFO)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Transporte OS Risaralda Pro", version="7.0")

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

# Instancias globales
grafo = None
asignador = None

def inicializar_sistemas():
    """Inicializa grafo y asignador al startup"""
    global grafo, asignador
    try:
        grafo = GrafoMetropolitano()
        asignador = AsignadorRutasInteligente()
    except Exception as e:
        logging.warning(f"No se pudieron inicializar sistemas de grafo: {e}")

@app.on_event("startup")
def startup_event():
    inicializar_sistemas()

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

# ==========================================
# ENDPOINTS EXISTENTES
# ==========================================

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

# ==========================================
# NUEVOS ENDPOINTS - FASE 2: GRAFO Y DIJKSTRA
# ==========================================

@app.get("/grafo/matriz-adyacencia")
def obtener_matriz_adyacencia():
    """Retorna la matriz de adyacencia del grafo de paradas."""
    if not grafo:
        raise HTTPException(status_code=503, detail="Sistema de grafo no inicializado")
    
    return {
        "matriz": grafo.obtener_matriz_adyacencia(),
        "paradas_total": len(grafo.paradas),
        "descripcion": "Matriz binaria: 1 = hay conexión directa entre paradas"
    }

@app.get("/grafo/matriz-ponderada")
def obtener_matriz_ponderada():
    """Retorna la matriz ponderada con distancias en km."""
    if not grafo:
        raise HTTPException(status_code=503, detail="Sistema de grafo no inicializado")
    
    return {
        "matriz": grafo.obtener_matriz_ponderada(),
        "paradas_total": len(grafo.paradas),
        "unidad": "km",
        "descripcion": "Matriz de distancias: inf = sin conexión directa"
    }

@app.get("/grafo/paradas")
def obtener_paradas(db: Session = Depends(get_db)):
    """Retorna todas las paradas con sus coordenadas."""
    paradas = db.query(ParadaDB).all()
    
    resultado = []
    for p in paradas:
        resultado.append({
            "parada_id": p.id,
            "nombre": p.nombre,
            "latitud": p.latitud,
            "longitud": p.longitud,
            "personas_esperando": p.personas_esperando,
            "demanda_historica": p.demanda_historica
        })
    
    return {"paradas": resultado, "total": len(resultado)}

@app.get("/grafo/centralidad")
def obtener_centralidad():
    """Retorna paradas ordenadas por centralidad (grado - cantidad de conexiones)."""
    if not grafo:
        raise HTTPException(status_code=503, detail="Sistema de grafo no inicializado")
    
    centralidades = grafo.centralidad()
    
    return {
        "paradas_ordenadas": centralidades,
        "interpretacion": "Mayor grado = parada más conectada (hub)"
    }

@app.get("/ruta-optima/{origen_id}/{destino_id}")
def calcular_ruta_optima(origen_id: int, destino_id: int):
    """
    Calcula la ruta más corta entre dos paradas usando Dijkstra.
    
    Args:
        origen_id: ID de parada de origen
        destino_id: ID de parada de destino
    
    Returns:
        distancia_km, lista de paradas, lista de nombres
    """
    if not grafo:
        raise HTTPException(status_code=503, detail="Sistema de grafo no inicializado")
    
    distancia, ids_paradas, nombres_paradas = grafo.dijkstra(origen_id, destino_id)
    
    if distancia == np.inf:
        return {
            "error": "No hay ruta disponible entre estas paradas",
            "origen_id": origen_id,
            "destino_id": destino_id
        }
    
    return {
        "distancia_km": distancia,
        "tiempo_estimado_min": round(distancia / 30 * 60, 1),  # 30 km/h promedio
        "paradas_ids": ids_paradas,
        "paradas_nombres": nombres_paradas,
        "num_paradas": len(nombres_paradas)
    }

@app.get("/rutas/info")
def obtener_info_rutas(db: Session = Depends(get_db)):
    """Retorna información detallada de todas las rutas."""
    rutas = db.query(RutaDB).all()
    
    resultado = []
    for r in rutas:
        resultado.append({
            "ruta_id": r.id,
            "nombre": r.nombre,
            "codigo": r.codigo_ruta,
            "distancia_km": r.distancia_km,
            "tiempo_estimado_min": r.tiempo_estimado_min,
            "demanda_promedio": r.demanda_promedio,
            "tarifa_base": r.tarifa_base
        })
    
    return {"rutas": resultado, "total": len(resultado)}

# ==========================================
# NUEVOS ENDPOINTS - ASIGNACIÓN INTELIGENTE
# ==========================================

@app.get("/asignacion/buses")
def obtener_asignacion_buses():
    """Retorna asignación actual de buses a rutas."""
    if not asignador:
        raise HTTPException(status_code=503, detail="Sistema de asignación no inicializado")
    
    asignaciones = asignador.obtener_asignaciones_actuales()
    stats = asignador.estadisticas_asignacion()
    
    return {
        "asignaciones": asignaciones,
        "estadisticas": stats,
        "total_asignaciones": len(asignaciones)
    }

@app.get("/asignacion/estadisticas")
def obtener_estadisticas_asignacion():
    """Retorna estadísticas de la asignación de rutas."""
    if not asignador:
        raise HTTPException(status_code=503, detail="Sistema de asignación no inicializado")
    
    stats = asignador.estadisticas_asignacion()
    return stats

# ==========================================
# NUEVOS ENDPOINTS - CONGESTIÓN Y SALUD
# ==========================================

@app.get("/congestión/por-ruta")
def obtener_congestion_por_ruta(db: Session = Depends(get_db)):
    """
    Calcula congestión por ruta basada en pasajeros actuales vs capacidad.
    """
    vehiculos = db.query(VehiculoDB).all()
    rutas = db.query(RutaDB).all()
    
    congestión_por_ruta = {}
    
    for ruta in rutas:
        buses_en_ruta = [v for v in vehiculos if v.ruta_asignada_id == ruta.id]
        
        if not buses_en_ruta:
            congestión_por_ruta[ruta.nombre] = {
                "ruta_id": ruta.id,
                "num_buses": 0,
                "capacidad_total": 0,
                "pasajeros_total": 0,
                "congestion_porcentaje": 0,
                "estado": "🟢 SIN SERVICIO"
            }
            continue
        
        # Obtener telemetría
        telemetrias = db.query(TelemetriaBusDB).filter(
            TelemetriaBusDB.vehiculo_id.in_([b.id for b in buses_en_ruta])
        ).all()
        
        capacidad_total = sum(b.capacidad for b in buses_en_ruta)
        pasajeros_total = sum(t.pasajeros_a_bordo for t in telemetrias)
        
        if capacidad_total == 0:
            congestion_pct = 0
        else:
            congestion_pct = (pasajeros_total / capacidad_total) * 100
        
        # Determinar estado
        if congestion_pct < 50:
            estado = "🟢 BAJA"
        elif congestion_pct < 75:
            estado = "🟡 MEDIA"
        elif congestion_pct < 90:
            estado = "🔴 ALTA"
        else:
            estado = "🔴 CRÍTICA"
        
        congestión_por_ruta[ruta.nombre] = {
            "ruta_id": ruta.id,
            "num_buses": len(buses_en_ruta),
            "capacidad_total": capacidad_total,
            "pasajeros_total": pasajeros_total,
            "congestion_porcentaje": round(congestion_pct, 1),
            "estado": estado
        }
    
    return {
        "congestiones": congestión_por_ruta,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/salud/flota")
def obtener_salud_flota(db: Session = Depends(get_db)):
    """
    Retorna semáforo de salud general de la flota.
    """
    vehiculos = db.query(VehiculoDB).all()
    telemetrias = db.query(TelemetriaBusDB).all()
    
    estados = {
        "VERDE": 0,
        "AMARILLO": 0,
        "ROJO": 0
    }
    
    detalle_buses = []
    
    for v in vehiculos:
        telem = next((t for t in telemetrias if t.vehiculo_id == v.id), None)
        
        if not telem:
            estado = "AMARILLO"  # Sin telemetría reciente
        elif telem.velocidad_kmh > 80 or telem.nivel_energia < 15:
            estado = "ROJO"  # Problemas críticos
        elif telem.velocidad_kmh > 60 or telem.nivel_energia < 30:
            estado = "AMARILLO"  # Alerta
        else:
            estado = "VERDE"  # Normal
        
        estados[estado] += 1
        
        detalle_buses.append({
            "vehiculo_id": v.id,
            "placa": v.placa,
            "tipo_motor": v.tipo_motor,
            "estado": estado,
            "velocidad_kmh": telem.velocidad_kmh if telem else None,
            "nivel_energia": telem.nivel_energia if telem else None,
            "pasajeros_a_bordo": telem.pasajeros_a_bordo if telem else None
        })
    
    # Calcular salud general
    total = len(vehiculos)
    porcentaje_verde = (estados["VERDE"] / total * 100) if total > 0 else 0
    
    if porcentaje_verde >= 80:
        salud_general = "🟢 EXCELENTE"
    elif porcentaje_verde >= 60:
        salud_general = "🟡 ACEPTABLE"
    else:
        salud_general = "🔴 CRÍTICA"
    
    return {
        "salud_general": salud_general,
        "estados_resumido": estados,
        "porcentaje_verde": round(porcentaje_verde, 1),
        "total_buses": total,
        "detalle_buses": detalle_buses,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/salud/bus/{vehiculo_id}")
def obtener_salud_bus(vehiculo_id: int, db: Session = Depends(get_db)):
    """
    Retorna estado detallado de un bus específico.
    """
    vehiculo = db.query(VehiculoDB).filter(VehiculoDB.id == vehiculo_id).first()
    
    if not vehiculo:
        raise HTTPException(status_code=404, detail="Vehículo no encontrado")
    
    telem = db.query(TelemetriaBusDB).filter(TelemetriaBusDB.vehiculo_id == vehiculo_id).first()
    ruta = db.query(RutaDB).filter(RutaDB.id == vehiculo.ruta_asignada_id).first() if vehiculo.ruta_asignada_id else None
    
    # Calcular estado
    alertas = []
    
    if telem:
        if telem.velocidad_kmh > 80:
            alertas.append("⚠️ EXCESO DE VELOCIDAD")
        if telem.nivel_energia < 15:
            energía_tipo = "Batería" if vehiculo.tipo_motor == "Electrico" else "Combustible"
            alertas.append(f"⚠️ {energía_tipo} CRÍTICA")
        if telem.velocidad_kmh < 5:
            alertas.append("⏸️ BUS DETENIDO")
        
        if len(alertas) > 0:
            estado = "🔴 ALERTA"
        elif telem.velocidad_kmh > 60:
            estado = "🟡 ATENCIÓN"
        else:
            estado = "🟢 NORMAL"
    else:
        estado = "❓ SIN DATOS"
        alertas.append("No hay telemetría reciente")
    
    return {
        "vehiculo_id": vehiculo_id,
        "placa": vehiculo.placa,
        "tipo_motor": vehiculo.tipo_motor,
        "capacidad": vehiculo.capacidad,
        "estado_mecanico": vehiculo.estado_mecanico,
        "estado_operacion": vehiculo.estado_operacion,
        "salud_actual": estado,
        "alertas_activas": alertas,
        "ruta_asignada": ruta.nombre if ruta else "Sin asignar",
        "telemetria": {
            "velocidad_kmh": telem.velocidad_kmh if telem else None,
            "nivel_energia": telem.nivel_energia if telem else None,
            "pasajeros_a_bordo": telem.pasajeros_a_bordo if telem else None,
            "latitud": telem.latitud if telem else None,
            "longitud": telem.longitud if telem else None,
            "ultima_actualizacion": telem.ultima_actualizacion.isoformat() if telem else None
        }
    }

@app.get("/mapa-calor/paradas")
def obtener_mapa_calor_paradas(db: Session = Depends(get_db)):
    """
    Retorna mapa de calor de demanda por paradas.
    Útil para visualizar congestión en tiempo real.
    """
    paradas = db.query(ParadaDB).all()
    
    resultado = []
    max_personas = max([p.personas_esperando for p in paradas]) if paradas else 1
    
    for p in paradas:
        # Normalizar a escala 0-1
        intensidad = p.personas_esperando / max_personas if max_personas > 0 else 0
        
        # Determinar color
        if intensidad < 0.33:
            color = "🟢 BAJA"
        elif intensidad < 0.66:
            color = "🟡 MEDIA"
        else:
            color = "🔴 ALTA"
        
        resultado.append({
            "parada_id": p.id,
            "nombre": p.nombre,
            "latitud": p.latitud,
            "longitud": p.longitud,
            "personas_esperando": p.personas_esperando,
            "intensidad": round(intensidad, 2),
            "categoria": color
        })
    
    return {
        "mapa_calor": resultado,
        "max_personas": max_personas,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/alertas/activas")
def obtener_alertas_activas(db: Session = Depends(get_db)):
    """Retorna todas las alertas activas del sistema."""
    alertas = db.query(AlertaDB).order_by(AlertaDB.fecha.desc()).limit(50).all()
    
    resultado = []
    for a in alertas:
        v = db.query(VehiculoDB).filter(VehiculoDB.id == a.vehiculo_id).first()
        
        resultado.append({
            "alerta_id": a.id,
            "vehiculo_id": a.vehiculo_id,
            "placa": v.placa if v else "S/P",
            "tipo_alerta": a.tipo_alerta,
            "descripcion": a.descripcion,
            "fecha": a.fecha.isoformat(),
            "severidad": "🔴 CRÍTICA" if a.tipo_alerta in ["EXCESO_VELOCIDAD", "BATERIA_BAJA", "COMBUSTIBLE_BAJO"] else "🟡 INFO"
        })
    
    return {
        "alertas": resultado,
        "total": len(resultado)
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
