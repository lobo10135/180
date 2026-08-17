import datetime
import io
import pandas as pd
reportlab_available = True
try:
    from reportlab.lib.pagesizes import landscape, letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
except ImportError:
    reportlab_available = False

import requests
import streamlit as st
import yfinance as yf

# Streamlit Layout konfigurieren
st.set_page_config(page_title="180's Strategie Scanner", layout="wide")


@st.cache_data(ttl=86400)
def get_sp500_tickers():
    """Lädt die aktuellen S&P 500 Ticker dynamisch von Wikipedia."""
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
            " like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    tables = pd.read_html(io.StringIO(response.text))
    df = tables[0]
    tickers = df["Symbol"].tolist()
    tickers = [t.replace(".", "-") for t in tickers]
    return tickers


@st.cache_data(ttl=86400)
def get_dax_tickers():
    """Gibt eine bereinigte, feste Liste aktueller DAX-Unternehmen zurück (inkl. Qiagen & Hochtief)."""
    return [
        "ADS.DE", "ALV.DE", "BAS.DE", "BAYN.DE", "BEI.DE", "BMW.DE", "BNR.DE",
        "CBK.DE", "CON.DE", "DTG.DE", "DBK.DE", "DB1.DE", "DHL.DE", "DTE.DE", 
        "EOAN.DE", "FRE.DE", "HNR1.DE", "HEI.DE", "HEN3.DE", "HOT.DE", "IFX.DE", 
        "MBG.DE", "MRK.DE", "MTX.DE", "MUV2.DE", "P911.DE", "PAH3.DE", "QIA.DE",
        "RHM.DE", "RWE.DE", "SAP.DE", "SRT3.DE", "SIE.DE", "SHL.DE", "SY1.DE", 
        "VOW3.DE", "VNA.DE", "ZAL.DE", "AIR.PA"
    ]


@st.cache_data(ttl=86400)
def get_mdax_tickers():
    """Gibt eine strikt bereinigte, feste Liste echter MDAX-Unternehmen zurück (garantiert ohne DAX-Werte wie Qiagen & Hochtief)."""
    return [
        "AIXA.DE", "AT1.DE", "ARL.DE", "BC8.DE", "BEI2.DE", "B3SA.DE", "AG1.DE", 
        "COP.DE", "DBG.DE", "DEQ.DE", "DHER.DE", "DWNI.DE", "ELM.DE", "ENR.DE", 
        "EVT.DE", "FRA.DE", "FNT.DE", "G24.DE", "GKS.DE", "HAG.DE", 
        "HNR.DE", "JUN3.DE", "KKR.DE", "KRN.DE", "LAN.DE", "LEG.DE", 
        "LXS.DE", "NEM.DE", "NDX1.DE", "OSR.DE", "PSM.DE", "RAT.DE", "RXC.DE", 
        "SANT.DE", "SAZ.DE", "SHA.DE", "SIX2.DE", "SMHN.DE", "TEG.DE", "TLX.DE", 
        "UN01.DE", "UTDI.DE", "WAC.DE", "WAF.DE", "JEN.DE", "KTN.DE"
    ]


