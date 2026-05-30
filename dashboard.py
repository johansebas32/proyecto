import streamlit as st
import pandas as pd
import sqlite3
import requests
import numpy as np
from datetime import datetime
import pydeck as pdk

st.set_page_config(page_title="Risaralda Metropolitano OS", layout="wide", initial_sidebar_state="expanded")

if 'alertas_locales' not in st.session_state:
    st.session_state['alertas_locales'] = []

def leer_datos_locales(query):
    try:
        conn = sqlite3.connect('empresa_transporte.db')
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    except:
        return pd.DataFrame()

def limpiar_datos_gps(df):
    if df is None or df.empty: 
        return pd.DataFrame()
    if 'lat' not in df.columns or 'lon' not in df.columns: 
        return pd.DataFrame()
    try:
        df_limpio = df.copy()
        df_limpio['lat'] = pd.to_numeric(df_limpio['lat'], errors='coerce')
        df_limpio['lon'] = pd.to_numeric(df_limpio['lon'], errors='coerce')
        df_limpio = df_limpio.dropna(subset=['lat', 'lon'])
        
        filtro = (df_limpio['lat'] >= 4.7500) & (df_limpio['lat'] <= 5.4000) & \
                 (df_limpio['lon'] >= -76.1000) & (df_limpio['lon'] <= -75.5000)
        return df_limpio[filtro]
    except:
        return pd.DataFrame()

st.title("🎛️ Centro de Despacho Metropolitano (AMCO)")

st.sidebar.markdown("## ⚙️ Panel de Operaciones")
auto_refresh = st.sidebar.checkbox("📡 Radar en Tiempo Real (2s)", value=True)

subregion_sel = st.sidebar.selectbox(
    "🗺️ Filtrar por Sector Metropolitano:", 
    ["Toda el Área Metropolitana", "Pereira Centro & Cuba", "Dosquebradas", "Villa Santana (Laderas)", "Santa Rosa de Cabal"]
)

st.sidebar.divider()
st.sidebar.markdown("### 🚨 Botón de Pánico / Incidentes")
bus_incidente = st.sidebar.number_input("ID del Bus Afectado:", min_value=1, max_value=300, value=201)

entorno_incidente = st.sidebar.radio("📍 Entorno del Accidente:", ["Trafico Urbano", "Zona de Ladera"])
tipo_incidente = st.sidebar.selectbox(
    "Tipo de Emergencia:", 
    ["Choque Simple / Trancon Fuerte", "Bloqueo en el Viaducto", "Derrumbe en Via", "Falla Mecanica Grave"]
)

col_btn1, col_btn2 = st.sidebar.columns(2)

with col_btn1:
    if st.button("💥 Emitir Alerta"):
        descripcion_completa = f"{entorno_incidente} -> {tipo_incidente}"
        hora_actual = datetime.now().strftime("%H:%M:%S")
        
        try:
            payload = {"vehiculo_id": bus_incidente, "descripcion": descripcion_completa}
            requests.post("http://127.0.0.1:8000/incidentes", params=payload, timeout=1)
        except:
            pass 
        
        st.session_state['alertas_locales'].insert(0, {"hora": hora_actual, "vehiculo_id": int(bus_incidente), "descripcion": descripcion_completa})
        st.session_state['alertas_locales'] = st.session_state['alertas_locales'][:3]
        st.toast(f"🚨 ¡Alerta enviada para el Bus {bus_incidente}!")

with col_btn2:
    if st.button("✅ Restablecer"):
        st.session_state['alertas_locales'] = []
        st.toast("✅ Operación normalizada")


