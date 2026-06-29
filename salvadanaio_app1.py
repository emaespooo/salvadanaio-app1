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

# Custom CSS for FinTech aesthetic
st.markdown("""
<style>
    /* Primary color palette */
    :root {
        --primary-color: #1f77b4;
        --success-color: #2ca02c;
        --danger-color: #d62728;
        --warning-color: #ff7f0e;
        --neutral-light: #f8f9fa;
        --neutral-dark: #1e1e1e;
        --border-color: #e0e0e0;
    }
    
    /* Custom metric card styling */
    [data-testid="metric-container"] {
        background-color: #f8f9fa;
        border-radius: 12px;
        padding: 1.25rem;
        border-left: 4px solid #1f77b4;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
    }
    
    /* Form styling */
    .stForm {
        background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%);
        border-radius: 12px;
        border: 1px solid #e0e0e0;
        padding: 2rem;
        box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
    }
    
    /* Container styling */
    [data-testid="stVerticalBlock"] > [data-testid="stContainer"] {
        border-radius: 12px;
    }
    
    /* Expandable section styling */
    .streamlit-expanderHeader {
        background-color: #f8f9fa;
        border-radius: 8px;
        border: 1px solid #e0e0e0;
    }
    
    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] button {
        border-radius: 8px 8px 0 0;
        font-weight: 500;
    }
    
    /* Dataframe styling */
    [data-testid="stDataFrame"] {
        border-radius: 8px;
        overflow: hidden;
    }
    
    /* Header styling */
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

# Color scheme for charts
COLOR_GUADAGNO = "#2ca02c"  # Green for income
COLOR_SPESE = "#d62728"      # Red for expenses
COLOR_DIESEL = "#ff7f0e"     # Orange for diesel
COLOR_SALDO = "#1f77b4"      # Blue for balance

# ============================================================================
# GOOGLE SHEETS CONNECTION
# ============================================================================

@st.cache_resource(ttl=3600)
def init_connection():
    """Inizializza la connessione a Google Sheets con diagnostica granulare degli errori."""
    try:
        creds_dict = st.secrets["gcp_service_account"]
    except KeyError:
        st.error("⚠️ Credenziali 'gcp_service_account' non trovate nei secrets di Streamlit.")
        return None

    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
    except Exception as e:
        st.error(f"⚠️ Errore nell'autenticazione con Google: {e}")
        return None

    try:
        url = st.secrets["connections"]["gsheets"]["spreadsheet"]
    except KeyError:
        st.error("⚠️ URL dello Spreadsheet non trovato nei secrets (connections.gsheets.spreadsheet).")
        return None

    try:
        return client.open_by_url(url).sheet1
    except gspread.SpreadsheetNotFound:
        st.error("⚠️ Spreadsheet non trovato. Controlla l'URL nei secrets.")
        return None
    except Exception as e:
        st.error(f"Errore di connessione al Cloud: {e}")
        return None


sheet = init_connection()


def carica_dati():
    """Carica i dati dal foglio, garantendo sempre tipi e colonne corretti anche in caso di errore."""
    if not sheet:
        return pd.DataFrame(columns=COLONNE_BASE)

    try:
        records = sheet.get_all_records()
    except gspread.exceptions.APIError as e:
        st.error(f"⚠️ Errore API di Google Sheets durante il caricamento dei dati: {e}")
        return pd.DataFrame(columns=COLONNE_BASE)
    except Exception as e:
        st.error(f"⚠️ Errore imprevisto durante il caricamento dei dati: {e}")
        return pd.DataFrame(columns=COLONNE_BASE)

    df = pd.DataFrame(records) if records else pd.DataFrame(columns=COLONNE_BASE)

    # Garantiamo la presenza di tutte le colonne base
    for col in COLONNE_BASE:
        if col not in df.columns:
            df[col] = 0.0 if col in COLONNE_NUMERICHE else ""

    for col in COLONNE_NUMERICHE:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    df["Data"] = df["Data"].astype(str)
    df["Mese"] = df["Mese"].astype(str)
    return df


def trova_numero_riga(data_str):
    """
    Trova il numero di riga REALE sul foglio Google (1-indexed, header incluso)
    corrispondente a una data, così da poter aggiornare/eliminare SOLO quella riga
    invece di riscrivere l'intero foglio.
    """
    if not sheet:
        return None
    try:
        cella = sheet.find(data_str, in_column=1)
        return cella.row if cella else None
    except gspread.exceptions.CellNotFound:
        return None
    except Exception as e:
        st.warning(f"⚠️ Impossibile localizzare la riga sul foglio: {e}")
        return None


df = carica_dati()

# ============================================================================
# HEADER SECTION
# ============================================================================

col_header_left, col_header_right = st.columns([4, 1])

with col_header_left:
    st.markdown("""
    <h1 style="margin: 0; color: #1e1e1e; font-size: 2.5rem;">
        💰 Il Mio Salvadanaio
    </h1>
    <p style="margin: 0.5rem 0 0 0; color: #666; font-size: 0.95rem;">
        Gestisci guadagni, spese e analizza il tuo patrimonio
    </p>
    """, unsafe_allow_html=True)

with col_header_right:
    st.markdown(f"""
    <div style="text-align: right; padding-top: 0.5rem;">
        <p style="color: #999; font-size: 0.85rem; margin: 0;">
            Ultimo aggiornamento<br/>
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
    "📝 Registra Nuovo",
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
        
        # --- KPI SECTION ---
        st.markdown("### 🎯 Riepilogo Globale")
        
        totale_guadagni = resoconto_mensile['Guadagno'].sum()
        totale_spese = resoconto_mensile['Spese Totali'].sum()
        saldo_totale = resoconto_mensile["Utile Netto"].sum()
        
        kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)
        
        with kpi_col1:
            st.metric(
                "📈 Entrate Totali",
                f"{totale_guadagni:,.2f} €",
                delta=None,
                help="Somma di tutti i guadagni registrati"
            )
        
        with kpi_col2:
            st.metric(
                "📉 Spese Totali",
                f"{totale_spese:,.2f} €",
                delta=f"-{totale_spese:,.2f} €" if totale_spese > 0 else "0,00 €",
                help="Somma di tutte le spese"
            )
        
        with kpi_col3:
            st.metric(
                "⚖️ Utile Netto",
                f"{saldo_totale:,.2f} €",
                delta=f"{saldo_totale:,.2f} €",
                delta_color="normal" if saldo_totale >= 0 else "inverse",
                help="Guadagni meno spese totali"
            )
        
        with kpi_col4:
            rapporto_spesa = (totale_spese / totale_guadagni * 100) if totale_guadagni > 0 else 0
            st.metric(
                "💸 Rapporto Spesa",
                f"{rapporto_spesa:.1f} %",
                delta=f"{'⚠️ Elevato' if rapporto_spesa > 60 else '✅ Sano'}" if totale_guadagni > 0 else "—",
                help="Percentuale di spese rispetto ai guadagni"
            )
        
        # --- STORICO SALDO ACCUMULATO ---
        st.markdown("### 📈 Andamento del Saldo Accumulato")
        
        df_storico = df_clean.sort_values(by="Data").copy()
        df_storico["Utile_Giorno"] = df_storico["Guadagno"] - (df_storico["Spese_Generiche"] + df_storico["Diesel"])
        df_storico["Saldo Accumulato (€)"] = df_storico["Utile_Giorno"].cumsum()
        
        fig_linea = px.line(
            df_storico,
            x="Data",
            y="Saldo Accumulato (€)",
            markers=True,
            template="plotly_white",
            color_discrete_sequence=[COLOR_SALDO]
        )
        
        fig_linea.update_traces(
            line=dict(width=3, color=COLOR_SALDO),
            marker=dict(size=6, symbol="circle"),
            hovertemplate="<b>%{x}</b><br>Saldo: € %{y:,.2f}<extra></extra>"
        )
        
        fig_linea.update_layout(
            height=400,
            hovermode="x unified",
            margin=dict(t=20, b=20, l=60, r=20),
            yaxis_title="Saldo (€)",
            xaxis_title="Data",
            plot_bgcolor="rgba(248, 249, 250, 0.5)",
            paper_bgcolor="white",
            font=dict(family="Arial, sans-serif", size=11, color="#1e1e1e")
        )
        
        st.plotly_chart(fig_linea, use_container_width=True)
        
        # --- MONTHLY BREAKDOWN ---
        st.markdown("### 📅 Dettaglio Mensile")
        
        for idx, (_, row) in enumerate(resoconto_mensile.iloc[::-1].iterrows()):
            mese_corrente = row["Mese"]
            utile_mese = row['Utile Netto']
            colore_utile = "🟢" if utile_mese >= 0 else "🔴"
            
            with st.expander(
                f"**{mese_corrente}** • Entrate: €{row['Guadagno']:,.2f} | Spese: €{row['Spese Totali']:,.2f} | Netto: {colore_utile} €{utile_mese:,.2f}",
                expanded=(idx == 0)
            ):
                col_metrics, col_chart = st.columns([1, 1])
                
                with col_metrics:
                    st.markdown("**Metriche Mensili**")
                    
                    met_col1, met_col2, met_col3 = st.columns(3)
                    
                    with met_col1:
                        st.metric(
                            "📈 Entrate",
                            f"€{row['Guadagno']:,.2f}",
                            help="Guadagni del mese"
                        )
                    
                    with met_col2:
                        st.metric(
                            "📉 Uscite",
                            f"€{row['Spese Totali']:,.2f}",
                            help="Spese totali del mese"
                        )
                    
                    with met_col3:
                        st.metric(
                            "⚖️ Netto",
                            f"€{utile_mese:,.2f}",
                            delta_color="normal" if utile_mese >= 0 else "inverse",
                            help="Risultato netto"
                        )
                    
                    st.markdown("**Dettaglio Spese**")
                    dettaglio_mese = pd.DataFrame({
                        "Categoria": ["Spese Generiche", "Diesel"],
                        "Importo": [row["Spese_Generiche"], row["Diesel"]],
                    })
                    
                    st.dataframe(
                        dettaglio_mese,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "Categoria": st.column_config.TextColumn("Categoria", width="medium"),
                            "Importo": st.column_config.NumberColumn("Importo", format="€ %.2f", width="medium"),
                        }
                    )
                
                with col_chart:
                    st.markdown("**Distribuzione Spese**")
                    
                    if row["Spese Totali"] > 0:
                        fig_pie = px.pie(
                            dettaglio_mese,
                            values="Importo",
                            names="Categoria",
                            color_discrete_sequence=[COLOR_DIESEL, COLOR_SPESE],
                            hole=0.3
                        )
                        
                        st.plotly_chart(fig_pie, use_container_width=True)
                    else:
                        st.info("Nessuna spesa da visualizzare.")