def evaluate_stock(df_single, ticker, strategy_mode):
    """Prüft eine einzelne DataFrame-Historie auf Long- oder Short-Strategie."""
    try:
        if df_single is None or len(df_single) < 55:
            return None

        if isinstance(df_single.columns, pd.MultiIndex):
            df_single.columns = df_single.columns.get_level_values(0)

        df_single = df_single.copy()
        df_single["SMA10"] = df_single["Close"].rolling(window=10).mean()
        df_single["SMA50"] = df_single["Close"].rolling(window=50).mean()

        t = df_single.iloc[-1]
        t_minus_1 = df_single.iloc[-2]

        range_t_1 = t_minus_1["High"] - t_minus_1["Low"]
        if range_t_1 == 0 or pd.isna(range_t_1):
            return None
        
        range_t = t["High"] - t["Low"]
        if range_t == 0 or pd.isna(range_t):
            return None

        if strategy_mode == "Long":
            lower_quartile_t_1 = t_minus_1["Low"] + 0.25 * range_t_1
            cond_t_minus_1 = t_minus_1["Close"] <= lower_quartile_t_1

            upper_quartile_t = t["Low"] + 0.75 * range_t
            cond_t_upper = t["Close"] >= upper_quartile_t
            cond_sma10 = t["Close"] > t["SMA10"]
            cond_sma50 = t["Close"] > t["SMA50"]

            if cond_t_minus_1 and cond_t_upper and cond_sma10 and cond_sma50:
                high_t = float(t["High"])
                stop_buy = round(high_t + 0.125, 2)
                stop_loss = round(stop_buy - 1.0, 2)

                return {
                    "Ticker": ticker,
                    "Stop Buy": stop_buy,
                    "Stop": stop_loss,
                    "Schluss (T)": round(float(t["Close"]), 2),
                    "High (T)": round(high_t, 2),
                    "Low (T)": round(float(t["Low"]), 2),
                    "SMA 10": round(float(t["SMA10"]), 2),
                    "SMA 50": round(float(t["SMA50"]), 2),
                    "Schluss (T-1)": round(float(t_minus_1["Close"]), 2),
                }
        elif strategy_mode == "Short":
            upper_quartile_t_1 = t_minus_1["Low"] + 0.75 * range_t_1
            cond_t_minus_1 = t_minus_1["Close"] >= upper_quartile_t_1

            lower_quartile_t = t["Low"] + 0.25 * range_t
            cond_t_lower = t["Close"] <= lower_quartile_t
            cond_sma10 = t["Close"] < t["SMA10"]
            cond_sma50 = t["Close"] < t["SMA50"]

            if cond_t_minus_1 and cond_t_lower and cond_sma10 and cond_sma50:
                low_t = float(t["Low"])
                stop_buy = round(low_t - 0.125, 2)
                stop_loss = round(stop_buy + 1.0, 2)

                return {
                    "Ticker": ticker,
                    "Stop Buy": stop_buy,
                    "Stop": stop_loss,
                    "Schluss (T)": round(float(t["Close"]), 2),
                    "High (T)": round(float(t["High"]), 2),
                    "Low (T)": round(low_t, 2),
                    "SMA 10": round(float(t["SMA10"]), 2),
                    "SMA 50": round(float(t["SMA50"]), 2),
                    "Schluss (T-1)": round(float(t_minus_1["Close"]), 2),
                }
    except Exception:
        return None
    return None


def generate_pdf(df, strategy_title):
    """Erstellt ein sauberes PDF im Querformat aus dem Ergebnis-DataFrame"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30,
    )
    
    elements = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'ReportTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#1f77b4'),
        spaceAfter=15,
    )
    
    subtitle_style = ParagraphStyle(
        'ReportSubtitle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.gray,
        spaceAfter=20,
    )

    elements.append(Paragraph(f"180's Scanner – Ergebnis ({strategy_title})", title_style))
    elements.append(Paragraph(f"Erstellt am: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", subtitle_style))
    
    table_data = [list(df.columns)]
    for _, row in df.iterrows():
        table_data.append([str(val) for val in row])
        
    t = Table(table_data, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f77b4')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f9f9f9')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d3d3d3')),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
    ]))
    
    elements.append(t)
    doc.build(elements)
    buffer.seek(0)
    return buffer


# --- Benutzeroberfläche ---
st.title("🔮 180's Strategie Scanner")
st.markdown("""
Dieser Streamlit-Scanner überprüft Aktien auf die **"180's"-Strategien**:

* **🟢 Long-Strategie:**
  * **Tag T-1 (Vortag):** Schlusskurs im **unteren Viertel (untere 25 %)**.
  * **Tag T (Letzter Tag):** Schlusskurs im **oberen Viertel (obere 25 %)** **UND** über **10-Tage** sowie **50-Tage-Durchschnitt**.
  * **Berechnungen:** Stop Buy = High (Tag T) $+ 0.125$ | Stop = Stop Buy $- 1$

* **🔴 Short-Strategie:**
  * **Tag T-1 (Vortag):** Schlusskurs im **oberen Viertel (obere 25 %)**.
  * **Tag T (Letzter Tag):** Schlusskurs im **unteren Viertel (untere 25 %)** **UND** unter **10-Tage** sowie **50-Tage-Durchschnitt**.
  * **Berechnungen:** Stop Buy = Low (Tag T) $- 0.125$ | Stop = Stop Buy $+ 1$
