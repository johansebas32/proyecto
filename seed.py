import sqlite3
import random
from datetime import datetime, timedelta

def poblar_sistema_masivo():
    conn = sqlite3.connect('empresa_transporte.db')
    cursor = conn.cursor()
    
    tablas = ['alertas_flota', 'telemetria_buses', 'historial_viajes', 'ruta_paradas', 'paradas', 'rutas', 'conductores', 'usuarios', 'vehiculos']
    for t in tablas: cursor.execute(f"DROP TABLE IF EXISTS {t}")
    conn.commit()
    
    print("🏗️ Configurando Servidor Masivo para 14 Municipios de RISARALDA...")
    
    cursor.execute("CREATE TABLE vehiculos (id INTEGER PRIMARY KEY, placa TEXT UNIQUE, capacidad INTEGER, tipo_motor TEXT, estado_mecanico TEXT)")
    cursor.execute("CREATE TABLE conductores (id TEXT PRIMARY KEY, nombre TEXT, licencia TEXT UNIQUE, experiencia_anos INTEGER, vehiculo_actual_id INTEGER)")
    cursor.execute("CREATE TABLE rutas (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE, codigo_ruta TEXT UNIQUE, tarifa_base REAL)")
    cursor.execute("CREATE TABLE paradas (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT, latitud REAL, longitud REAL)")
    cursor.execute("CREATE TABLE ruta_paradas (id INTEGER PRIMARY KEY AUTOINCREMENT, ruta_id INTEGER, parada_id INTEGER, orden_secuencia INTEGER)")
    cursor.execute("CREATE TABLE usuarios (id TEXT PRIMARY KEY, nombre TEXT, saldo_billetera REAL, deuda REAL, tipo_usuario TEXT)")
    cursor.execute("CREATE TABLE historial_viajes (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario_id TEXT, ruta_id INTEGER, vehiculo_id INTEGER, fecha TEXT, costo_aplicado REAL, metodo_pago TEXT)")
    cursor.execute("CREATE TABLE telemetria_buses (vehiculo_id INTEGER PRIMARY KEY, latitud REAL, longitud REAL, velocidad_kmh REAL, nivel_energia REAL, pasajeros_a_bordo INTEGER, ultima_actualizacion TEXT)")
    cursor.execute("CREATE TABLE alertas_flota (id INTEGER PRIMARY KEY AUTOINCREMENT, vehiculo_id INTEGER, tipo_alerta TEXT, descripcion TEXT, fecha TEXT)")
    
    print("🚌 Fabricando 150 Buses y Contratando Conductores...")
    vehiculos, conductores = [], []
    for i in range(1, 151):
        tipo_motor = "Electrico" if i <= 75 else "Gasolina"
        vehiculos.append((i, f"RIS-{i:03d}", random.choice([40, 60, 80]), tipo_motor, "Optimo"))
        
        licencia_unica = f"LIC-{1000 + i}" 
        conductores.append((f"C{i:03d}", f"Conductor {i}", licencia_unica, random.randint(1, 20), i))
    
    cursor.executemany("INSERT INTO vehiculos VALUES (?, ?, ?, ?, ?)", vehiculos)
    cursor.executemany("INSERT INTO conductores VALUES (?, ?, ?, ?, ?)", conductores)

    print("🗺️ Registrando los 14 Corredores Regionales...")
    rutas_nombres = [
        "Pereira Centro", "Dosquebradas Viaducto", "Santa Rosa Termales", 
        "La Virginia Valle", "Marsella Cultura", "Belén de Umbría Café", 
        "Apía Vientos", "Santuario Tatamá", "Quinchía Villa", 
        "Guática Seda", "Balboa Mirador", "La Celia Naturaleza", 
        "Pueblo Rico Chocó", "Mistrató Indígena"
    ]
    rutas = [(idx+1, nombre, f"R-{idx+1:02d}", random.uniform(3000, 20000)) for idx, nombre in enumerate(rutas_nombres)]
    cursor.executemany("INSERT INTO rutas VALUES (?, ?, ?, ?)", rutas)

    print("👥 Creando 300 Usuarios y Asignando Deudas...")
    usuarios = []
    nombres = ["Juan", "Sara", "Pedro", "Maria", "Luis", "Ana", "Diego", "Paula", "Andres", "Camila"]
    apellidos = ["Gomez", "Restrepo", "Perez", "Jaramillo", "Cano", "Lopez", "Marin", "Ospina"]
    for idx in range(1, 301):
        nombre = f"{random.choice(nombres)} {random.choice(apellidos)} {idx}"
        deuda = round(random.uniform(1000, 100000), 2) if random.random() > 0.7 else 0.0
        usuarios.append((f"U{idx:03d}", nombre, random.uniform(0, 50000), deuda, "Regular"))
    cursor.executemany("INSERT INTO usuarios VALUES (?, ?, ?, ?, ?)", usuarios)

    print("📈 Generando 3000 Viajes para la IA...")
    viajes = []
    base_date = datetime.now()
    for _ in range(3000):
        fecha = (base_date - timedelta(days=random.randint(0, 30), hours=random.randint(0, 23), minutes=random.randint(0,59))).strftime("%Y-%m-%d %H:%M:%S")
        viajes.append((f"U{random.randint(1, 300):03d}", random.randint(1, 14), random.randint(1, 150), fecha, 3500.0, "Tarjeta"))
    cursor.executemany("INSERT INTO historial_viajes (usuario_id, ruta_id, vehiculo_id, fecha, costo_aplicado, metodo_pago) VALUES (?, ?, ?, ?, ?, ?)", viajes)

    conn.commit()
    conn.close()
    print("✅ Sistema a Gran Escala Listo.")

if __name__ == "__main__":
    poblar_sistema_masivo()