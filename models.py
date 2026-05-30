from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    ForeignKey,
    DateTime,
    Text
)

from database import Base
import datetime


# ======================================================
# VEHICULOS
# ======================================================

class VehiculoDB(Base):
    __tablename__ = "vehiculos"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    placa = Column(
        String(10),
        unique=True,
        nullable=False
    )

    capacidad = Column(
        Integer,
        default=40
    )

    tipo_motor = Column(
        String(20),
        nullable=False
    )

    estado_mecanico = Column(
        String(20),
        default="Optimo"
    )

    # NUEVO
    ruta_asignada_id = Column(
        Integer,
        ForeignKey("rutas.id"),
        nullable=True
    )

    # posición matemática sobre la ruta
    posicion_ruta = Column(
        Float,
        default=0.0
    )

    # 1 = ida
    # -1 = regreso
    sentido = Column(
        Integer,
        default=1
    )

    ocupacion_actual = Column(
        Integer,
        default=0
    )

    estado_operacion = Column(
        String(20),
        default="EN_SERVICIO"
    )


# ======================================================
# HISTORICO GPS
# ======================================================

class HistoricoRutaDB(Base):
    __tablename__ = "historico_rutas"

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    vehiculo_id = Column(
        Integer,
        ForeignKey("vehiculos.id")
    )

    latitud = Column(Float)
    longitud = Column(Float)

    velocidad_kmh = Column(
        Float,
        default=0
    )

    timestamp = Column(
        DateTime,
        default=datetime.datetime.utcnow
    )


# ======================================================
# CONDUCTORES
# ======================================================

class ConductorDB(Base):
    __tablename__ = "conductores"

    id = Column(
        String(20),
        primary_key=True,
        index=True
    )

    nombre = Column(
        String(100),
        nullable=False
    )

    licencia = Column(
        String(20),
        unique=True,
        nullable=False
    )

    experiencia_anos = Column(
        Integer,
        default=0
    )

    vehiculo_actual_id = Column(
        Integer,
        ForeignKey("vehiculos.id"),
        nullable=True
    )


# ======================================================
# RUTAS
# ======================================================

class RutaDB(Base):
    __tablename__ = "rutas"

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    nombre = Column(
        String(100),
        unique=True,
        nullable=False
    )

    codigo_ruta = Column(
        String(10),
        unique=True,
        nullable=False
    )

    tarifa_base = Column(
        Float,
        default=2900.0
    )

    geometria_ruta = Column(
        Text,
        nullable=True
    )

    # NUEVO
    distancia_km = Column(
        Float,
        default=0
    )

    tiempo_estimado_min = Column(
        Float,
        default=0
    )

    demanda_promedio = Column(
        Integer,
        default=0
    )


# ======================================================
# PARADAS
# ======================================================

class ParadaDB(Base):
    __tablename__ = "paradas"

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    nombre = Column(
        String(100),
        nullable=False
    )

    latitud = Column(
        Float,
        nullable=False
    )

    longitud = Column(
        Float,
        nullable=False
    )

    personas_esperando = Column(
        Integer,
        default=0
    )

    demanda_historica = Column(
        Integer,
        default=0
    )


# ======================================================
# RUTA PARADAS
# ======================================================

class RutaParadaDB(Base):
    __tablename__ = "ruta_paradas"

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    ruta_id = Column(
        Integer,
        ForeignKey("rutas.id"),
        nullable=False
    )

    parada_id = Column(
        Integer,
        ForeignKey("paradas.id"),
        nullable=False
    )

    orden_secuencia = Column(
        Integer,
        nullable=False
    )


# ======================================================
# USUARIOS
# ======================================================

class UsuarioDB(Base):
    __tablename__ = "usuarios"

    id = Column(
        String(20),
        primary_key=True,
        index=True
    )

    nombre = Column(
        String(100),
        nullable=False
    )

    saldo_billetera = Column(
        Float,
        default=0.0
    )

    deuda = Column(
        Float,
        default=0.0
    )

    tipo_usuario = Column(
        String(20),
        default="Regular"
    )


# ======================================================
# VIAJES
# ======================================================

class HistorialViajesDB(Base):
    __tablename__ = "historial_viajes"

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    usuario_id = Column(
        String(20),
        ForeignKey("usuarios.id"),
        nullable=False
    )

    ruta_id = Column(
        Integer,
        ForeignKey("rutas.id"),
        nullable=False
    )

    vehiculo_id = Column(
        Integer,
        ForeignKey("vehiculos.id"),
        nullable=False
    )

    fecha = Column(
        DateTime,
        default=datetime.datetime.utcnow
    )

    costo_aplicado = Column(
        Float,
        nullable=False
    )

    metodo_pago = Column(
        String(20),
        default="Tarjeta_NFC"
    )


# ======================================================
# TELEMETRIA
# ======================================================

class TelemetriaBusDB(Base):
    __tablename__ = "telemetria_buses"

    vehiculo_id = Column(
        Integer,
        ForeignKey("vehiculos.id"),
        primary_key=True
    )

    latitud = Column(
        Float,
        nullable=False
    )

    longitud = Column(
        Float,
        nullable=False
    )

    velocidad_kmh = Column(
        Float,
        default=0.0
    )

    nivel_energia = Column(
        Float,
        default=100.0
    )

    pasajeros_a_bordo = Column(
        Integer,
        default=0
    )

    estado_salud = Column(
        String(20),
        default="VERDE"
    )

    ultima_actualizacion = Column(
        DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow
    )


# ======================================================
# ALERTAS
# ======================================================

class AlertaDB(Base):
    __tablename__ = "alertas_flota"

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    vehiculo_id = Column(
        Integer,
        ForeignKey("vehiculos.id"),
        nullable=False
    )

    tipo_alerta = Column(
        String(50),
        nullable=False
    )

    descripcion = Column(
        String(200),
        nullable=False
    )

    fecha = Column(
        DateTime,
        default=datetime.datetime.utcnow
    )