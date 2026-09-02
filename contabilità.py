import streamlit as st
st.set_page_config(layout="wide")
import requests
from datetime import datetime, date
import pandas as pd
import os
import folium
from streamlit_folium import st_folium
import plotly.graph_objects as go
import base64

# --- 0. CONTROLLO ACCESSO PROPRIETARIO ---
is_proprietario = (st.session_state.get("ruolo_corrente") == "Proprietario")

if not is_proprietario:
    st.error("🚨 Accesso Negato: questa sezione è riservata esclusivamente al proprietario.")
    st.info("Torna alla pagina principale del Diario Alimentare ed effettua il login con le credenziali da amministratore.")
    st.stop()

# --- Configurazione ---
st.title("🚴 Gestione Uscite da Intervals.icu")

try:
    API_KEY = st.secrets["intervals"]["api_key"]
    ATHLETE_ID = st.secrets["intervals"]["athlete_id"]
except Exception as e:
    st.error("Errore: Configura le credenziali di Intervals nei secrets.")
    st.stop()

def timedelta_to_str(seconds):
    if not seconds:
        return "00:00:00"
    ore = int(seconds // 3600)
    minuti = int((seconds % 3600) // 60)
    secondi = int(seconds % 60)
    return f"{ore:02d}:{minuti:02d}:{secondi:02d}"

def safe_int(val):
    try:
        if val is None or val == "":
            return None
        return int(float(val))
    except (ValueError, TypeError):
        return None

# --- 1. STATISTICHE DINAMICHE DIRETTAMENTE DA INTERVALS (Dal 15/11/2025) ---
with st.spinner("Sincronizzazione dati da Intervals.icu in corso..."):
    url_global = f"https://intervals.icu/api/v1/athlete/{ATHLETE_ID}/activities"
    params_global = {
        "oldest": "2025-11-15",
        "newest": date.today().strftime("%Y-%m-%d"),
        "iw": True
    }
    auth_global = ("API_KEY", API_KEY.strip())
    
    resp_global = requests.get(url_global, auth=auth_global, params=params_global)

if resp_global.status_code == 200:
    activities_net = resp_global.json()
    
    if activities_net:
        df_activities = pd.DataFrame(activities_net)
        
        tot_km = round(df_activities.get("distance", pd.Series([0])).fillna(0).sum() / 1000.0, 2)
        tot_dislivello = int(df_activities.get("total_elevation_gain", pd.Series([0])).fillna(0).sum())
        
        # Calcolo delle ore totali in sella (da moving_time in secondi)
        tot_secondi_sella = df_activities.get("moving_time", pd.Series([0])).fillna(0).sum()
        ore_totali = int(tot_secondi_sella // 3600)
        minuti_totali = int((tot_secondi_sella % 3600) // 60)
        stringa_ore_sella = f"{ore_totali}h {minuti_totali:02d}m"
        
        st.markdown("---")
        st.subheader("📊 Statistiche Dinamiche e Riepilogo (TCR - Dal 15/11/2025)")
        
        col_m1, col_m2, col_m3, col_img = st.columns([2, 2, 2, 3])
        
        with col_m1:
            st.metric("Km Totali (Raccolta)", f"{tot_km:,.2f} km")
        with col_m2:
            st.metric("D+ Totale (Raccolta)", f"{tot_dislivello:,} m")
        with col_m3:
            st.metric("Ore in sella", stringa_ore_sella)
        with col_img:
            st.subheader("TCR Advanced Pro 0")
            try:
                cartella_script = os.path.dirname(__file__)
                percorso_foto = os.path.join(cartella_script, "TCR.png")
                st.image(percorso_foto, use_container_width=True)
            except Exception:
                st.warning("Immagine TCR.png non trovata.")
        
        st.markdown("---")
    else:
        st.info("Nessuna attività trovata a partire dal 15/11/2025.")
else:
    st.error(f"Errore di connessione a Intervals.icu: {resp_global.status_code}")

# --- 2. ESPLORATORE STORICO ON-DEMAND DA INTERVALS (Persistenza su File per Riavvii) ---
FILE_DATA_INIZIO = "ultima_data_inizio.txt"
FILE_DATA_FINE = "ultima_data_fine.txt"

def carica_data_salvata(file_path, default_val):
    if os.path.exists(file_path):
        try:
            with open(file_path, "r") as f:
                val = f.read().strip()
                return datetime.strptime(val, "%Y-%m-%d").date()
        except Exception:
            pass
    return default_val

def salva_data_su_file(file_path, data_val):
    try:
        with open(file_path, "w") as f:
            f.write(data_val.strftime("%Y-%m-%d"))
    except Exception:
        pass

if "saved_start" not in st.session_state:
    st.session_state["saved_start"] = carica_data_salvata(FILE_DATA_INIZIO, date(2026, 1, 1))

if "saved_end" not in st.session_state:
    st.session_state["saved_end"] = carica_data_salvata(FILE_DATA_FINE, date.today())

with st.expander("🔍 Esplora Archivio Storico da Intervals (Range Personalizzato e Filtri)", expanded=False):
    st.write("Seleziona un periodo, filtra per data specifica o cerca per nome dell'uscita all'interno del flusso di Intervals.")
    
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        data_inizio_custom = st.date_input("Data Inizio Range", value=st.session_state["saved_start"], key="widget_start")
    with col_c2:
        data_fine_custom = st.date_input("Data Fine Range", value=st.session_state["saved_end"], key="widget_end")
        
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        filtro_nome = st.text_input("Filtra per Nome Uscita (opzionale):", value="", placeholder="Es. Giro Samu, Salita...")
    with col_f2:
        attiva_data_singola = st.checkbox("Filtra per una data singola specifica")
        
    data_singola_specifica = None
    if attiva_data_singola:
        data_singola_specifica = st.date_input("Seleziona Data Specifica", value=date.today(), key="widget_single_date")

    if st.button("🚀 Estrai Dati dal Flusso", key="btn_calcola_custom"):
        st.session_state["saved_start"] = data_inizio_custom
        st.session_state["saved_end"] = data_fine_custom
        salva_data_su_file(FILE_DATA_INIZIO, data_inizio_custom)
        salva_data_su_file(FILE_DATA_FINE, data_fine_custom)
        
        with st.spinner("Interrogazione in corso..."):
            if attiva_data_singola and data_singola_specifica:
                oldest_param = data_singola_specifica.strftime("%Y-%m-%d")
                newest_param = data_singola_specifica.strftime("%Y-%m-%d")
            else:
                oldest_param = data_inizio_custom.strftime("%Y-%m-%d")
                newest_param = data_fine_custom.strftime("%Y-%m-%d")

            url_custom = f"https://intervals.icu/api/v1/athlete/{ATHLETE_ID}/activities"
            params_custom = {
                "oldest": oldest_param,
                "newest": newest_param,
                "iw": True
            }
            auth_custom = ("API_KEY", API_KEY.strip())
            
            resp_custom = requests.get(url_custom, auth=auth_custom, params=params_custom)
            
            if resp_custom.status_code == 200:
                attivita_ext_custom = resp_custom.json()
                if attivita_ext_custom:
                    st.session_state["custom_activities"] = attivita_ext_custom
                else:
                    st.session_state["custom_activities"] = []
                    st.info("Nessuna attività trovata in questo intervallo nel flusso di Intervals.")
            else:
                st.error(f"Errore di connessione a Intervals.icu: {resp_custom.status_code}")

    if "custom_activities" in st.session_state and st.session_state["custom_activities"]:
        attivita_da_mostrare = st.session_state["custom_activities"]
        if filtro_nome.strip():
            query_testo = filtro_nome.strip().lower()
            attivita_da_mostrare = [
                act for act in attivita_da_mostrare 
                if query_testo in act.get("name", "").lower()
            ]

        if not attivita_da_mostrare:
            st.warning("Nessuna attività corrisponde al filtro di ricerca inserito.")
        else:
            df_filtrato_vista = pd.DataFrame(attivita_da_mostrare)
            distanza_tot_km = round(df_filtrato_vista.get("distance", pd.Series([0])).fillna(0).sum() / 1000.0, 2)
            dislivello_tot_m = int(df_filtrato_vista.get("total_elevation_gain", pd.Series([0])).fillna(0).sum())
            num_uscite = len(df_filtrato_vista)
            
            st.markdown("---")
            mc1, mc2, mc3 = st.columns(3)
            mc1.metric("Km Totali Periodo", f"{distanza_tot_km:,.2f} km")
            mc2.metric("Dislivello (D+) Periodo", f"{dislivello_tot_m:,} m")
            mc3.metric("Uscite Registrate", f"{num_uscite}")
            st.markdown("---")
            
            with st.container(height=650):
                for idx, act in enumerate(attivita_da_mostrare):
                    act_id = str(act.get("id"))
                    act_title = act.get("name", "Uscita senza titolo")
                    act_date = act.get("start_date_local", "").split("T")[0]
                    act_dist = round(act.get("distance", 0) / 1000, 2)
                    act_time = timedelta_to_str(act.get("moving_time", 0))
                    act_elev = safe_int(act.get("total_elevation_gain")) or 0
                    
                    key_toggle = f"show_map_{act_id}_{idx}"
                    if key_toggle not in st.session_state:
                        st.session_state[key_toggle] = False
                        
                    key_edit = f"edit_name_{act_id}_{idx}"
                    if key_edit not in st.session_state:
                        st.session_state[key_edit] = False

                    with st.container(border=True):
                        col_info, col_btn_edit, col_btn1, col_btn2 = st.columns([2.5, 0.8, 1, 1])
                        
                        with col_info:
                            st.markdown(f"<h3 style='margin: 0; padding-bottom: 5px;'>{act_title} <span style='font-size: 1.1rem; color: #999;'>({act_date})</span></h3>", unsafe_allow_html=True)
                            st.markdown(f"<p style='font-size: 1.2rem; margin: 0;'>Distanza: <b>{act_dist} km</b> &nbsp;|&nbsp; D+: <b>{act_elev} m</b> &nbsp;|&nbsp; Tempo: <b>{act_time}</b></p>", unsafe_allow_html=True)
                        
                        with col_btn_edit:
                            st.write("")
                            edit_label = "✏️ Chiudi" if st.session_state[key_edit] else "✏️ Modifica Nome"
                            if st.button(edit_label, key=f"btn_edit_{act_id}_{idx}", use_container_width=True):
                                st.session_state[key_edit] = not st.session_state[key_edit]
                                st.rerun()

                        with col_btn1:
                            st.write("") 
                            btn_label = "🗺️ Nascondi Mappa" if st.session_state[key_toggle] else "🗺️ Anteprima Mappa"
                            if st.button(btn_label, key=f"btn_preview_{act_id}_{idx}", use_container_width=True):
                                st.session_state[key_toggle] = not st.session_state[key_toggle]
                                st.rerun()
                                
                        with col_btn2:
                            st.write("") 
                            if st.button("🔍 Pagina Dedicata", key=f"btn_custom_{act_id}_{idx}", use_container_width=True):
                                st.session_state["selected_activity_id"] = act_id
                                st.session_state["selected_activity_title"] = act_title
                                st.session_state["selected_activity_date"] = act_date
                                st.switch_page("pages/visualizza_mappa.py")

                        if st.session_state[key_edit]:
                            st.markdown("---")
                            col_input_name, col_save_name = st.columns([3, 1])
                            with col_input_name:
                                nuovo_nome = st.text_input("Nuovo nome attività", value=act_title, key=f"input_new_name_{act_id}_{idx}", label_visibility="collapsed")
                            with col_save_name:
                                if st.button("💾 Salva Nome", key=f"btn_save_name_{act_id}_{idx}", use_container_width=True):
                                    if nuovo_nome.strip() and nuovo_nome != act_title:
                                        auth_update = ("API_KEY", API_KEY.strip())
                                        payload = {"name": nuovo_nome.strip()}
                                        
                                        clean_id = ''.join(c for c in act_id if c.isdigit())
                                        url_update = f"https://intervals.icu/api/v1/activity/{act_id}"
                                        
                                        try:
                                            resp_up = requests.put(url_update, auth=auth_update, json=payload)
                                            if resp_up.status_code == 404 and act_id != clean_id:
                                                url_update = f"https://intervals.icu/api/v1/activity/{clean_id}"
                                                resp_up = requests.put(url_update, auth=auth_update, json=payload)
                                                
                                            if resp_up.status_code == 200:
                                                act["name"] = nuovo_nome.strip()
                                                st.session_state[key_edit] = False
                                                st.success("Nome aggiornato con successo su Intervals!")
                                                st.rerun()
                                            else:
                                                st.error(f"Errore API Intervals: {resp_up.status_code}")
                                        except Exception as e:
                                            st.error(f"Errore di connessione: {e}")
                                    else:
                                        st.warning("Inserisci un nome valido o differente.")

                        if st.session_state[key_toggle]:
                            st.markdown("---")
                            
                            clean_id = ''.join(c for c in act_id if c.isdigit())
                            target_url = f"https://intervals.icu/api/v1/activity/{clean_id}/streams"
                            auth_streams = ("API_KEY", API_KEY.strip())
                            
                            with st.spinner("Caricamento tracciato in corso..."):
                                try:
                                    resp_streams = requests.get(target_url, auth=auth_streams)
                                    if resp_streams.status_code == 404 and act_id != clean_id:
                                        target_url = f"https://intervals.icu/api/v1/activity/{act_id}/streams"
                                        resp_streams = requests.get(target_url, auth=auth_streams)
                                        
                                    if resp_streams.status_code == 200:
                                        data = resp_streams.json()
                                        lats, lons = [], []
                                        
                                        if isinstance(data, list):
                                            for stream in data:
                                                if isinstance(stream, dict):
                                                    stype = stream.get("type")
                                                    if stype in ["latlng", "lating"]:
                                                        lat_data = stream.get("data", [])
                                                        lon_data = stream.get("data2", [])
                                                        
                                                        if isinstance(lat_data, list) and isinstance(lon_data, list) and len(lat_data) == len(lon_data) and len(lat_data) > 0:
                                                            for lat, lon in zip(lat_data, lon_data):
                                                                if lat is not None and lon is not None:
                                                                    lats.append(float(lat))
                                                                    lons.append(float(lon))
                                                        elif isinstance(lat_data, list) and len(lat_data) > 0:
                                                            for pt in lat_data:
                                                                if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                                                                    if pt[0] is not None and pt[1] is not None:
                                                                        lats.append(float(pt[0]))
                                                                        lons.append(float(pt[1]))
                                                                        
                                        if lats and lons:
                                            c_map_title, c_map_style = st.columns([4, 2])
                                            with c_map_title:
                                                st.markdown("#### 🗺️ Percorso Attività")
                                            with c_map_style:
                                                stile_mappa_prev = st.selectbox(
                                                    "Stile Mappa",
                                                    ["Stradale (OpenStreetMap)", "Satellite (ArcGIS)"],
                                                    key=f"style_{act_id}_{idx}",
                                                    label_visibility="collapsed"
                                                )
                                            
                                            if "Satellite" in stile_mappa_prev:
                                                basemap_style = "white-bg"
                                                tile_source = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
                                                labels_source = "https://services.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}"
                                            else:
                                                basemap_style = "open-street-map"
                                                tile_source = None
                                                labels_source = None

                                            fig = go.Figure()
                                            fig.add_trace(go.Scattermap(
                                                lat=lats, lon=lons, mode='lines',
                                                line=dict(width=4, color='dodgerblue'), name='Tracciato'
                                            ))
                                            fig.add_trace(go.Scattermap(
                                                lat=[lats[0], lats[-1]], lon=[lons[0], lons[-1]], mode='markers',
                                                marker=dict(size=10, color=['green', 'red']), text=['Partenza', 'Arrivo'], name='Marker'
                                            ))
                                            
                                            map_config = dict(
                                                style=basemap_style,
                                                center=dict(lat=sum(lats)/len(lats), lon=sum(lons)/len(lons)),
                                                zoom=11
                                            )

                                            layers_list = []
                                            if tile_source:
                                                layers_list.append({
                                                    "sourcetype": "raster",
                                                    "source": [tile_source],
                                                    "below": "traces"
                                                })
                                            if labels_source:
                                                layers_list.append({
                                                    "sourcetype": "raster",
                                                    "source": [labels_source],
                                                    "below": "traces"
                                                })
                                                
                                            if layers_list:
                                                map_config["layers"] = layers_list

                                            fig.update_layout(
                                                map=map_config,
                                                margin=dict(l=0, r=0, t=0, b=0),
                                                height=450,
                                                showlegend=False
                                            )
                                            
                                            st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': True, 'displaylogo': False})
                                            
                                            linee = [
                                                '<?xml version="1.0" encoding="UTF-8"?>',
                                                '<gpx version="1.1" creator="Streamlit App" xmlns="http://www.topografix.com/GPX/1/1">',
                                                '  <trk>',
                                                f'    <name>{act_title}</name>',
                                                '    <trkseg>'
                                            ]
                                            for lat, lon in zip(lats, lons):
                                                linee.append(f'      <trkpt lat="{lat}" lon="{lon}"></trkpt>')
                                            linee.extend([
                                                '    </trkseg>',
                                                '  </trk>',
                                                '</gpx>'
                                            ])
                                            contenuto_gpx = "\n".join(linee)
                                            nome_file = "".join(c for c in act_title if c.isalnum() or c in (' ', '_', '-')).strip().replace(' ', '_')
                                            if not nome_file:
                                                nome_file = "tracciato"

                                            b64 = base64.b64encode(contenuto_gpx.encode()).decode()
                                            href = f'<a href="data:application/gpx+xml;base64,{b64}" download="{nome_file}.gpx" style="text-decoration: none;"><div style="background-color: #ff4b4b; color: white; padding: 0.5rem 1rem; border-radius: 0.5rem; text-align: center; font-weight: 600; margin-top: 0.5rem; margin-bottom: 0.5rem;">📥 Scarica Tracciato GPX</div></a>'
                                            st.markdown(href, unsafe_allow_html=True)
                                        else:
                                            st.warning("Nessun punto di coordinate valido trovato in questa attività.")
                                    else:
                                        st.error(f"Errore nel recupero flussi da Intervals (Status: {resp_streams.status_code})")
                                except Exception as e:
                                    st.error(f"Errore durante il caricamento della mappa: {e}")

# --- 3. CONTENITORE GRAFICI INTERATTIVI E DETTAGLIO USCITE ---
st.markdown("---")

FILE_GRAFICO_INIZIO = "grafico_data_inizio.txt"
FILE_GRAFICO_FINE = "grafico_data_fine.txt"

if "grafico_start_val" not in st.session_state:
    st.session_state["grafico_start_val"] = carica_data_salvata(FILE_GRAFICO_INIZIO, date(2026, 1, 1))

if "grafico_end_val" not in st.session_state:
    st.session_state["grafico_end_val"] = carica_data_salvata(FILE_GRAFICO_FINE, date.today())

with st.expander("📈 Analisi Grafica e Dettaglio Uscite per Metrica", expanded=False):
    st.write("Fissa il range temporale di ricerca, il livello di aggregazione (Settimane/Mesi/Anni) e seleziona il parametro da analizzare.")
    
    col_r1, col_r2, col_r3, col_r4 = st.columns([2, 2, 2, 2])
    with col_r1:
        range_inizio = st.date_input("Inizio Range Grafico", value=st.session_state["grafico_start_val"], key="grafico_start_input")
    with col_r2:
        range_fine = st.date_input("Fine Range Grafico", value=st.session_state["grafico_end_val"], key="grafico_end_input")
    with col_r3:
        tipo_aggregazione = st.selectbox(
            "Raggruppa per",
            ["Giornaliero", "Settimanale", "Mensile", "Annuale"],
            key="selettore_aggregazione"
        )
    with col_r4:
        scelta_metrica = st.selectbox(
            "Seleziona Dato Grafico",
            ["Km", "D+", "Ore in sella"],
            key="selettore_metrica_grafico"
        )

    if range_inizio != st.session_state["grafico_start_val"] or range_fine != st.session_state["grafico_end_val"]:
        st.session_state["grafico_start_val"] = range_inizio
        st.session_state["grafico_end_val"] = range_fine
        salva_data_su_file(FILE_GRAFICO_INIZIO, range_inizio)
        salva_data_su_file(FILE_GRAFICO_FINE, range_fine)

    url_grafico = f"https://intervals.icu/api/v1/athlete/{ATHLETE_ID}/activities"
    params_grafico = {
        "oldest": range_inizio.strftime("%Y-%m-%d"),
        "newest": range_fine.strftime("%Y-%m-%d"),
        "iw": True
    }
    resp_grafico = requests.get(url_grafico, auth=("API_KEY", API_KEY.strip()), params=params_grafico)

    if resp_grafico.status_code == 200:
        dati_raw_grafico = resp_grafico.json()
        if dati_raw_grafico:
            df_g = pd.DataFrame(dati_raw_grafico)
            
            df_g['data_fmt'] = pd.to_datetime(df_g['start_date_local'])
            df_g['data_solo'] = df_g['data_fmt'].dt.date
            df_g['Km'] = df_g.get('distance', 0).fillna(0) / 1000.0
            df_g['D+'] = df_g.get('total_elevation_gain', 0).fillna(0)
            df_g['Ore in sella'] = df_g.get('moving_time', 0).fillna(0) / 3600.0
            df_g['titolo_uscita'] = df_g.get('name', 'Uscita senza nome')
            df_g['id_str'] = df_g.get('id').astype(str)

            if tipo_aggregazione == "Settimanale":
                df_g['periodo_chiave'] = df_g['data_fmt'].dt.to_period('W').dt.start_time.dt.date
                df_aggregato = df_g.groupby('periodo_chiave').agg({
                    'Km': 'sum',
                    'D+': 'sum',
                    'Ore in sella': 'sum',
                    'titolo_uscita': lambda x: f"Totale Settimanale ({len(x)} uscite)"
                }).reset_index().rename(columns={'periodo_chiave': 'asse_x'})
            elif tipo_aggregazione == "Mensile":
                df_g['periodo_chiave'] = df_g['data_fmt'].dt.to_period('M').dt.start_time.dt.date
                df_aggregato = df_g.groupby('periodo_chiave').agg({
                    'Km': 'sum',
                    'D+': 'sum',
                    'Ore in sella': 'sum',
                    'titolo_uscita': lambda x: f"Totale Mensile ({len(x)} uscite)"
                }).reset_index().rename(columns={'periodo_chiave': 'asse_x'})
            elif tipo_aggregazione == "Annuale":
                df_g['periodo_chiave'] = df_g['data_fmt'].dt.to_period('Y').dt.start_time.dt.date
                df_aggregato = df_g.groupby('periodo_chiave').agg({
                    'Km': 'sum',
                    'D+': 'sum',
                    'Ore in sella': 'sum',
                    'titolo_uscita': lambda x: f"Totale Annuale ({len(x)} uscite)"
                }).reset_index().rename(columns={'periodo_chiave': 'asse_x'})
            else:
                df_g['periodo_chiave'] = df_g['data_solo']
                df_aggregato = df_g.copy().rename(columns={'data_solo': 'asse_x'})

            fig_stat = go.Figure()
            
            fig_stat.add_trace(go.Bar(
                x=df_aggregato['asse_x'],
                y=df_aggregato[scelta_metrica],
                name=scelta_metrica,
                marker=dict(color='dodgerblue'),
                customdata=df_aggregato['asse_x'].astype(str).values
            ))

            fig_stat.update_layout(
                title=f"Andamento {tipo_aggregazione.lower()}: {scelta_metrica}",
                xaxis_title="Periodo",
                yaxis_title=scelta_metrica,
                margin=dict(l=20, r=20, t=40, b=20),
                height=350,
                clickmode='event+select'
            )

            event_selezionato = st.plotly_chart(fig_stat, use_container_width=True, on_select="rerun", key="chart_uscite_interattivo")

            periodo_selezionato = None
            if event_selezionato and "selection" in event_selezionato and event_selezionato["selection"]["points"]:
                punto = event_selezionato["selection"]["points"][0]
                if "customdata" in punto:
                    periodo_selezionato = punto["customdata"]

            if periodo_selezionato:
                p_date = datetime.strptime(periodo_selezionato, "%Y-%m-%d").date()
                df_filtrato_periodo = df_g[df_g['periodo_chiave'] == p_date]
            else:
                df_filtrato_periodo = df_g

            if df_filtrato_periodo.empty:
                df_filtrato_periodo = df_g

            tot_km_periodo = df_filtrato_periodo['Km'].sum()
            tot_d_periodo = df_filtrato_periodo['D+'].sum()
            tot_ore_periodo = df_filtrato_periodo['Ore in sella'].sum()
            num_uscite_periodo = int(len(df_filtrato_periodo))

            st.markdown("---")
            
            if periodo_selezionato:
                p_date_obj = datetime.strptime(periodo_selezionato, "%Y-%m-%d")
                if tipo_aggregazione == "Settimanale":
                    etichetta_periodo = f"Settimana dal {p_date_obj.strftime('%d/%m/%Y')}"
                elif tipo_aggregazione == "Mensile":
                    etichetta_periodo = f"Mese di {p_date_obj.strftime('%B %Y')}"
                elif tipo_aggregazione == "Annuale":
                    etichetta_periodo = f"Anno {p_date_obj.strftime('%Y')}"
                else:
                    etichetta_periodo = f"Giorno {p_date_obj.strftime('%d/%m/%Y')}"
                titolo_totali = f"Totale Selezionato ({etichetta_periodo})"
            else:
                titolo_totali = "Totale Intero Periodo"

            st.markdown(f"#### 📊 {titolo_totali}")
            
            # Utilizziamo 4 colonne con pesi uguali definiti esplicitamente
            col_tot1, col_tot2, col_tot3, col_tot4 = st.columns([1, 1, 1, 1])
            col_tot1.metric("Km", f"{tot_km_periodo:,.2f} km")
            col_tot2.metric("D+", f"{tot_d_periodo:,.0f} m")
            col_tot3.metric("Ore in sella", f"{timedelta_to_str(tot_ore_periodo * 3600)}")
            col_tot4.metric("Uscite", str(num_uscite_periodo))

            st.markdown("---")
            
            opzioni_tendina = {
                f"{row['data_solo']} - {row['titolo_uscita']} ({row[scelta_metrica]:.1f} {scelta_metrica})": row['id_str'] 
                for _, row in df_filtrato_periodo.sort_values('data_fmt', ascending=False).iterrows()
            }
            
            if opzioni_tendina:
                scelta_utente_tendina = st.selectbox(
                    f"Seleziona Uscita dal Periodo ({len(opzioni_tendina)} disponibili)",
                    options=list(opzioni_tendina.keys()),
                    key="select_uscita_dettaglio_grafico"
                )
                id_attivita_scelta = opzioni_tendina[scelta_utente_tendina]
            else:
                st.warning("Nessuna uscita trovata per la selezione corrente.")
                id_attivita_scelta = None
            
            if id_attivita_scelta:
                dati_uscita_corrente = df_g[df_g['id_str'] == id_attivita_scelta].iloc[0]

                col_tit_g, col_btn_edit_g = st.columns([4, 1])
                with col_tit_g:
                    st.markdown(f"#### 🚴 Dettaglio: {dati_uscita_corrente['titolo_uscita']} ({dati_uscita_corrente['data_solo']})")
                
                key_edit_g = f"edit_name_g_{id_attivita_scelta}"
                if key_edit_g not in st.session_state:
                    st.session_state[key_edit_g] = False

                with col_btn_edit_g:
                    edit_label_g = "✏️ Chiudi" if st.session_state[key_edit_g] else "✏️ Modifica Nome"
                    if st.button(edit_label_g, key=f"btn_edit_trigger_{id_attivita_scelta}", use_container_width=True):
                        st.session_state[key_edit_g] = not st.session_state[key_edit_g]
                        st.rerun()

                if st.session_state[key_edit_g]:
                    with st.container(border=True):
                        col_in_g, col_sv_g = st.columns([3, 1])
                        with col_in_g:
                            nuovo_nome_g = st.text_input("Nuovo nome attività", value=dati_uscita_corrente['titolo_uscita'], key=f"input_new_name_g_{id_attivita_scelta}", label_visibility="collapsed")
                        with col_sv_g:
                            if st.button("💾 Salva Nome", key=f"btn_save_name_g_{id_attivita_scelta}", use_container_width=True):
                                if nuovo_nome_g.strip() and nuovo_nome_g != dati_uscita_corrente['titolo_uscita']:
                                    clean_id_update = ''.join(c for c in id_attivita_scelta if c.isdigit())
                                    auth_update = ("API_KEY", API_KEY.strip())
                                    payload = {"name": nuovo_nome_g.strip()}
                                    url_update = f"https://intervals.icu/api/v1/activity/{id_attivita_scelta}"
                                    
                                    try:
                                        resp_up = requests.put(url_update, auth=auth_update, json=payload)
                                        if resp_up.status_code == 404 and id_attivita_scelta != clean_id_update:
                                            url_update = f"https://intervals.icu/api/v1/activity/{clean_id_update}"
                                            resp_up = requests.put(url_update, auth=auth_update, json=payload)
                                            
                                        if resp_up.status_code == 200:
                                            df_g.loc[df_g['id_str'] == id_attivita_scelta, 'titolo_uscita'] = nuovo_nome_g.strip()
                                            st.session_state[key_edit_g] = False
                                            st.success("Nome aggiornato con successo su Intervals!")
                                            st.rerun()
                                        else:
                                            st.error(f"Errore API Intervals: {resp_up.status_code}")
                                    except Exception as e:
                                        st.error(f"Errore di connessione: {e}")
                                else:
                                    st.warning("Inserisci un nome valido o differente.")

                clean_id_g = ''.join(c for c in id_attivita_scelta if c.isdigit())
                target_url_g = f"https://intervals.icu/api/v1/activity/{clean_id_g}/streams"
                
                with st.spinner("Caricamento traccia GPS in corso..."):
                    resp_str_g = requests.get(target_url_g, auth=("API_KEY", API_KEY.strip()))
                    if resp_str_g.status_code == 404 and id_attivita_scelta != clean_id_g:
                        target_url_g = f"https://intervals.icu/api/v1/activity/{id_attivita_scelta}/streams"
                        resp_str_g = requests.get(target_url_g, auth=("API_KEY", API_KEY.strip()))

                    if resp_str_g.status_code == 200:
                        stream_data_g = resp_str_g.json()
                        lats_g, lons_g = [], []
                        
                        if isinstance(stream_data_g, list):
                            for stream in stream_data_g:
                                if isinstance(stream, dict):
                                    stype = stream.get("type")
                                    if stype in ["latlng", "lating"]:
                                        lat_data = stream.get("data", [])
                                        lon_data = stream.get("data2", [])
                                        
                                        if isinstance(lat_data, list) and isinstance(lon_data, list) and len(lat_data) == len(lon_data) and len(lat_data) > 0:
                                            for lat, lon in zip(lat_data, lon_data):
                                                if lat is not None and lon is not None:
                                                    lats_g.append(float(lat))
                                                    lons_g.append(float(lon))
                                        break

                        if lats_g and lons_g and len(lats_g) > 0:
                            with st.expander("🗺️ Visualizza Mappa e Download GPX", expanded=False):
                                tipo_mappa = st.radio(
                                    "Stile Mappa",
                                    ["Standard", "Satellite"],
                                    horizontal=True,
                                    key=f"stile_mappa_{id_attivita_scelta}"
                                )

                                fig_map = go.Figure()
                                fig_map.add_trace(go.Scattermap(
                                    lat=lats_g, lon=lons_g, mode='lines',
                                    line=dict(width=4, color='dodgerblue'), name='Tracciato'
                                ))
                                fig_map.add_trace(go.Scattermap(
                                    lat=[lats_g[0], lats_g[-1]], lon=[lons_g[0], lons_g[-1]], mode='markers',
                                    marker=dict(size=10, color=['green', 'red']), text=['Partenza', 'Arrivo'], name='Marker'
                                ))
                                
                                if tipo_mappa == "Satellite":
                                    map_config = dict(
                                        style="white-bg",
                                        layers=[
                                            {
                                                "below": 'traces',
                                                "sourcetype": "raster",
                                                "source": [
                                                    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
                                                ]
                                            }
                                        ],
                                        center=dict(lat=sum(lats_g)/len(lats_g), lon=sum(lons_g)/len(lons_g)),
                                        zoom=11
                                    )
                                else:
                                    map_config = dict(
                                        style="open-street-map",
                                        center=dict(lat=sum(lats_g)/len(lats_g), lon=sum(lons_g)/len(lons_g)),
                                        zoom=11
                                    )

                                fig_map.update_layout(
                                    map=map_config,
                                    margin=dict(l=0, r=0, t=0, b=0),
                                    height=450,
                                    showlegend=False
                                )
                                
                                st.plotly_chart(fig_map, use_container_width=True, config={'scrollZoom': True, 'displaylogo': False})

                                linee_gpx = [
                                    '<?xml version="1.0" encoding="UTF-8"?>',
                                    '<gpx version="1.1" creator="Streamlit App" xmlns="http://www.topografix.com/GPX/1/1">',
                                    '  <trk>',
                                    f'    <name>{dati_uscita_corrente["titolo_uscita"]}</name>',
                                    '    <trkseg>'
                                ]
                                for lat, lon in zip(lats_g, lons_g):
                                    linee_gpx.append(f'      <trkpt lat="{lat}" lon="{lon}"></trkpt>')
                                linee_gpx.extend([
                                    '    </trkseg>',
                                    '  </trk>',
                                    '</gpx>'
                                ])
                                contenuto_gpx_uscita = "\n".join(linee_gpx)
                                nome_file_gpx = "".join(c for c in dati_uscita_corrente["titolo_uscita"] if c.isalnum() or c in (' ', '_', '-')).strip().replace(' ', '_')
                                if not nome_file_gpx:
                                    nome_file_gpx = "tracciato_uscita"

                                b64_gpx = base64.b64encode(contenuto_gpx_uscita.encode()).decode()
                                href_gpx = f'<a href="data:application/gpx+xml;base64,{b64_gpx}" download="{nome_file_gpx}.gpx" style="text-decoration: none;"><div style="background-color: #ff4b4b; color: white; padding: 0.5rem 1rem; border-radius: 0.5rem; text-align: center; font-weight: 600; margin-top: 0.5rem; margin-bottom: 0.5rem;">📥 Scarica Tracciato GPX</div></a>'
                                st.markdown(href_gpx, unsafe_allow_html=True)
                        else:
                            st.warning("⚠️ Nessuna coordinata GPS valida disponibile per questa specifica uscita su Intervals.icu.")
                    else:
                        st.error(f"Errore nel recupero flussi da Intervals (Status: {resp_str_g.status_code})")
        else:
            st.info("Nessuna attività trovata nel range temporale selezionato per il grafico.")
    else:
        st.error("Errore nel recupero dati per il grafico da Intervals.icu.")

# --- 4. SEZIONE PARAMETRI DI INTERVALS (RICERCA PER GIORNO SPECIFICO) ---
st.markdown("---")

with st.expander("🎯 Dashboard Avanzata Parametri Intervals.icu", expanded=True):
    st.write("Estrazione dei parametri per il giorno selezionato.")
    
    oggi = date.today()
    
    c1, _ = st.columns([1, 3])
    with c1:
        giorno_scelto = st.date_input("Seleziona Giorno", value=oggi, key="sec4_giorno_singolo")
    
    start_sec4 = giorno_scelto
    end_sec4 = giorno_scelto

    url_sec4 = f"https://intervals.icu/api/v1/athlete/{ATHLETE_ID}/activities"
    params_sec4 = {
        "oldest": start_sec4.strftime("%Y-%m-%d"),
        "newest": end_sec4.strftime("%Y-%m-%d"),
        "iw": True
    }
    resp_sec4 = requests.get(url_sec4, auth=("API_KEY", API_KEY.strip()), params=params_sec4)

    url_well = f"https://intervals.icu/api/v1/athlete/{ATHLETE_ID}/wellness"
    params_well = {
        "oldest": start_sec4.strftime("%Y-%m-%d"),
        "newest": end_sec4.strftime("%Y-%m-%d")
    }
    resp_well = requests.get(url_well, auth=("API_KEY", API_KEY.strip()), params=params_well)

    val_load = 0.0
    val_if = 0.0
    val_vi = 1.0
    val_eftp = 279.0
    val_ef = 0.0
    val_ctl = 0.0
    val_atl = 0.0
    np_val = 0.0
    gp_val = 0.0
    avg_hr = 0.0
    m = {}

    if resp_well.status_code == 200:
        dati_well = resp_well.json()
        if dati_well:
            df_w = pd.DataFrame(dati_well)
            if not df_w.empty and 'id' in df_w.columns:
                df_w['data_well'] = pd.to_datetime(df_w['id']).dt.date
                df_w_filtrato = df_w[df_w['data_well'] == giorno_scelto]
                if not df_w_filtrato.empty:
                    ultimo_w = df_w_filtrato.sort_values('id', ascending=False).iloc[0]
                    val_ctl = float(ultimo_w.get('ctl', 0.0) or 0.0)
                    val_atl = float(ultimo_w.get('atl', 0.0) or 0.0)

    if resp_sec4.status_code == 200:
        dati_sec4 = resp_sec4.json()
        if dati_sec4:
            df_s4 = pd.DataFrame(dati_sec4)
            if not df_s4.empty and 'start_date_local' in df_s4.columns:
                df_s4['data_attivita'] = pd.to_datetime(df_s4['start_date_local']).dt.date
                df_s4_filtrato = df_s4[df_s4['data_attivita'] == giorno_scelto]
                
                if not df_s4_filtrato.empty:
                    ultima_act = df_s4_filtrato.sort_values('start_date_local', ascending=False).iloc[0]
                    m = ultima_act.to_dict()
                    
                    act_id = m.get('id')
                    if act_id:
                        url_detail = f"https://intervals.icu/api/v1/activity/{act_id}"
                        resp_detail = requests.get(url_detail, auth=("API_KEY", API_KEY.strip()))
                        if resp_detail.status_code == 200:
                            detail_json = resp_detail.json()
                            m.update(detail_json)

                        url_streams = f"https://intervals.icu/api/v1/activity/{act_id}/streams"
                        resp_streams = requests.get(url_streams, auth=("API_KEY", API_KEY.strip()))
                        watts_stream = []
                        if resp_streams.status_code == 200:
                            streams_data = resp_streams.json()
                            if isinstance(streams_data, list):
                                for stream in streams_data:
                                    if isinstance(stream, dict) and stream.get("type") == "watts":
                                        watts_stream = stream.get("data", [])
                                        break

                    val_load = float(m.get('icu_training_load') or m.get('load') or 0.0)
                    val_eftp = float(m.get('icu_ftp') or m.get('eftp') or 279.0)
                    
                    val_ctl = float(m.get('icu_ctl') or val_ctl or 0.0)
                    val_atl = float(m.get('icu_atl') or val_atl or 0.0)

                    np_val = float(m.get('normalized_watts') or m.get('icu_normalized_watts') or m.get('np') or m.get('weighted_average_watts') or 0.0)
                    gp_val = float(m.get('average_watts') or m.get('icu_average_watts') or m.get('watts') or 0.0)
                    avg_hr = float(m.get('average_heartrate') or m.get('icu_average_heartrate') or m.get('hr') or 0.0)

                    if np_val == 0.0 and watts_stream:
                        valid_watts = [w for w in watts_stream if w is not None and w >= 0]
                        if len(valid_watts) >= 30:
                            rolling_30s = [sum(valid_watts[i:i+30])/30 for i in range(len(valid_watts)-29)]
                            np_val = float((sum([w**4 for w in rolling_30s]) / len(rolling_30s)) ** 0.25)
                        elif valid_watts:
                            np_val = float(sum(valid_watts) / len(valid_watts))

                    if np_val == 0.0 and gp_val > 0:
                        np_val = gp_val

                    if np_val > 0 and val_eftp > 0:
                        val_if = np_val / val_eftp
                    else:
                        raw_if = float(m.get('intensity_factor') or m.get('icu_intensity') or 0.0)
                        val_if = raw_if / 100.0 if raw_if > 2.0 else raw_if

                    val_vi = float(m.get('variability_index') or m.get('vi') or m.get('icu_variability_index') or 0.0)
                    if val_vi == 0.0 and np_val > 0 and gp_val > 0:
                        val_vi = np_val / gp_val
                    if val_vi == 0.0: 
                        val_vi = 1.0

                    val_ef = float(m.get('efficiency_factor') or m.get('ef') or m.get('icu_efficiency_factor') or 0.0)
                    if val_ef == 0.0 and np_val > 0 and avg_hr > 0:
                        val_ef = np_val / avg_hr

    val_tsb = val_ctl - val_atl

    st.markdown("---")

    def apply_dark_theme(fig, height=220):
        fig.update_layout(
            height=height,
            margin=dict(l=20, r=20, t=50, b=10),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='white')
        )
        return fig

    with st.container(border=True):
        st.markdown("### 1. Gestione del Carico e della Forma (Grafico 'Fitness')")
        st.caption("ℹ️ **Legenda:** Monitoraggio a lungo termine del carico di allenamento (CTL = Fitness, ATL = Fatica, TSB = Stato di Forma/Balance).")
        col_s1_1, col_s1_2, col_s1_3 = st.columns(3)
        
        with col_s1_1:
            fig_ctl = go.Figure(go.Indicator(
                mode="gauge+number", value=val_ctl, title={"text": "<b>Fitness (CTL)</b>"},
                gauge={'axis': {'range': [0, 150]}, 'bar': {'color': "royalblue"}, 'bgcolor': "rgba(0,0,0,0)"}
            ))
            st.plotly_chart(apply_dark_theme(fig_ctl), use_container_width=True, config={'displaylogo': False})
            st.markdown("<p style='text-align: center; font-size: 0.85rem; color: #aaa;'><b>CTL (Chronic Training Load):</b> Carico di allenamento cronico, ovvero la fitness aerobica di fondo sviluppata negli ultimi 42 giorni.</p>", unsafe_allow_html=True)
            
        with col_s1_2:
            fig_atl = go.Figure(go.Indicator(
                mode="gauge+number", value=val_atl, title={"text": "<b>Fatigue (ATL)</b>"},
                gauge={'axis': {'range': [0, 150]}, 'bar': {'color': "darkorange"}, 'bgcolor': "rgba(0,0,0,0)"}
            ))
            st.plotly_chart(apply_dark_theme(fig_atl), use_container_width=True, config={'displaylogo': False})
            st.markdown("<p style='text-align: center; font-size: 0.85rem; color: #aaa;'><b>ATL (Acute Training Load):</b> Carico di fatica acuto e stress muscolare accumulato negli ultimi 7 giorni.</p>", unsafe_allow_html=True)
            
        with col_s1_3:
            fig_tsb = go.Figure(go.Indicator(
                mode="gauge+number", value=val_tsb, title={"text": "<b>Form (TSB)</b>"},
                gauge={'axis': {'range': [-50, 50]}, 'bar': {'color': "forestgreen" if -30 <= val_tsb <= -10 else "crimson"}, 'bgcolor': "rgba(0,0,0,0)"}
            ))
            st.plotly_chart(apply_dark_theme(fig_tsb), use_container_width=True, config={'displaylogo': False})
            st.markdown("<p style='text-align: center; font-size: 0.85rem; color: #aaa;'><b>TSB (Training Stress Balance):</b> Stato di freschezza o affaticamento (CTL meno ATL). Valori positivi indicano riposo, negativi indicano carico.</p>", unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown("### 2. Intensità e Stress della Singola Sessione")
        st.caption("ℹ️ **Legenda:** Valutazione dello stress immediato dell'allenamento (TSS/Load), dell'Intensity Factor (IF) e della regolarità dello sforzo tramite il Variability Index (VI).")
        col_s2_1, col_s2_2, col_s2_3 = st.columns(3)
        
        with col_s2_1:
            fig_load = go.Figure(go.Indicator(
                mode="gauge+number", value=val_load, title={"text": "<b>Load / TSS Sessione</b>"},
                gauge={'axis': {'range': [0, 400]}, 'bar': {'color': "dodgerblue"}, 'bgcolor': "rgba(0,0,0,0)"}
            ))
            st.plotly_chart(apply_dark_theme(fig_load), use_container_width=True, config={'displaylogo': False})
            st.markdown("<p style='text-align: center; font-size: 0.85rem; color: #aaa;'><b>Training Stress Score (TSS):</b> Quantifica lo stress complessivo della singola sessione in base a durata e intensità rapportate alla tua FTP.</p>", unsafe_allow_html=True)

        with col_s2_2:
            fig_if = go.Figure(go.Indicator(
                mode="gauge+number", value=val_if, title={"text": "<b>Intensity Factor (IF)</b>"},
                number={'valueformat': ".2f"},
                gauge={'axis': {'range': [0, 1.3]}, 'bar': {'color': "purple"}, 'bgcolor': "rgba(0,0,0,0)"}
            ))
            st.plotly_chart(apply_dark_theme(fig_if), use_container_width=True, config={'displaylogo': False})
            st.markdown("<p style='text-align: center; font-size: 0.85rem; color: #aaa;'><b>Intensity Factor (IF):</b> Esprime quanto è stata dura l'uscita rapportando la Potenza Normalizzata (NP) alla tua soglia (FTP).</p>", unsafe_allow_html=True)

        with col_s2_3:
            fig_vi = go.Figure(go.Indicator(
                mode="gauge+number", value=val_vi, title={"text": "<b>Variability Index (VI)</b>"},
                number={'valueformat': ".2f"},
                gauge={'axis': {'range': [1.0, 1.5]}, 'bar': {'color': "teal"}, 'bgcolor': "rgba(0,0,0,0)"}
            ))
            st.plotly_chart(apply_dark_theme(fig_vi), use_container_width=True, config={'displaylogo': False})
            st.markdown("<p style='text-align: center; font-size: 0.85rem; color: #aaa;'><b>Variability Index (VI):</b> Rapporto tra Potenza Normalizzata e Potenza Media; misura la regolarità dello sforzo (1.0 indica pedalata perfettamente rotonda).</p>", unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown("### 3. Analisi della Performance e Capacità")
        st.caption("ℹ️ **Legenda:** Analisi della potenza funzionale stimata (eFTP) e dell'Efficiency Factor (EF).")
        col_s3_1, col_s3_2 = st.columns(2)
        
        with col_s3_1:
            fig_eftp = go.Figure(go.Indicator(
                mode="gauge+number", value=val_eftp, title={"text": "<b>eFTP (W)</b>"},
                gauge={'axis': {'range': [0, 400]}, 'bar': {'color': "crimson"}, 'bgcolor': "rgba(0,0,0,0)"}
            ))
            st.plotly_chart(apply_dark_theme(fig_eftp), use_container_width=True, config={'displaylogo': False})
            st.markdown("<p style='text-align: center; font-size: 0.85rem; color: #aaa;'><b>eFTP (Estimated Functional Threshold Power):</b> La stima dinamica della tua soglia di potenza funzionale calcolata sulle migliori prestazioni recenti.</p>", unsafe_allow_html=True)

        with col_s3_2:
            fig_ef = go.Figure(go.Indicator(
                mode="gauge+number", value=val_ef, title={"text": "<b>Efficiency Factor (EF)</b>"},
                number={'valueformat': ".2f"},
                gauge={'axis': {'range': [0.0, 2.5]}, 'bar': {'color': "goldenrod"}, 'bgcolor': "rgba(0,0,0,0)"}
            ))
            st.plotly_chart(apply_dark_theme(fig_ef), use_container_width=True, config={'displaylogo': False})
            st.markdown("<p style='text-align: center; font-size: 0.85rem; color: #aaa;'><b>Efficiency Factor (EF):</b> Rapporto tra Potenza Normalizzata e frequenza cardiaca media; indica l'efficienza cardiocircolatoria e aerobica.</p>", unsafe_allow_html=True)

        st.markdown("---")

        col_s3_3, col_s3_4 = st.columns(2)
        with col_s3_3:
            valore_np_display = float(np_val) if np_val else 0.0
            
            fig_np_gauge = go.Figure(go.Indicator(
                mode="gauge+number", 
                value=valore_np_display, 
                title={"text": "<b>Potenza Normalizzata (NP)</b>"},
                gauge={'axis': {'range': [0, 400]}, 'bar': {'color': "mediumorchid"}, 'bgcolor': "rgba(0,0,0,0)"}
            ))
            st.plotly_chart(apply_dark_theme(fig_np_gauge), use_container_width=True, config={'displaylogo': False})
            st.markdown("<p style='text-align: center; font-size: 0.85rem; color: #aaa;'><b>Potenza Normalizzata (NP):</b> Stima della potenza equivalente che toglie i picchi, riflettendo il costo metabolico reale dell'uscita.</p>", unsafe_allow_html=True)

        with col_s3_4:
            valore_fc_display = float(avg_hr) if avg_hr else 0.0
            
            fig_fc_gauge = go.Figure(go.Indicator(
                mode="gauge+number", 
                value=valore_fc_display, 
                title={"text": "<b>FC Media (bpm)</b>"},
                gauge={'axis': {'range': [0, 200]}, 'bar': {'color': "orangered"}, 'bgcolor': "rgba(0,0,0,0)"}
            ))
            st.plotly_chart(apply_dark_theme(fig_fc_gauge), use_container_width=True, config={'displaylogo': False})
            st.markdown("<p style='text-align: center; font-size: 0.85rem; color: #aaa;'><b>Frequenza Cardiaca Media:</b> Battito cardiaco medio registrato durante tutta la sessione di allenamento.</p>", unsafe_allow_html=True)