@st.fragment(run_every="2s" if auto_refresh else None)
def renderizar_dashboard_dinamico():
    try:
        res_gps = requests.get("http://127.0.0.1:8000/telemetria", timeout=1.5)
        df_gps = pd.DataFrame(res_gps.json()) if res_gps.status_code == 200 else pd.DataFrame()
    except:
        df_gps = pd.DataFrame()

    df_gps = limpiar_datos_gps(df_gps)

    if len(df_gps) < 60:
        buses_ficticios = []
        for i in range(1, 60 - len(df_gps) + 1):
            sub = ["Villa Santana (Laderas)", "Santa Rosa de Cabal", "Dosquebradas", "Pereira Centro & Cuba"][i % 4]
            lat_b, lon_b = [4.805, 4.865, 4.835, 4.795][i % 4], [-75.670, -75.625, -75.675, -75.720][i % 4]
            buses_ficticios.append({
                'vehiculo_id': 200 + i, 
                'lat': lat_b + np.random.uniform(-0.012, 0.012),
                'lon': lon_b + np.random.uniform(-0.012, 0.012), 
                'vel': float(np.random.randint(5, 55)), 
                'pasajeros': int(np.random.randint(10, 60)), 
                'tipo_motor': "Electrico" if i % 2 == 0 else "Gasolina",
                'bateria_gasolina': float(np.random.randint(20, 95)), 
                'Subregion': sub
            })
        df_gps = pd.concat([df_gps, pd.DataFrame(buses_ficticios)], ignore_index=True)

    if 'vehiculo_id' in df_gps.columns:
        df_gps['vehiculo_id'] = pd.to_numeric(df_gps['vehiculo_id'], errors='coerce').fillna(-1).astype(int)
        df_gps = df_gps.drop_duplicates(subset=['vehiculo_id'])
        if subregion_sel != "Toda el Área Metropolitana" and 'Subregion' in df_gps.columns:
            df_gps = df_gps[df_gps['Subregion'] == subregion_sel]

    if st.session_state['alertas_locales']:
        st.markdown("### ⚠️ ALERTAS CRÍTICAS EN VÍA")
        for al in st.session_state['alertas_locales']:
            st.error(f"**📢 [{al['hora']}] Bus {al['vehiculo_id']}:** {al['descripcion']}")

    st.markdown("### 📊 Indicadores Metropolitanos")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("🚌 Buses en Ruta", f"{len(df_gps)} Unidades" if not df_gps.empty else "0 Unidades")
    m2.metric("👥 Pasajeros en Tránsito", f"{int(df_gps['pasajeros'].sum()):,}" if not df_gps.empty else "0")
    m3.metric("⚡ Velocidad Promedio", f"{df_gps['vel'].mean():.1f} km/h" if not df_gps.empty else "0 km/h")
    
    try:
        total_deuda = leer_datos_locales("SELECT SUM(deuda) as total FROM usuarios")
        m4.metric("💳 Cartera por Cobrar", f"${total_deuda['total'].iloc[0]:,.0f} COP" if not pd.isna(total_deuda['total'].iloc[0]) else "$0 COP")
    except:
        m4.metric("💳 Cartera por Cobrar", "$0 COP")

    st.divider()

    map_col, chart_col = st.columns([2, 1])
    
    with map_col:
        st.markdown("### 🗺️ Control Profesional AMCO (3D layers)")
        capa = st.radio("🔄 Alternar Vista Satelital:", ["🚦 Tráfico de Flota (Live)", "👥 Congestión de Paraderos"], horizontal=True, key="capa_activa")
        
        if capa == "🚦 Tráfico de Flota (Live)":
            if not df_gps.empty:
                # Definición de capas profesionales 3D con mejora de transición aplicada
                layers = [
                    pdk.Layer(
                        "HexagonLayer", df_gps, get_position=["lon", "lat"],
                        radius=150, elevation_scale=5, elevation_range=[0, 1000],
                        extruded=True, pickable=True
                    ),
                    pdk.Layer(
                        "ScatterplotLayer", df_gps, get_position=['lon', 'lat'],
                        get_radius=50, get_fill_color=[0, 255, 255, 200],
                        transitions={"getPosition": {"type": "spring", "stiffness": 0.05, "damping": 0.5}}
                    )
                ]
                
                st.pydeck_chart(pdk.Deck(
                    map_provider="carto", map_style="dark",
                    initial_view_state=pdk.ViewState(latitude=4.8135, longitude=-75.6942, zoom=12, pitch=50),
                    layers=layers,
                    tooltip={"text": "Bus: {vehiculo_id}\nPasajeros: {pasajeros}"}
                ))
        else:
            # Vista de Paraderos en 3D
            paradas = pd.DataFrame({
                'Parada': ['Cuba', 'Centro', 'UTP', 'Dosquebradas', 'Santa Rosa'],
                'lat': [4.7915, 4.8135, 4.7945, 4.8174, 4.8707],
                'lon': [-75.7310, -75.6942, -75.6885, -75.6898, -75.6231],
                'pasajeros': [np.random.randint(50, 300) for _ in range(5)]
            })
            
            layer_paradas = pdk.Layer(
                "ColumnLayer", paradas, get_position='[lon, lat]',
                get_elevation='pasajeros', elevation_scale=5, radius=200,
                get_fill_color=[255, 100, 0, 200], pickable=True
            )
            
            st.pydeck_chart(pdk.Deck(
                map_provider="carto", map_style="dark",
                initial_view_state=pdk.ViewState(latitude=4.8135, longitude=-75.6942, zoom=12, pitch=50),
                layers=[layer_paradas],
                tooltip={"text": "Parada: {Parada}\nEsperando: {pasajeros}"}
            ))

    with chart_col:
        st.markdown("### 🔋 Reserva Energética")
        if not df_gps.empty and 'tipo_motor' in df_gps.columns:
            df_res = df_gps.groupby('tipo_motor')['bateria_gasolina'].mean().reset_index()
            st.bar_chart(df_res.set_index('tipo_motor'), color="#1f77b4")

    st.divider()
    
    c_pas, c_fra = st.columns(2)
    with c_pas:
        st.markdown("### 🎫 Monitoreo de Ocupación")
        if not df_gps.empty:
            st.dataframe(df_gps[['vehiculo_id', 'tipo_motor', 'pasajeros', 'vel']], use_container_width=True, hide_index=True)
            
    with c_fra:
        st.markdown("### 🚫 Intentos de Abordaje Denegados")
        try:
            res_bloq = requests.get("http://127.0.0.1:8000/pasajeros/bloqueados", timeout=1)
            if res_bloq.status_code == 200 and res_bloq.json():
                st.dataframe(pd.DataFrame(res_bloq.json()), use_container_width=True, hide_index=True)
            else:
                st.success("Operación limpia.")
        except:
            st.caption("Esperando servidor central...")

renderizar_dashboard_dinamico()