""")

# Zeile 1: S&P 500 Buttons
st.subheader("S&P 500 Scanner")
col1, col2 = st.columns(2)
with col1:
    run_sp_long = st.button("🟢 S&P500 Long", type="secondary")
with col2:
    run_sp_short = st.button("🔻 S&P500 Short", type="secondary")

# Zeile 2: DAX Buttons
st.subheader("DAX (Deutscher Aktienindex) Scanner")
col3, col4 = st.columns(2)
with col3:
    run_dax_long = st.button("🟢 Dax Long", type="secondary")
with col4:
    run_dax_short = st.button("🔻 Dax Short", type="secondary")

# Zeile 3: MDAX Buttons
st.subheader("MDAX Scanner")
col5, col6 = st.columns(2)
with col5:
    run_mdax_long = st.button("🟢 MDax Long", type="secondary")
with col6:
    run_mdax_short = st.button("🔻 MDax Short", type="secondary")

# Ausführung Logik
triggered_button = None
strategy_mode = None
universe_type = None

if run_sp_long:
    triggered_button, strategy_mode, universe_type = run_sp_long, "Long", "S&P 500"
elif run_sp_short:
    triggered_button, strategy_mode, universe_type = run_sp_short, "Short", "S&P 500"
elif run_dax_long:
    triggered_button, strategy_mode, universe_type = run_dax_long, "Long", "DAX"
elif run_dax_short:
    triggered_button, strategy_mode, universe_type = run_dax_short, "Short", "DAX"
elif run_mdax_long:
    triggered_button, strategy_mode, universe_type = run_mdax_long, "Long", "MDAX"
elif run_mdax_short:
    triggered_button, strategy_mode, universe_type = run_mdax_short, "Short", "MDAX"

if triggered_button:
    if universe_type == "S&P 500":
        tickers = get_sp500_tickers()
    elif universe_type == "DAX":
        tickers = get_dax_tickers()
    else:
        tickers = get_mdax_tickers()

    st.info(
        f"Lade und analysiere {len(tickers)} Aktien aus dem **{universe_type}** für die"
        f" **{strategy_mode}**-Strategie. Bitte warten..."
    )

    results = []
    progress_bar = st.progress(0)
    total = len(tickers)

    for idx, ticker in enumerate(tickers):
        try:
            df_single = yf.download(ticker, period="4mo", progress=False, auto_adjust=True)
            if df_single is not None and not df_single.empty:
                res = evaluate_stock(df_single, ticker, strategy_mode)
                if res:
                    results.append(res)
        except Exception:
            pass

        progress_bar.progress(min((idx + 1) / total, 1.0))

    progress_bar.empty()

    if results:
        st.success(
            f"Analyse abgeschlossen! Es wurden **{len(results)}** Treffer für"
            f" **{universe_type} {strategy_mode}** gefunden."
        )
        result_df = pd.DataFrame(results)
        
        desired_columns = [
            "Ticker",
            "Stop Buy",
            "Stop",
            "Schluss (T)",
            "High (T)",
            "Low (T)",
            "SMA 10",
            "SMA 50",
            "Schluss (T-1)",
        ]
        result_df = result_df[[col for col in desired_columns if col in result_df.columns]]

        st.dataframe(result_df, use_container_width=True, hide_index=True)
        
        if reportlab_available:
            pdf_buffer = generate_pdf(result_df, f"{universe_type} {strategy_mode}")
            st.download_button(
                label=f"📥 Ergebnisse als PDF herunterladen ({universe_type} {strategy_mode})",
                data=pdf_buffer,
                file_name=f"180s_{universe_type.replace(' ', '_')}_{strategy_mode.lower()}_ergebnisse.pdf",
                mime="application/pdf",
            )
        else:
            st.info("Hinweis: Installieren Sie `reportlab` (`pip install reportlab`), um die PDF-Export-Funktion zu aktivieren.")
    else:
        st.warning(
            f"Aktuell erfüllen keine Aktien im **{universe_type}** die Kriterien dieser"
            f" **{strategy_mode}**-Strategie."
        )
