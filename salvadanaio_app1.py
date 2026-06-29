import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

# ============================================================================
# PAGE CONFIGURATION & THEME
# ============================================================================

st.set_page_config(
    page_title="Il Mio Salvadanaio",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS per estetica FinTech e spaziazioni
st.markdown("""
<style>
    :root {
        --primary-color: #1f77b4;
        --success-color: #2ca02c;
        --danger-color: #d62728;
        --warning-color: #ff7f0e;
        --neutral-light: #f8f9fa;
        --neutral-dark: #1e1e1e;
        --border-color: #e0e0e0;
    }
    
    [data-testid="metric-container"] {
        background-color: #f8f9fa;
        border-radius: 12px;
        padding: 1.25rem;
        border-left: 4px solid #1f77b4;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
    }
    
    .stForm {
        background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%);
        border-radius: 12px;
        border: 1px solid #e0e0e0;
        padding: 2rem;
        box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
    }
    
    .streamlit-expanderHeader {
        background-color: #f8f9fa;
        border-radius: 8px;
        border: 1px solid #e0e0e0;
    }
    
    .stTabs [data-baseweb="tab-list"] button {
        border-radius: 8px 8px 0 0;
        font-weight: 500;
    }
    
    [data-testid="stDataFrame"] {
        border-radius: 8px;
        overflow: hidden;
    }
    
    h1, h2, h3 {
        color: #1e1e1e;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# CONSTANTS & CONFIGURATION
# ============================================================================

COLONNE_BASE = ["Data", "Mese", "Guadagno", "Spese_Generiche", "Diesel"]
COLONNE_NUMERICHE = ["Guadagno", "Spese_Generiche", "Diesel"]

COLOR_GUADAGNO = "#2ca02c"
COLOR_SPESE = "#d62728"
COLOR_DIESEL = "#ff7f0e"
COLOR_SALDO = "#1f77b4"

# ============================================================================
# GOOGLE SHEETS CONNECTION
# ============================================================================

@st.cache_resource(ttl=3600)
def init_connection():
    try:
        creds_dict = st.secrets["gcp_service_account"]
    except KeyError:
        st.error("⚠️ Credenziali 'gcp_service_account' non trovate nei secrets.")
        return None

    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
    except Exception as e:
        st.error(f"⚠️ Errore nell'autenticazione: {e}")
        return None

    try:
        url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        return client.open_by_url(url).sheet1
    except Exception as e:
        st.error(f"Errore di connessione al Cloud: {e}")
        return None

sheet = init_connection()

def carica_dati():
    if not sheet:
        return pd.DataFrame(columns=COLONNE_BASE)

    try:
        records = sheet.get_all_records()
    except Exception as e:
        st.error(f"⚠️ Errore caricamento dati: {e}")
        return pd.DataFrame(columns=COLONNE_BASE)

    df = pd.DataFrame(records) if records else pd.DataFrame(columns=COLONNE_BASE)

    for col in COLONNE_BASE:
        if col not in df.columns:
            df[col] = 0.0 if col in COLONNE_NUMERICHE else ""

    for col in COLONNE_NUMERICHE:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    df["Data"] = df["Data"].astype(str)
    df["Mese"] = df["Mese"].astype(str)
    return df

def trova_numero_riga(data_str):
    if not sheet:
        return None
    try:
        cella = sheet.find(data_str, in_column=1)
        return cella.row if cella else None
    except gspread.exceptions.CellNotFound:
        return None
    except Exception:
        return None

df = carica_dati()

# ============================================================================
# HEADER SECTION
# ============================================================================

col_header_left, col_header_right = st.columns([4, 1])

with col_header_left:
    st.markdown("""
    <h1 style="margin: 0; color: #1e1e1e; font-size: 2.5rem;">💰 Il Mio Salvadanaio</h1>
    <p style="margin: 0.5rem 0 0 0; color: #666; font-size: 0.95rem;">Gestisci guadagni, spese e analizza il tuo patrimonio</p>
    """, unsafe_allow_html=True)

with col_header_right:
    st.markdown(f"""
    <div style="text-align: right; padding-top: 0.5rem;">
        <p style="color: #999; font-size: 0.85rem; margin: 0;">Ultimo aggiornamento<br/>
            <strong style="color: #1f77b4; font-size: 0.9rem;">{datetime.now().strftime('%d/%m/%Y %H:%M')}</strong>
        </p>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# ============================================================================
# TAB-BASED LAYOUT
# ============================================================================

tab_dashboard, tab_registra, tab_storico = st.tabs([
    "📊 Dashboard Principale",
    "📝 Registra Nuovo / Modifica",
    "📋 Storico Completo"
])

# ============================================================================
# TAB 1: DASHBOARD PRINCIPALE
# ============================================================================
with tab_dashboard:
    df_clean = df[(df["Data"] != "") & (df["Data"] != "0")].copy()
    
    if not df_clean.empty:
        resoconto_mensile = (
            df_clean.groupby("Mese")
            .agg({"Guadagno": "sum", "Spese_Generiche": "sum", "Diesel": "sum"})
            .reset_index()
        )
        resoconto_mensile["Spese Totali"] = resoconto_mensile["Spese_Generiche"] + resoconto_mensile["Diesel"]
        resoconto_mensile["Utile Netto"] = resoconto_mensile["Guadagno"] - resoconto_mensile["Spese Totali"]
        
        st.markdown("### 🎯 Riepilogo Globale")
        totale_guadagni = resoconto_mensile['Guadagno'].sum()
        totale_spese = resoconto_mensile['Spese Totali'].sum()
        saldo_totale = resoconto_mensile["Utile Netto"].sum()
        
        kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)
        with kpi_col1:
            st.metric("📈 Entrate Totali", f"{totale_guadagni:,.2f} €")
        with kpi_col2:
            st.metric("📉 Spese Totali", f"{totale_spese:,.2f} €")
        with kpi_col3:
            st.metric("⚖️ Utile Netto", f"{saldo_totale:,.2f} €", delta_color="normal" if saldo_totale >= 0 else "inverse")
        with kpi_col4:
            rapporto_spesa = (totale_spese / totale_guadagni * 100) if totale_guadagni > 0 else 0
            st.metric("💸 Rapporto Spesa", f"{rapporto_spesa:.1f} %")
        
        st.markdown("### 📈 Andamento del Saldo Accumulato")
        df_storico = df_clean.sort_values(by="Data").copy()
        df_storico["Utile_Giorno"] = df_storico["Guadagno"] - (df_storico["Spese_Generiche"] + df_storico["Diesel"])
        df_storico["Saldo Accumulato (€)"] = df_storico["Utile_Giorno"].cumsum()
        
        fig_linea = px.line(df_storico, x="Data", y="Saldo Accumulato (€)", markers=True, template="plotly_white")
        fig_linea.update_traces(line=dict(width=3, color=COLOR_SALDO))
        st.plotly_chart(fig_linea, use_container_width=True)
        
        st.markdown("### 📅 Dettaglio Mensile")
        for idx, (_, row) in enumerate(resoconto_mensile.iloc[::-1].iterrows()):
            mese_corrente = row["Mese"]
            utile_mese = row['Utile Netto']
            colore_utile = "🟢" if utile_mese >= 0 else "🔴"
            
            with st.expander(f"**{mese_corrente}** • Netto: {colore_utile} €{utile_mese:,.2f}", expanded=(idx == 0)):
                col_metrics, col_chart = st.columns([1, 1])
                with col_metrics:
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Entrate", f"{row['Guadagno']:,.2f} €")
                    m2.metric("Uscite", f"{row['Spese Totali']:,.2f} €")
                    m3.metric("Netto", f"{utile_mese:,.2f} €")
                    
                    dettaglio_mese = pd.DataFrame({
                        "Categoria": ["Spese Generiche", "Diesel"],
                        "Importo": [row["Spese_Generiche"], row["Diesel"]],
                    })
                    st.dataframe(dettaglio_mese, use_container_width=True, hide_index=True)
                with col_chart:
                    if row["Spese Totali"] > 0:
                        fig_pie = px.pie(dettaglio_mese, values="Importo", names="Categoria", color_discrete_sequence=[COLOR_SPESE, COLOR_DIESEL], hole=0.3)
                        fig_pie.update_layout(margin=dict(t=0,b=0,l=0,r=0), height=200)
                        st.plotly_chart(fig_pie, use_container_width=True)
                    else:
                        st.info("Nessuna spesa da visualizzare.")
    else:
        st.info("Nessun dato registrato nel Cloud.")

# ============================================================================
# TAB 2: REGISTRA NUOVO / MODIFICA
# ============================================================================
with tab_registra:
    modalita_modifica = "data_da_modificare" in st.session_state
    
    if modalita_modifica:
        st.warning(f"🔄 Modalità Modifica attiva per la data: **{st.session_state['data_da_modificare']}**")
        riga_vecchia = df[df["Data"] == st.session_state["data_da_modificare"]]
        if not riga_vecchia.empty:
            data_default = datetime.strptime(st.session_state["data_da_modificare"], "%Y-%m-%d")
            val_guadagno = float(riga_vecchia.iloc[0]["Guadagno"])
            val_spese = float(riga_vecchia.iloc[0]["Spese_Generiche"])
            val_diesel = float(riga_vecchia.iloc[0]["Diesel"])
        else:
            modalita_modifica = False
    else:
        data_default = datetime.today()
        val_guadagno, val_spese, val_diesel = 0.0, 0.0, 0.0

    st.markdown("### ✍️ Inserisci o Modifica i dati di una giornata")
    
    with st.form("inserimento_giornaliero", clear_on_submit=True):
        col_data, col_guadagno, col_spese, col_diesel = st.columns(4)
        
        with col_data:
            if modalita_modifica:
                st.write(f"**Data in modifica:** {st.session_state['data_da_modificare']}")
                data_inserimento = data_default
            else:
                data_inserimento = st.date_input("Data", data_default)
                
        with col_guadagno:
            guadagno = st.number_input("Guadagno (€)", min_value=0.0, step=10.0, value=val_guadagno)
        with col_spese:
            spese_gen = st.number_input("Spese generiche (€)", min_value=0.0, step=5.0, value=val_spese)
        with col_diesel:
            diesel = st.number_input("Spesa Diesel (€)", min_value=0.0, step=5.0, value=val_diesel)
        
        col_btn1, col_btn2 = st.columns([1, 5])
        with col_btn1:
            submit = st.form_submit_button("Salva" if not modalita_modifica else "Aggiorna")
        
        if modalita_modifica:
            with col_btn2:
                if st.form_submit_button("Annulla Modifica"):
                    del st.session_state["data_da_modificare"]
                    st.rerun()

    if submit and sheet:
        data_str = data_inserimento.strftime("%Y-%m-%d")
        mese_str = data_inserimento.strftime("%Y-%m")
        nuova_riga = [data_str, mese_str, guadagno, spese_gen, diesel]
        
        riga_esistente = trova_numero_riga(data_str)
        
        if riga_esistente:
            # Sovrascrive SOLO la riga specifica (più sicuro, nessun rischio di svuotare il foglio)
            sheet.update(range_name=f"A{riga_esistente}:E{riga_esistente}", values=[nuova_riga])
            st.toast("Dati aggiornati con successo! 🔄")
        else:
            sheet.append_row(nuova_riga)
            st.toast("Nuovi dati salvati con successo! 💰")
            
        if "data_da_modificare" in st.session_state:
            del st.session_state["data_da_modificare"]
            
        st.rerun()

# ============================================================================
# TAB 3: STORICO COMPLETO & PANNELLO DI CONTROLLO
# ============================================================================
with tab_storico:
    st.markdown("### 📋 Registro Storico dei Dati")
    df_clean = df[(df["Data"] != "") & (df["Data"] != "0")].copy()
    
    if not df_clean.empty:
        st.dataframe(
            df_clean.sort_values(by="Data", ascending=False),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Data": st.column_config.TextColumn("Data"),
                "Mese": st.column_config.TextColumn("Mese"),
                "Guadagno": st.column_config.NumberColumn("Guadagno (€)", format="%.2f €"),
                "Spese_Generiche": st.column_config.NumberColumn("Spese Generiche (€)", format="%.2f €"),
                "Diesel": st.column_config.NumberColumn("Diesel (€)", format="%.2f €")
            }
        )
        
        st.markdown("---")
        st.markdown("### 🛠️ Pannello di Controllo Gestione")
        col_mod, col_canc = st.columns(2)
        
        with col_mod:
            data_mod = st.selectbox("Seleziona data da MODIFICARE:", options=sorted(df_clean["Data"].unique(), reverse=True), key="sb_mod")
            if st.button("Carica nel Form di Modifica", type="secondary"):
                st.session_state["data_da_modificare"] = data_mod
                st.toast("Caricato! Vai al tab 'Registra Nuovo / Modifica'")
                
        with col_canc:
            data_canc = st.selectbox("Seleziona data da ELIMINARE:", options=sorted(df_clean["Data"].unique(), reverse=True), key="sb_canc")
            conferma = st.checkbox(f"Confermo di voler eliminare la giornata del {data_canc}", key="conf_del")
            if st.button("Elimina Definitivamente", type="primary", disabled=not conferma):
                riga_da_cancellare = trova_numero_riga(data_canc)
                if riga_da_cancellare:
                    sheet.delete_rows(riga_da_cancellare)
                    st.success(f"Giornata del {data_canc} eliminata dal cloud!")
                    st.rerun()
                else:
                    st.error("Errore nel trovare la riga da cancellare.")
    else:
        st.info("Nessun dato presente nello storico.")
