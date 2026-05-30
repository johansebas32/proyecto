import streamlit as st
import pandas as pd
import sqlite3
import requests
import numpy as np
from datetime import datetime
import pydeck as pdk

st.set_page_config(
    page_title="Risaralda Metropolitano OS",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
.stApp {
    background-color: #0f172a;
}
</style>
""", unsafe_allow_html=True)

RUTAS_METRO = [
    [[-75.7310,4.7915],[-75.7200,4.8000],[-75.7050,4.8070],[-75.6942,4.8135]],
    [[-75.6942,4.8135],[-75.6910,4.8140],[-75.6898,4.8174]],
    [[-75.6942,4.8135],[-75.6920,4.8070],[-75.6885,4.7945]],
    [[-75.6942,4.8135],[-75.6700,4.8300],[-75.6500,4.8500],[-75.6231,4.8707]]
]

if 'alertas_locales' not in st.session_state:
    st.session_state['alertas_locales'] = []

if 'historial_posiciones' not in st.session_state:
    st.session_state['historial_posiciones'] = {}


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

    df = df.copy()

    df['lat'] = pd.to_numeric(df['lat'], errors='coerce')
    df['lon'] = pd.to_numeric(df['lon'], errors='coerce')

    df = df.dropna(subset=['lat', 'lon'])

    return df[
        (df['lat'] >= 4.75) &
        (df['lat'] <= 5.40) &
        (df['lon'] >= -76.10) &
        (df['lon'] <= -75.50)
    ]


def calcular_estado_salud(row):
    if row['vel'] < 5:
        return '🔴 DETENIDO'
    if row['vel'] < 20:
        return '🟡 LENTO'
    return '🟢 NORMAL'


st.title('🎛️ Centro Inteligente Metropolitano AMCO')

st.sidebar.markdown('## ⚙️ Centro Operacional')
auto_refresh = st.sidebar.checkbox('📡 Tiempo Real', value=True)


@st.fragment(run_every='2s' if auto_refresh else None)
def render_dashboard():

    try:
        response = requests.get(
            'http://127.0.0.1:8000/telemetria',
            timeout=2
        )

        df = pd.DataFrame(response.json())

    except:
        df = pd.DataFrame()

    df = limpiar_datos_gps(df)

    if df.empty:
        st.warning('Esperando telemetría...')
        return

    df['estado_ruta'] = df.apply(calcular_estado_salud, axis=1)

    st.markdown('### 📊 Estado Metropolitano')

    c1, c2, c3, c4 = st.columns(4)

    c1.metric('🚌 Flota Activa', len(df))
    c2.metric('👥 Pasajeros', int(df['pasajeros'].sum()))
    c3.metric('⚡ Velocidad Promedio', f"{df['vel'].mean():.1f} km/h")
    c4.metric('🔋 Energía Promedio', f"{df['bateria_gasolina'].mean():.1f}%")

    izquierda, derecha = st.columns([2.2, 1])

    with izquierda:

        rutas_df = pd.DataFrame([
            {
                'path': [[p[0], p[1]] for p in ruta]
            }
            for ruta in RUTAS_METRO
        ])

        layer_rutas = pdk.Layer(
            'PathLayer',
            rutas_df,
            get_path='path',
            get_width=6,
            get_color=[0, 180, 255]
        )

        layer_hex = pdk.Layer(
            'HexagonLayer',
            df,
            get_position=['lon', 'lat'],
            radius=180,
            elevation_scale=8,
            extruded=True,
            pickable=True
        )

        layer_buses = pdk.Layer(
            'ScatterplotLayer',
            df,
            get_position=['lon', 'lat'],
            get_radius=60,
            get_fill_color=[0,255,180,220],
            pickable=True,
            transitions={
                'getPosition': {
                    'type': 'spring',
                    'stiffness': 0.03,
                    'damping': 0.4
                }
            }
        )

        st.pydeck_chart(
            pdk.Deck(
                map_style='dark',
                map_provider='carto',
                initial_view_state=pdk.ViewState(
                    latitude=4.8135,
                    longitude=-75.6942,
                    zoom=11,
                    pitch=55
                ),
                layers=[
                    layer_rutas,
                    layer_hex,
                    layer_buses
                ],
                tooltip={
                    'text': 'Bus {vehiculo_id}\nPasajeros {pasajeros}\nVel {vel}'
                }
            )
        )

    with derecha:

        st.markdown('### 🚦 Salud Operativa')

        salud = df['estado_ruta'].value_counts()

        st.bar_chart(salud)

        st.markdown('### 🔋 Energía por Motor')

        energia = (
            df.groupby('tipo_motor')
            ['bateria_gasolina']
            .mean()
        )

        st.bar_chart(energia)

    st.divider()

    t1, t2 = st.columns(2)

    with t1:
        st.markdown('### 🎫 Ocupación en Tiempo Real')

        st.dataframe(
            df[[
                'vehiculo_id',
                'tipo_motor',
                'pasajeros',
                'vel',
                'estado_ruta'
            ]],
            use_container_width=True,
            hide_index=True
        )

    with t2:

        st.markdown('### 🚫 Pasajeros Bloqueados')

        try:
            r = requests.get(
                'http://127.0.0.1:8000/pasajeros/bloqueados',
                timeout=1
            )

            st.dataframe(
                pd.DataFrame(r.json()),
                use_container_width=True,
                hide_index=True
            )

        except:
            st.warning('Sin conexión API')

render_dashboard()
