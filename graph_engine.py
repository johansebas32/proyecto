import numpy as np
import heapq
from typing import List, Dict, Tuple, Optional
from database import SessionLocal
from models import (
    ParadaDB,
    RutaParadaDB,
    RutaDB
)


class GrafoMetropolitano:
    """
    Grafo ponderado para el sistema de transporte metropolitano.
    Nodos: Paradas
    Pesos: Distancia en km
    """

    def __init__(self):
        self.db = SessionLocal()
        
        # Cargar paradas
        self.paradas = (
            self.db.query(ParadaDB)
            .order_by(ParadaDB.id)
            .all()
        )

        # Mapeos: ID parada <-> índice matriz
        self.nodos = {
            parada.id: idx
            for idx, parada in enumerate(self.paradas)
        }

        self.nombres = {
            parada.id: parada.nombre
            for parada in self.paradas
        }

        n = len(self.paradas)

        # Matriz ponderada: DISTANCIAS (no solo 0 y 1)
        self.matriz_ponderada = np.full(
            (n, n),
            np.inf,
            dtype=float
        )
        
        # Diagonal = 0 (distancia a sí mismo)
        np.fill_diagonal(self.matriz_ponderada, 0)

        # Matriz de adyacencia (booleana)
        self.matriz_adyacencia = np.zeros(
            (n, n),
            dtype=int
        )

        self.construir_grafo()

    def construir_grafo(self):
        """
        Construye ambas matrices desde RutaParadaDB.
        """
        rutas = (
            self.db.query(RutaParadaDB)
            .order_by(
                RutaParadaDB.ruta_id,
                RutaParadaDB.orden_secuencia
            )
            .all()
        )

        rutas_dict = {}
        for r in rutas:
            rutas_dict.setdefault(
                r.ruta_id,
                []
            ).append(r.parada_id)

        # Para cada ruta, conectar paradas consecutivas
        for ruta_id, secuencia_paradas in rutas_dict.items():
            
            # Obtener la ruta para acceder a distancia_km
            ruta_obj = self.db.query(RutaDB).filter_by(id=ruta_id).first()
            
            for i in range(len(secuencia_paradas) - 1):
                
                parada_origen_id = secuencia_paradas[i]
                parada_destino_id = secuencia_paradas[i + 1]
                
                idx_origen = self.nodos[parada_origen_id]
                idx_destino = self.nodos[parada_destino_id]

                # Matriz de adyacencia (conexión binaria)
                self.matriz_adyacencia[idx_origen, idx_destino] = 1
                self.matriz_adyacencia[idx_destino, idx_origen] = 1

                # Matriz ponderada (distancia en km)
                # Dividir distancia total entre segmentos
                num_segmentos = len(secuencia_paradas) - 1
                peso = ruta_obj.distancia_km / num_segmentos if num_segmentos > 0 else 0

                self.matriz_ponderada[idx_origen, idx_destino] = peso
                self.matriz_ponderada[idx_destino, idx_origen] = peso

    # ==========================================
    # CONSULTAS BÁSICAS
    # ==========================================

    def obtener_matriz_adyacencia(self):
        """Retorna la matriz de adyacencia (booleana)."""
        return self.matriz_adyacencia.tolist()

    def obtener_matriz_ponderada(self):
        """Retorna la matriz ponderada (distancias)."""
        return self.matriz_ponderada.tolist()

    def grado_nodo(self, parada_id: int) -> int:
        """Grado del nodo (cuántas paradas conecta)."""
        idx = self.nodos[parada_id]
        return int(np.sum(self.matriz_adyacencia[idx]))

    def centralidad(self) -> List[Dict]:
        """Retorna paradas ordenadas por centralidad (grado)."""
        resultado = []
        for parada_id in self.nodos:
            resultado.append({
                "parada_id": parada_id,
                "nombre": self.nombres[parada_id],
                "grado": self.grado_nodo(parada_id)
            })
        resultado.sort(
            key=lambda x: x["grado"],
            reverse=True
        )
        return resultado

    # ==========================================
    # ALGORITMO DE DIJKSTRA
    # ==========================================

    def dijkstra(
        self,
        parada_origen_id: int,
        parada_destino_id: int
    ) -> Tuple[float, List[int], List[str]]:
        """
        Calcula la ruta más corta usando algoritmo de Dijkstra.
        
        Args:
            parada_origen_id: ID de parada de origen
            parada_destino_id: ID de parada de destino
        
        Returns:
            (distancia_total_km, lista_ids_paradas, lista_nombres_paradas)
        """
        if parada_origen_id not in self.nodos:
            return (np.inf, [], [])
        
        if parada_destino_id not in self.nodos:
            return (np.inf, [], [])

        n = len(self.paradas)
        idx_origen = self.nodos[parada_origen_id]
        idx_destino = self.nodos[parada_destino_id]

        # Inicializar distancias
        distancias = np.full(n, np.inf, dtype=float)
        distancias[idx_origen] = 0

        # Rastrear camino
        padres = [-1] * n
        visitados = [False] * n

        # Cola de prioridad: (distancia, índice)
        heap = [(0, idx_origen)]

        while heap:
            dist_actual, idx_actual = heapq.heappop(heap)

            if visitados[idx_actual]:
                continue

            visitados[idx_actual] = True

            # Si llegamos al destino
            if idx_actual == idx_destino:
                break

            # Explorar vecinos
            for idx_vecino in range(n):
                if not visitados[idx_vecino]:
                    # Verificar si hay arista
                    peso = self.matriz_ponderada[idx_actual, idx_vecino]
                    
                    if peso < np.inf:
                        nueva_dist = dist_actual + peso

                        if nueva_dist < distancias[idx_vecino]:
                            distancias[idx_vecino] = nueva_dist
                            padres[idx_vecino] = idx_actual
                            heapq.heappush(
                                heap,
                                (nueva_dist, idx_vecino)
                            )

        # Reconstruir camino
        camino_indices = []
        idx_actual = idx_destino

        if distancias[idx_destino] < np.inf:
            while idx_actual != -1:
                camino_indices.append(idx_actual)
                idx_actual = padres[idx_actual]

            camino_indices.reverse()

            # Convertir índices a IDs y nombres
            camino_ids = [
                list(self.nodos.keys())[list(self.nodos.values()).index(idx)]
                for idx in camino_indices
            ]

            camino_nombres = [
                self.nombres[parada_id]
                for parada_id in camino_ids
            ]

            return (
                round(distancias[idx_destino], 2),
                camino_ids,
                camino_nombres
            )
        else:
            return (np.inf, [], [])

    # ==========================================
    # ANÁLISIS DE RED
    # ==========================================

    def distancia_minima_entre_todos(self) -> float:
        """Distancia mínima entre cualquier par de paradas."""
        matriz_temp = self.matriz_ponderada.copy()
        np.fill_diagonal(matriz_temp, np.inf)
        return float(np.nanmin(matriz_temp[matriz_temp < np.inf]))

    def distancia_maxima_entre_todos(self) -> float:
        """Distancia máxima entre paradas conectadas."""
        matriz_temp = self.matriz_ponderada.copy()
        np.fill_diagonal(matriz_temp, np.inf)
        return float(np.nanmax(matriz_temp[matriz_temp < np.inf]))

    def paradas_mas_conectadas(self, top: int = 5) -> List[Dict]:
        """Top N paradas más conectadas."""
        return self.centralidad()[:top]

    def componentes_conexas(self) -> List[List[str]]:
        """
        Identifica componentes conexas del grafo.
        Retorna listas de nombres de paradas por componente.
        """
        n = len(self.paradas)
        visitados = [False] * n
        componentes = []

        def dfs(idx, componente):
            visitados[idx] = True
            componente.append(idx)
            
            for j in range(n):
                if not visitados[j] and self.matriz_adyacencia[idx, j]:
                    dfs(j, componente)

        for i in range(n):
            if not visitados[i]:
                componente = []
                dfs(i, componente)
                
                nombres_comp = [
                    list(self.nombres.values())[j]
                    for j in componente
                ]
                componentes.append(nombres_comp)

        return componentes
