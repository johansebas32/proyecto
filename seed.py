from database import Base, engine, SessionLocal
from models import (
    VehiculoDB,
    ConductorDB,
    RutaDB,
    ParadaDB,
    RutaParadaDB,
    UsuarioDB,
    HistorialViajesDB,
    TelemetriaBusDB
)

import random
import json
from datetime import datetime, timedelta

print("🧹 Reiniciando base de datos...")

Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

db = SessionLocal()

# =========================
# PARADAS
# =========================

PARADAS = [
    ("Cuba",4.7915,-75.7310),
    ("Centro",4.8135,-75.6942),
    ("UTP",4.7945,-75.6885),
    ("Dosquebradas",4.8174,-75.6898),
    ("Santa Rosa",4.8707,-75.6231),

    ("Villa Santana",4.8070,-75.6710),
    ("El Jardín",4.8030,-75.7020),
    ("Terminal",4.8150,-75.7000),
    ("Boston",4.8080,-75.6900),
    ("Samaria",4.8210,-75.6750),

    ("Frailes",4.8400,-75.6700),
    ("La Badea",4.8290,-75.6820),
    ("Viaducto",4.8140,-75.6880),
    ("La Virginia",4.8990,-75.8830),
    ("Marsella",4.9370,-75.7370),

    ("Apía",5.1060,-75.9430),
    ("Santuario",5.0800,-75.9650),
    ("Belén",5.2000,-75.8670),
    ("Mistrató",5.2960,-75.8830),
    ("Pueblo Rico",5.2240,-76.0360)
]

paradas_db = []

for nombre, lat, lon in PARADAS:

    parada = ParadaDB(
        nombre=nombre,
        latitud=lat,
        longitud=lon,
        personas_esperando=random.randint(20,250)
    )

    db.add(parada)
    paradas_db.append(parada)

db.commit()

print("✅ 20 paradas creadas")

# =========================
# RUTAS
# =========================

rutas_base = [
    "Pereira Centro",
    "Dosquebradas Viaducto",
    "Santa Rosa Termales",
    "La Virginia Valle",
    "Marsella Cultura",
    "Belén Café",
    "Apía Vientos",
    "Santuario Tatamá",
    "Quinchía Villa",
    "Guática Seda",
    "Balboa Mirador",
    "La Celia Naturaleza",
    "Pueblo Rico Chocó",
    "Mistrató Indígena"
]

for i, nombre in enumerate(rutas_base, start=1):

    origen = random.choice(PARADAS)
    destino = random.choice(PARADAS)

    path = [
        [origen[2], origen[1]],
        [
            (origen[2]+destino[2])/2,
            (origen[1]+destino[1])/2
        ],
        [destino[2], destino[1]]
    ]

    ruta = RutaDB(
        nombre=nombre,
        codigo_ruta=f"R-{i:02d}",
        tarifa_base=random.randint(3000,7000),
        geometria_ruta=json.dumps(path)
    )

    db.add(ruta)

db.commit()

print("✅ 14 rutas creadas")

# =========================
# VEHÍCULOS
# =========================

for i in range(1,201):

    vehiculo = VehiculoDB(
        id=i,
        placa=f"RIS-{i:03d}",
        capacidad=random.choice([40,60,80]),
        tipo_motor="Electrico" if i <= 100 else "Gasolina",
        estado_mecanico="Optimo"
    )

    db.add(vehiculo)

db.commit()

print("✅ 200 buses creados")

# =========================
# CONDUCTORES
# =========================

for i in range(1,201):

    conductor = ConductorDB(
        id=f"C{i:03d}",
        nombre=f"Conductor {i}",
        licencia=f"LIC-{1000+i}",
        experiencia_anos=random.randint(1,20),
        vehiculo_actual_id=i
    )

    db.add(conductor)

db.commit()

print("✅ 200 conductores creados")

# =========================
# USUARIOS
# =========================

nombres = [
    "Juan","Sara","Pedro","Maria","Luis",
    "Ana","Camila","Diego","Andres","Paula"
]

apellidos = [
    "Gomez","Restrepo","Perez","Lopez",
    "Marin","Ospina","Jaramillo"
]

for i in range(1,501):

    usuario = UsuarioDB(
        id=f"U{i:04d}",
        nombre=f"{random.choice(nombres)} {random.choice(apellidos)} {i}",
        saldo_billetera=random.randint(0,50000),
        deuda=random.randint(0,120000) if random.random() > 0.7 else 0,
        tipo_usuario="Regular"
    )

    db.add(usuario)

db.commit()

print("✅ 500 usuarios creados")

# =========================
# TELEMETRÍA INICIAL
# =========================

for i in range(1,201):

    parada = random.choice(PARADAS)

    telemetria = TelemetriaBusDB(
        vehiculo_id=i,
        latitud=parada[1],
        longitud=parada[2],
        velocidad_kmh=random.uniform(10,60),
        nivel_energia=random.uniform(30,100),
        pasajeros_a_bordo=random.randint(0,70),
        estado_salud="VERDE"
    )

    db.add(telemetria)

db.commit()

print("✅ Telemetría inicial creada")

# =========================
# HISTORIAL
# =========================

fecha_base = datetime.now()

for i in range(10000):

    viaje = HistorialViajesDB(
        usuario_id=f"U{random.randint(1,500):04d}",
        ruta_id=random.randint(1,14),
        vehiculo_id=random.randint(1,200),
        fecha=fecha_base - timedelta(
            days=random.randint(0,60),
            hours=random.randint(0,23),
            minutes=random.randint(0,59)
        ),
        costo_aplicado=random.randint(3000,7000),
        metodo_pago="Tarjeta_NFC"
    )

    db.add(viaje)

    if i % 500 == 0:
        db.commit()

db.commit()

print("✅ 10.000 viajes históricos creados")

db.close()

print("🚀 Sistema Metropolitano RISARALDA listo")