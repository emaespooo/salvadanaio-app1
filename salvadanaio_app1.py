import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

# Configurazione pagina
st.set_page_config(page_title="Il Mio Salvadanaio", page_icon="💰", layout="wide")
st.title("💰 Registro Guadagni, Spese e Grafici (Cloud)")

COLONNE_BASE = ["Data", "Mese", "Guadagno", "Spese_Generiche", "Diesel"]
COLONNE_NUMERICHE = ["Guadagno", "Spese_Generiche", "Diesel"]


# --- CONNESSIONE A GOOGLE SHEETS ---
@st.cache_resource(ttl=3600)  # Mantiene in cache la connessione per 1 ora
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

# --- LOGICA DI MODIFICA ---
data_da_modificare = st.session_state.get("data_da_modificare")
modalita_modifica = data_da_modificare is not None

if modalita_modifica:
    st.warning(f"🔄 Modalità Modifica attiva per la data: **{data_da_modificare}**")
    riga_vecchia = df[df["Data"] == data_da_modificare]
    if not riga_vecchia.empty:
        data_default = datetime.strptime(data_da_modificare, "%Y-%m-%d")
        val_guadagno = float(riga_vecchia.iloc[0]["Guadagno"])
        val_spese = float(riga_vecchia.iloc[0]["Spese_Generiche"])
        val_diesel = float(riga_vecchia.iloc[0]["Diesel"])
    else:
        # La riga non esiste più (es. cancellata da un'altra sessione): usciamo dalla modalità modifica
        st.session_state.pop("data_da_modificare", None)
        modalita_modifica = False
        data_default = datetime.today()
        val_guadagno, val_spese, val_diesel = 0.0, 0.0, 0.0
else:
    data_default = datetime.today()
    val_guadagno, val_spese, val_diesel = 0.0, 0.0, 0.0

# --- FORM DI INSERIMENTO / MODIFICA ---
st.header("✍️ Inserisci o Modifica i dati di una giornata")

with st.form("inserimento_giornaliero", clear_on_submit=True, border=True):
    col_data, col_guadagno, col_spese, col_diesel = st.columns(4)

    with col_data:
        if modalita_modifica:
            st.write(f"**Data in modifica:** {data_da_modificare}")
            data_inserimento = data_default
        else:
            data_inserimento = st.date_input("Data", data_default)

    with col_guadagno:
        guadagno = st.number_input(
            "Guadagno (€)", min_value=0.0, step=10.0, value=val_guadagno
        )
    with col_spese:
        spese_gen = st.number_input(
            "Spese generiche (€)", min_value=0.0, step=5.0, value=val_spese
        )
    with col_diesel:
        diesel = st.number_input(
            "Spesa Diesel (€)", min_value=0.0, step=5.0, value=val_diesel
        )

    col_btn1, col_btn2 = st.columns([1, 5])
    with col_btn1:
        submit = st.form_submit_button(
            "Salva" if not modalita_modifica else "Aggiorna",
            type="primary",
            use_container_width=True,
        )

    annulla_modifica = False
    if modalita_modifica:
        with col_btn2:
            annulla_modifica = st.form_submit_button("Annulla Modifica")

# --- GESTIONE ANNULLA MODIFICA ---
if annulla_modifica:
    st.session_state.pop("data_da_modificare", None)
    st.rerun()

# --- SALVATAGGIO SUL CLOUD (riga singola, niente clear() globale) ---
if submit and sheet:
    data_str = data_inserimento.strftime("%Y-%m-%d")
    mese_str = data_inserimento.strftime("%Y-%m")
    nuova_riga = [data_str, mese_str, guadagno, spese_gen, diesel]

    try:
        with st.spinner("Salvataggio in corso..."):
            if data_str in df["Data"].values:
                # Riga già esistente: aggiorniamo SOLO quella riga, non l'intero foglio
                riga_idx = trova_numero_riga(data_str)
                if riga_idx:
                    sheet.update(range_name=f"A{riga_idx}:E{riga_idx}", values=[nuova_riga])
                else:
                    st.warning("⚠️ Riga non trovata sul foglio: viene creata una nuova voce per sicurezza.")
                    sheet.append_row(nuova_riga)
            else:
                # Nuovo inserimento: append_row è rapido e non tocca il resto del foglio
                sheet.append_row(nuova_riga)

        st.session_state.pop("data_da_modificare", None)
        st.success("Dati salvati sul Cloud con successo!")
        st.rerun()
    except Exception as e:
        st.error(f"⚠️ Errore durante il salvataggio: {e}. I dati esistenti non sono stati alterati.")

# --- RESOCONTO MENSILE ---
st.divider()
st.header("📊 Resoconto Mensile e Storico")

df_clean = df[(df["Data"] != "") & (df["Data"] != "0")].copy()

