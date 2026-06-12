import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

# Configurazione pagina
st.set_page_config(page_title="Il Mio Salvadanaio", page_icon="💰", layout="wide")
st.title("💰 Registro Guadagni, Spese e Grafici (Cloud)")

# --- CONNESSIONE A GOOGLE SHEETS ---
def init_connection():
    try:
        # Recupera le credenziali dai Secrets di Streamlit
        creds_dict = st.secrets["gcp_service_account"]
        scope = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        
        # Recupera il link del foglio
        url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        sheet = client.open_by_url(url).sheet1
        return sheet
    except Exception as e:
        st.error(f"Errore di connessione al Cloud: {e}")
        return None

sheet = init_connection()

# Carica i dati dal foglio Google
if sheet:
    try:
        data = sheet.get_all_records()
        if data:
            df = pd.DataFrame(data)
        else:
            # Se il foglio è vuoto, inizializza le colonne corrette
            df = pd.DataFrame(columns=["Data", "Mese", "Guadagno", "Spese_Generiche", "Diesel"])
    except Exception:
        df = pd.DataFrame(columns=["Data", "Mese", "Guadagno", "Spese_Generiche", "Diesel"])
else:
    df = pd.DataFrame(columns=["Data", "Mese", "Guadagno", "Spese_Generiche", "Diesel"])

# CONTROLLO DI SICUREZZA: Se mancano colonne nel DataFrame, le creiamo vuote per evitare il KeyError
for col in ["Data", "Mese", "Guadagno", "Spese_Generiche", "Diesel"]:
    if col not in df.columns:
        df[col] = 0

# Assicuriamoci che i tipi di dati siano corretti
df["Guadagno"] = pd.to_numeric(df["Guadagno"], errors='coerce').fillna(0)
df["Spese_Generiche"] = pd.to_numeric(df["Spese_Generiche"], errors='coerce').fillna(0)
df["Diesel"] = pd.to_numeric(df["Diesel"], errors='coerce').fillna(0)
df["Data"] = df["Data"].astype(str)

# --- FORM DI INSERIMENTO / MODIFICA GIORNALIERO ---
st.header("✍️ Inserisci o Modifica i dati di una giornata")

data_default = datetime.today()
val_guadagno = 0.0
val_spese = 0.0
val_diesel = 0.0
modalita_modifica = False

if "data_da_modificare" in st.session_state and not df.empty:
    riga_vecchia = df[df["Data"] == st.session_state["data_da_modificare"]]
    if not riga_vecchia.empty:
        data_default = datetime.strptime(st.session_state["data_da_modificare"], "%Y-%m-%d")
        val_guadagno = float(riga_vecchia.iloc[0]["Guadagno"])
        val_spese = float(riga_vecchia.iloc[0]["Spese_Generiche"])
        val_diesel = float(riga_vecchia.iloc[0]["Diesel"])
        modalita_modifica = True
        st.warning(f"🔄 Stai modificando i dati del: {st.session_state['data_da_modificare']}")

with st.form("inserimento_giornaliero", clear_on_submit=True):
    col_data, col_guadagno, col_spese, col_diesel = st.columns(4)
    
    with col_data:
        if modalita_modifica:
            st.write(f"**Data:** {st.session_state['data_da_modificare']}")
            data_inserimento = data_default
        else:
            data_inserimento = st.date_input("Data", data_default)
            
    with col_guadagno:
        guadagno = st.number_input("Guadagno (€)", min_value=0.0, step=1.0, value=val_guadagno)
    with col_spese:
        spese_gen = st.number_input("Spese generiche (€)", min_value=0.0, step=1.0, value=val_spese)
    with col_diesel:
        diesel = st.number_input("Spesa Diesel (€)", min_value=0.0, step=1.0, value=val_diesel)
    
    testo_bottone = "Aggiorna Giornata" if modalita_modifica else "Salva Giornata"
    submit = st.form_submit_button(testo_bottone)

def salva_su_cloud(dataframe_da_salvare):
    if sheet:
        # Svuota il foglio e riscrive tutto (inclusi i titoli)
        sheet.clear()
        sheet.update([dataframe_da_salvare.columns.values.tolist()] + dataframe_da_salvare.values.tolist())

if submit:
    data_str = data_inserimento.strftime("%Y-%m-%d")
    mese_str = data_inserimento.strftime("%Y-%m")
    
    # Rimuove il vecchio record se si inserisce una data già esistente (sovrascrittura)
    if data_str in df["Data"].values:
        df = df[df["Data"] != data_str]
        
    nuovo_dato = pd.DataFrame({
        "Data": [data_str],
        "Mese": [mese_str],
        "Guadagno": [guadagno],
        "Spese_Generiche": [spese_gen],
        "Diesel": [diesel]
    })
    
    df = pd.concat([df, nuovo_dato], ignore_index=True)
    salva_su_cloud(df)
    
    if "data_da_modificare" in st.session_state:
        del st.session_state["data_da_modificare"]
        
    st.success("Dati salvati sul Cloud!")
    st.rerun()

# --- RESOCONTO MENSILE ---
st.markdown("---")
st.header("📊 Resoconto Mensile e Storico")

