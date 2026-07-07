import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from typing import Optional
import gspread
from google.oauth2.service_account import Credentials

# ============================================================================
# CONFIGURAZIONE PAGINA & TEMA FINTECH UI
# ============================================================================

st.set_page_config(
    page_title="Il Mio Salvadanaio",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# CSS Custom per un look moderno, pulito e "SaaS/FinTech"
st.markdown("""
<style>
    /* Importazione font pulito */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    html, body, [data-testid="stAppViewContainer"] {
        font-family: 'Inter', sans-serif;
        background-color: #f9fafb;
    }
    
    /* Box delle metriche (Card) elevate ed eleganti */
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border: 1px solid #f3f4f6;
        border-radius: 16px;
        padding: 20px 24px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
        transition: transform 0.2s ease;
    }
    div[data-testid="stMetric"]:hover {
        transform: translateY(-2px);
    }
    
    /* Form stile moderno */
    .stForm {
        background-color: #ffffff;
        border: 1px solid #e5e7eb !important;
        border-radius: 16px !important;
        padding: 2.5rem !important;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.05) !important;
    }
    
    /* Bottoni arrotondati premium */
    .stButton>button {
        border-radius: 10px !important;
        font-weight: 500 !important;
        padding: 0.5rem 1.5rem !important;
    }
    
    /* Tab dal look minimal */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
        background-color: #f3f4f6;
        padding: 6px;
        border-radius: 12px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px !important;
        padding: 8px 16px !important;
        background-color: transparent;
        color: #4b5563;
        font-weight: 500;
        border: none !important;
    }
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background-color: #ffffff !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        color: #111827 !important;
    }
    
    /* Contenitori expander */
    .streamlit-expanderHeader {
        background-color: #ffffff !important;
        border: 1px solid #e5e7eb !important;
        border-radius: 12px !important;
        padding: 1rem !important;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# COSTANTI CROMATICHE
# ============================================================================

COLONNE_BASE = ["Data", "Mese", "Guadagno", "Spese_Generiche", "Diesel"]
COLONNE_NUMERICHE = ["Guadagno", "Spese_Generiche", "Diesel"]

# Palette colori minimal ed eleganti
COLOR_GUADAGNO = "#10B981"  # Smeraldo
COLOR_SPESE = "#EF4444"     # Rosso Soft
COLOR_DIESEL = "#F59E0B"    # Ambra
COLOR_SALDO = "#3B82F6"     # Blu Moderno

# ============================================================================
# CONNESSIONE GOOGLE SHEETS
# ============================================================================

@st.cache_resource(ttl=3600)
def init_connection():
    """Inizializza e ritorna l'oggetto Sheet (prima pagina) o None se fallisce.

    La risorsa è messa in cache per 1 ora (ttl=3600).
    """
    try:
        creds_dict = st.secrets.get("gcp_service_account")
        if not creds_dict:
            st.warning("Credenziali GCP non configurate in `st.secrets`. Connessione disabilitata.")
            return None
        scope = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        url = st.secrets.get("connections", {}).get("gsheets", {}).get("spreadsheet")
        if not url:
            st.warning("URL del foglio di lavoro non trovato in `st.secrets['connections']`.")
            return None
        return client.open_by_url(url).sheet1
    except Exception as e:
        st.error("Errore durante la connessione a Google Sheets. Controlla le credenziali e la rete.")
        st.exception(e)
        return None

def carica_dati(sheet) -> pd.DataFrame:
    """Carica i dati dal foglio, restituisce un DataFrame con colonne garantite."""
    if not sheet:
        return pd.DataFrame(columns=COLONNE_BASE)
    try:
        records = sheet.get_all_records()
        df = pd.DataFrame(records) if records else pd.DataFrame(columns=COLONNE_BASE)
        for col in COLONNE_BASE:
            if col not in df.columns:
                df[col] = 0.0 if col in COLONNE_NUMERICHE else ""
        for col in COLONNE_NUMERICHE:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
        df["Data"] = df["Data"].astype(str)
        df["Mese"] = df["Mese"].astype(str)
        return df
    except Exception as e:
        st.error("Errore durante il caricamento dei dati dal foglio.")
        st.exception(e)
        return pd.DataFrame(columns=COLONNE_BASE)

def trova_numero_riga(data_str: str, sheet) -> Optional[int]:
    """Restituisce il numero di riga della prima occorrenza di `data_str` nella colonna A, oppure None."""
    if not sheet:
        return None
    try:
        cella = sheet.find(data_str, in_column=1)
        return cella.row if cella else None
    except Exception as e:
        st.warning(f"Impossibile cercare la riga per {data_str}: {e}")
        return None


def format_currency(value: float) -> str:
    """Formato rapido per valute in Euro (es. 1,234.56 €)."""
    try:
        return f"{value:,.2f} €"
    except Exception:
        return "0.00 €"

sheet = init_connection()
df = carica_dati(sheet)

# ============================================================================
# HEADER DESIGN
# ============================================================================

col_header_left, col_header_right = st.columns([3, 1])

with col_header_left:
    st.markdown("""
    <div style="display: flex; align-items: center; gap: 15px;">
        <span style="font-size: 3rem;">💰</span>
        <div>
            <h1 style="margin: 0; font-size: 2.2rem; font-weight: 700; color: #111827; letter-spacing: -0.05em;">Il Mio Salvadanaio</h1>
            <p style="margin: 2px 0 0 0; color: #6b7280; font-size: 1rem;">Wealth management & tracking finanziario personale</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

with col_header_right:
    st.markdown(f"""
    <div style="background-color: #ffffff; padding: 12px 18px; border-radius: 12px; border: 1px solid #e5e7eb; text-align: right; box-shadow: 0 1px 2px rgba(0,0,0,0.05);">
        <p style="color: #9ca3af; font-size: 0.75rem; text-transform: uppercase; font-weight: 600; margin: 0; letter-spacing: 0.05em;">Ultimo Sync</p>
        <p style="color: #111827; font-size: 0.95rem; font-weight: 600; margin: 2px 0 0 0;">{datetime.now().strftime('%d %b %Y • %H:%M')}</p>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br/>", unsafe_allow_html=True)

# ============================================================================
# STRUTTURA A TAB
# ============================================================================

tab_dashboard, tab_registra, tab_storico = st.tabs([
    "📊 Dashboard",
    "✨ Nuova Registrazione / Modifica",
    "🗂️ Archivio Storico"
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
        
        totale_guadagni = resoconto_mensile['Guadagno'].sum()
        totale_spese = resoconto_mensile['Spese Totali'].sum()
        saldo_totale = resoconto_mensile["Utile Netto"].sum()
        
        # --- CARD METRICHE RILEVANTI ---
        kpi_col1, kpi_col2, kpi_col3 = st.columns(3)
        with kpi_col1:
            st.metric("📈 ENTRATE TOTALI", format_currency(totale_guadagni))
        with kpi_col2:
            st.metric("📉 USCITE TOTALI", format_currency(totale_spese))
        with kpi_col3:
            st.metric(
                "💰 SALDO NETTO",
                format_currency(saldo_totale),
                delta=f"{'+' if saldo_totale >= 0 else ''}{format_currency(saldo_totale)}",
                delta_color="normal" if saldo_totale >= 0 else "inverse",
            )
        
        st.markdown("<br/>", unsafe_allow_html=True)
        
        # --- GRAFICO AD ANDAMENTO PREMIUM (AREA SFUMATA) ---
        st.markdown("### 📈 Andamento Patrimoniale")
        df_storico = df_clean.sort_values(by="Data").copy()
        df_storico["Utile_Giorno"] = df_storico["Guadagno"] - (df_storico["Spese_Generiche"] + df_storico["Diesel"])
        df_storico["Saldo Accumulato"] = df_storico["Utile_Giorno"].cumsum()
        
        fig_linea = go.Figure()
        fig_linea.add_trace(go.Scatter(
            x=df_storico["Data"], 
            y=df_storico["Saldo Accumulato"],
            mode='lines+markers',
            line=dict(color=COLOR_SALDO, width=4, shape='spline'),
            marker=dict(size=7, color="#ffffff", line=dict(color=COLOR_SALDO, width=2)),
            fill='tozeroy',
            fillcolor='rgba(59, 130, 246, 0.06)',
            name='Saldo (€)'
        ))
        fig_linea.update_layout(
            template="plotly_white",
            height=350,
            margin=dict(t=10, b=10, l=40, r=10),
            xaxis=dict(showgrid=False),
            yaxis=dict(gridcolor='#f3f4f6')
        )
        st.plotly_chart(fig_linea, use_container_width=True)
        
        # --- SEZIONE EXPANDER MESE PER MESE ---
        st.markdown("### 📅 Resoconti Mensili")
        for idx, (_, row) in enumerate(resoconto_mensile.iloc[::-1].iterrows()):
            mese_corrente = row["Mese"]
            utile_mese = row['Utile Netto']
            icona_stato = "🟢" if utile_mese >= 0 else "🔴"

            with st.expander(
                f"**{mese_corrente}** &nbsp;|&nbsp; Netto: {icona_stato} **{format_currency(utile_mese)}**",
                expanded=(idx == 0),
            ):
                col_m_left, col_m_right = st.columns([1, 1])
                with col_m_left:
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Entrate", format_currency(row['Guadagno']))
                    m2.metric("Uscite", format_currency(row['Spese Totali']))
                    m3.metric("Netto", format_currency(utile_mese))
                    
                    st.markdown("<br/>", unsafe_allow_html=True)
                    dettaglio_mese = pd.DataFrame({
                        "Categoria": ["Spese Generiche", "Diesel"],
                        "Importo": [row["Spese_Generiche"], row["Diesel"]],
                    })
                    st.dataframe(dettaglio_mese, use_container_width=True, hide_index=True)
                    
                with col_m_right:
                    if row["Spese Totali"] > 0:
                        fig_pie = px.pie(
                            dettaglio_mese, values="Importo", names="Categoria",
                            color_discrete_sequence=[COLOR_SPESE, COLOR_DIESEL], hole=0.5
                        )
                        fig_pie.update_layout(margin=dict(t=10,b=10,l=10,r=10), height=180, showlegend=True)
                        st.plotly_chart(fig_pie, use_container_width=True)
                    else:
                        st.info("Nessuna spesa da tracciare per questo mese.")
    else:
        st.info("Nessun dato registrato. Inizia inserendo una riga nel secondo Tab.")

# ============================================================================
# TAB 2: NUOVA REGISTRAZIONE / MODIFICA
# ============================================================================
with tab_registra:
    modalita_modifica = "data_da_modificare" in st.session_state
    
    if modalita_modifica:
        st.info(f"⚙️ **Modalità Modifica Attiva:** Stai modificando la data del **{st.session_state['data_da_modificare']}**")
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

    with st.form("inserimento_giornaliero", clear_on_submit=True):
        st.markdown("### 📝 Compila i dati giornalieri")
        col_data, col_guadagno, col_spese, col_diesel = st.columns(4)
        
        with col_data:
            if modalita_modifica:
                st.write(f"📅 **Data bloccata:** {st.session_state['data_da_modificare']}")
                data_inserimento = data_default
            else:
                data_inserimento = st.date_input("Data di riferimento", data_default)
                
        with col_guadagno:
            guadagno = st.number_input("Guadagno (€)", min_value=0.0, step=10.0, value=val_guadagno)
        with col_spese:
            spese_gen = st.number_input("Spese Generiche (€)", min_value=0.0, step=5.0, value=val_spese)
        with col_diesel:
            diesel = st.number_input("Diesel (€)", min_value=0.0, step=5.0, value=val_diesel)
            
        st.markdown("<br/>", unsafe_allow_html=True)
        col_btn1, col_btn2 = st.columns([1, 5])
        with col_btn1:
            submit = st.form_submit_button("Salva Record", type="primary")
        if modalita_modifica:
            with col_btn2:
                if st.form_submit_button("Annulla Modifica"):
                    del st.session_state["data_da_modificare"]
                    st.rerun()

    if submit and sheet:
        data_str = data_inserimento.strftime("%Y-%m-%d")
        mese_str = data_inserimento.strftime("%Y-%m")
        nuova_riga = [data_str, mese_str, guadagno, spese_gen, diesel]
        
        riga_esistente = trova_numero_riga(data_str, sheet)
        if riga_esistente:
            sheet.update(range_name=f"A{riga_esistente}:E{riga_esistente}", values=[nuova_riga])
            st.toast("Record sovrascritto e aggiornato!", icon="🔄")
        else:
            sheet.append_row(nuova_riga)
            st.toast("Nuovo record inserito!", icon="✨")
            
        if "data_da_modificare" in st.session_state:
            del st.session_state["data_da_modificare"]
        st.rerun()

# ============================================================================
# TAB 3: ARCHIVIO STORICO & GESTIONE DATA
# ============================================================================
with tab_storico:
    st.markdown("### 🗂️ Registro completo delle transazioni")
    df_clean = df[(df["Data"] != "") & (df["Data"] != "0")].copy()
    
    if not df_clean.empty:
        # Visualizzazione tabella avanzata con mini barre di riempimento (Bar chart in-column)
        st.dataframe(
            df_clean.sort_values(by="Data", ascending=False),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Data": st.column_config.TextColumn("📅 Data Transazione"),
                "Mese": st.column_config.TextColumn("📆 Mese"),
                "Guadagno": st.column_config.NumberColumn("💰 Guadagno", format="%.2f €", help="Entrate nette del giorno"),
                "Spese_Generiche": st.column_config.NumberColumn("🛍️ Spese Generiche", format="%.2f €"),
                "Diesel": st.column_config.NumberColumn("⛽ Spesa Diesel", format="%.2f €")
            }
        )
        
        # --- PANNELLO DI AZIONE RIBASSATO ED ELIMINAZIONE DI SICUREZZA ---
        st.markdown("<br/><hr style='border-color:#e5e7eb;'/>", unsafe_allow_html=True)
        st.markdown("### 🛠️ Azioni Rapide sui Dati")
        
        col_mod, col_canc = st.columns(2)
        with col_mod:
            st.markdown("<p style='color:#6b7280; font-size:0.9rem;'>Modifica una riga esistente ricaricandola nel form</p>", unsafe_allow_html=True)
            data_mod = st.selectbox("Scegli data da modificare", options=sorted(df_clean["Data"].unique(), reverse=True), key="sb_mod")
            if st.button("🔄 Carica nei campi inserimento", type="secondary"):
                st.session_state["data_da_modificare"] = data_mod
                st.toast("Dati pronti per la modifica nel secondo Tab!")
                
        with col_canc:
            st.markdown("<p style='color:#6b7280; font-size:0.9rem;'>Elimina definitivamente un dato dal Cloud</p>", unsafe_allow_html=True)
            data_canc = st.selectbox("Scegli data da eliminare", options=sorted(df_clean["Data"].unique(), reverse=True), key="sb_canc")
            conferma = st.checkbox(f"Ho capito che non potrò recuperare i dati del {data_canc}", key="conf_del")
            if st.button("🗑️ Elimina Record", type="primary", disabled=not conferma):
                riga_da_cancellare = trova_numero_riga(data_canc, sheet)
                if riga_da_cancellare:
                    sheet.delete_rows(riga_da_cancellare)
                    st.toast(f"Dati del {data_canc} rimossi dal cloud.", icon="🗑️")
                    st.rerun()
    else:
        st.info("Nessuno storico disponibile.")