if not df_clean.empty:
    resoconto_mensile = (
        df_clean.groupby("Mese")
        .agg({"Guadagno": "sum", "Spese_Generiche": "sum", "Diesel": "sum"})
        .reset_index()
    )
    resoconto_mensile["Spese Totali"] = resoconto_mensile["Spese_Generiche"] + resoconto_mensile["Diesel"]
    resoconto_mensile["Utile Netto"] = resoconto_mensile["Guadagno"] - resoconto_mensile["Spese Totali"]

    # --- KPI METRICS ---
    st.subheader("🎯 Stato del Salvadanaio Complessivo")
    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        c1.metric("Entrate Totali", f"{resoconto_mensile['Guadagno'].sum():,.2f} €")
        c2.metric("Spese Totali", f"{resoconto_mensile['Spese Totali'].sum():,.2f} €")

        saldo_totale = resoconto_mensile["Utile Netto"].sum()
        delta_colore = "normal" if saldo_totale >= 0 else "inverse"
        c3.metric(
            "💰 SALDO ACCUMULATO",
            f"{saldo_totale:,.2f} €",
            delta=f"{saldo_totale:,.2f} €",
            delta_color=delta_colore,
        )

    # --- GRAFICO STORICO ---
    st.markdown("### 📈 Andamento del Saldo Accumulato")
    df_storico = df_clean.sort_values(by="Data").copy()
    df_storico["Utile_Giorno"] = df_storico["Guadagno"] - (df_storico["Spese_Generiche"] + df_storico["Diesel"])
    df_storico["Saldo Accumulato (€)"] = df_storico["Utile_Giorno"].cumsum()

    fig_linea = px.line(df_storico, x="Data", y="Saldo Accumulato (€)", markers=True, template="plotly_white")
    fig_linea.update_traces(line=dict(color="#2ca02c", width=3))
    fig_linea.update_layout(height=300, margin=dict(t=10, b=10, l=0, r=0))
    st.plotly_chart(fig_linea, use_container_width=True)

    # --- DETTAGLIO MESE PER MESE ---
    for _, row in resoconto_mensile.iloc[::-1].iterrows():
        mese_corrente = row["Mese"]
        with st.expander(f"📅 Mese: {mese_corrente} (Netto: {row['Utile Netto']:.2f} €)", expanded=True):
            col_dati, col_grafico = st.columns([1, 1])

            with col_dati:
                m1, m2, m3 = st.columns(3)
                m1.metric("Entrate", f"{row['Guadagno']:.2f} €")
                m2.metric("Uscite", f"{row['Spese Totali']:.2f} €")
                m3.metric("Netto", f"{row['Utile Netto']:.2f} €")

                dettaglio_mese = pd.DataFrame({
                    "Categoria": ["Spese Generiche", "Diesel"],
                    "Importo": [row["Spese_Generiche"], row["Diesel"]],
                })
                st.dataframe(
                    dettaglio_mese,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Importo": st.column_config.NumberColumn("Importo", format="€ %.2f"),
                    },
                )

            with col_grafico:
                if row["Spese Totali"] > 0:
                    fig = px.pie(
                        dettaglio_mese,
                        values="Importo",
                        names="Categoria",
                        height=180,
                        color_discrete_sequence=px.colors.qualitative.Safe,
                    )
                    fig.update_layout(margin=dict(t=0, b=0, l=0, r=0))
                    st.plotly_chart(fig, use_container_width=True, key=f"pie_{mese_corrente}")
                else:
                    st.info("Nessuna spesa questo mese!")

    # --- GESTIONE E CANCELLAZIONE ---
    st.divider()
    with st.expander("🛠️ Pannello di Controllo (Vedi, Modifica, Elimina)"):
        df_pannello = df_clean.sort_values(by="Data", ascending=False).copy()
        df_pannello["Data"] = pd.to_datetime(df_pannello["Data"], errors="coerce")

        st.dataframe(
            df_pannello,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                "Mese": st.column_config.TextColumn("Mese"),
                "Guadagno": st.column_config.NumberColumn("Guadagno", format="€ %.2f"),
                "Spese_Generiche": st.column_config.NumberColumn("Spese Generiche", format="€ %.2f"),
                "Diesel": st.column_config.NumberColumn("Diesel", format="€ %.2f"),
            },
        )

        col_mod, col_canc = st.columns(2)

        with col_mod:
            data_mod = st.selectbox(
                "Seleziona data da MODIFICARE:",
                options=sorted(df_clean["Data"].unique(), reverse=True),
                key="sb_mod",
            )
            if st.button("Carica nel Form", type="secondary"):
                st.session_state["data_da_modificare"] = data_mod
                st.rerun()

        with col_canc:
            data_canc = st.selectbox(
                "Seleziona data da ELIMINARE:",
                options=sorted(df_clean["Data"].unique(), reverse=True),
                key="sb_canc",
            )
            conferma_canc = st.checkbox(
                "⚠️ Confermo di voler eliminare definitivamente questa giornata",
                key="chk_conferma_canc",
            )
            if st.button("Elimina Definitivamente", type="primary", disabled=not conferma_canc):
                try:
                    with st.spinner("Eliminazione in corso..."):
                        riga_idx = trova_numero_riga(data_canc)
                        if riga_idx:
                            sheet.delete_rows(riga_idx)
                            st.success(f"Giornata del {data_canc} eliminata!")
                            st.rerun()
                        else:
                            st.error("⚠️ Riga non trovata sul foglio. Eliminazione annullata.")
                except Exception as e:
                    st.error(f"⚠️ Errore durante l'eliminazione: {e}")
else:
    st.info("Benvenuto! Non ci sono ancora dati registrati nel Cloud. Inserisci la tua prima giornata qui sopra.")
