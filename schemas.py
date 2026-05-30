from pydantic import BaseModel
from typing import List, Optional

class TelemetriaIn(BaseModel):
    latitud: float
    longitud: float
    velocidad_kmh: float
    nivel_energia: float
    pasajeros_a_bordo: int
    ruta_historial: Optional[List[List[float]]] = None