# Mostra i dati solo se il DataFrame non è vuoto e contiene almeno una riga reale di dati
if not df.empty and len(df[df["Data"] != "0"]) > 0:
    # Rimuoviamo eventuali righe di sicurezza vuote ("0") prima di fare i grafici
    df_clean = df[df["Data"] != "0"].copy()
    
    resoconto_mensile = df_clean.groupby("Mese").agg({
        "Guadagno": "sum",
        "Spese_Generiche": "sum",
        "Diesel": "sum"
    }).reset_index()
    
    resoconto_mensile["Spese Totali"] = resoconto_mensile["Spese_Generiche"] + resoconto_mensile["Diesel"]
    resoconto_mensile["Utile Netto"] = resoconto_mensile["Guadagno"] - resoconto_mensile["Spese Totali"]
    
    # --- SALVADANAIO TOTALE ---
    utile_totale_assoluto = resoconto_mensile["Utile Netto"].sum()
    guadagni_totali_assoluti = resoconto_mensile["Guadagno"].sum()
    spese_totali_assolute = resoconto_mensile["Spese Totali"].sum()
    
    st.subheader("🎯 Stato del Salvadanaio Complessivo (Tutti i mesi)")
    c1, c2, c3 = st.columns(3)
    c1.metric("Entrate Totali Storiche", f"{guadagni_totali_assoluti:.2f} €")
    c2.metric("Spese Totali Storiche", f"{spese_totali_assolute:.2f} €")
    c3.subheader(f"💰 SALDO ACCUMULATO: {utile_totale_assoluto:.2f} €")
    
    # --- GRAFICO DELL'ANDAMENTO NEL TEMPO ---
    st.markdown("### 📈 Andamento del Saldo Accumulato nel Tempo")
    df_storico = df_clean.sort_values(by="Data").copy()
    df_storico["Utile_Giorno"] = df_storico["Guadagno"] - (df_storico["Spese_Generiche"] + df_storico["Diesel"])
    df_storico["Saldo Accumulato (€)"] = df_storico["Utile_Giorno"].cumsum()
    
    fig_linea = px.line(df_storico, x="Data", y="Saldo Accumulato (€)", title="Evoluzione del tuo risparmio giorno dopo giorno", markers=True, render_mode="svg")
    fig_linea.update_traces(line=dict(color="#2ca02c", width=3)) 
    fig_linea.update_layout(height=350, margin=dict(t=40, b=20, l=0, r=0))
    st.plotly_chart(fig_linea, use_container_width=True)
    
    st.markdown("---")
    
    # --- DETTAGLIO MESE PER MESE ---
    for index, row in resoconto_mensile.iloc[::-1].iterrows():
        mese_corrente = row['Mese']
        st.subheader(f"📅 Mese: {mese_corrente}")
        col_dati, col_grafico = st.columns([1, 1])
        
        with col_dati:
            m1, m2, m3 = st.columns(3)
            m1.metric("Entrate", f"{row['Guadagno']:.2f} €")
            m2.metric("Uscite Totali", f"{row['Spese Totali']:.2f} €")
            m3.metric("Utile Netto", f"{row['Utile Netto']:.2f} €")
            
            dettaglio_mese = pd.DataFrame({
                "Categoria": ["Spese Generiche", "Diesel"],
                "Importo": [row['Spese_Generiche'], row['Diesel']]
            })
            st.dataframe(dettaglio_mese.style.format({"Importo": "{:.2f} €"}), use_container_width=True, hide_index=True)
        
        with col_grafico:
            if row['Spese Totali'] > 0:
                fig = px.pie(dettaglio_mese, values='Importo', names='Categoria', title="Divisione delle Spese", color_discrete_sequence=px.colors.qualitative.Pastel)
                fig.update_layout(margin=dict(t=30, b=0, l=0, r=0), height=200)
                st.plotly_chart(fig, use_container_width=True, key=f"grafico_torta_{mese_corrente}")
            else:
                st.info("Nessuna spesa registrata in questo mese. Ottimo!")
        st.markdown("---")
        
    # --- SEZIONE GESTIONE E CANCELLAZIONE ---
    with st.expander("👀 Vedi singoli inserimenti / Modifica e Cancella dati"):
        st.dataframe(df_clean.sort_values(by="Data", ascending=False), use_container_width=True, hide_index=True)
        
        st.markdown("### 🛠️ Azioni Rapide")
        col_mod, col_canc = st.columns(2)
        
        with col_mod:
            st.write("**🔄 Modifica una giornata:**")
            data_mod = st.selectbox("Seleziona la data da caricare nel form in alto", options=sorted(df_clean["Data"].unique(), reverse=True), key="sb_mod")
            if st.button("Carica nel Form"):
                st.session_state["data_da_modificare"] = data_mod
                st.rerun()
            if modalita_modifica:
                if st.button("Annulla Modifica"):
                    del st.session_state["data_da_modificare"]
                    st.rerun()
                    
        with col_canc:
            st.write("**❌ Cancella una giornata:**")
            data_canc = st.selectbox("Seleziona la data da eliminare definitivamente", options=sorted(df_clean["Data"].unique(), reverse=True), key="sb_canc")
            if st.button("Elimina Definitivamente", type="primary"):
                df_clean = df_clean[df_clean["Data"] != data_canc]
                salva_su_cloud(df_clean)
                st.success(f"Giornata del {data_canc} eliminata!")
                st.rerun()
else:
    st.info("Non ci sono ancora dati registrati. Inserisci la tua prima giornata di lavoro qui sopra!")