import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# --- 1. KONFIGURACJA I STAŁE ---
st.set_page_config(layout="wide", page_title="Chart Master Web")

REF_LINE_STYLES = ["Ciągła (-)", "Kropkowana (:)", "Przerywana (--)", "Kreska-Kropka (-.)"]
LINE_STYLE_MAP = {"Kropkowana (:)": ":", "Przerywana (--)": "--", "Ciągła (-)": "-", "Kreska-Kropka (-.)": "-."}
DEFAULT_REF_LINE_STYLE = "-" 
DEFAULT_REF_LINE_WIDTH = 1.0
DEFAULT_REF_LINE_COLOR = "#AAAAAA"
DARK_BACKGROUND = "#2A2A2A"

# --- 2. ZARZĄDZANIE STANEM ---
if 'df' not in st.session_state:
    data = {'X': np.arange(0, 10, 0.5), 
            'Y1': np.sin(np.arange(0, 10, 0.5)) * 10 + 20, 
            'Y2': np.cos(np.arange(0, 10, 0.5)) * 5 + 25}
    st.session_state.df = pd.DataFrame(data)

if 'annotations' not in st.session_state:
    st.session_state.annotations = []
if 'ref_lines' not in st.session_state:
    st.session_state.ref_lines = []
if 'series_config' not in st.session_state:
    st.session_state.series_config = {}

# --- 3. FUNKCJE POMOCNICZE ---
def process_uploaded_file(uploaded_file):
    try:
        if uploaded_file.name.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(uploaded_file)
        else:
            uploaded_file.seek(0)
            try:
                df = pd.read_csv(uploaded_file)
            except:
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file, sep=None, engine='python')
        
        # Proste czyszczenie nagłówków (jeśli potrzeba)
        df.columns = df.columns.astype(str)
        return df
    except Exception as e:
        st.error(f"Błąd: {e}")
        return None

def apply_scaling(df, y_cols, scaling_mode):
    if scaling_mode == "Brak (Original)" or df.empty: return df
    df_scaled = df.copy()
    for col in y_cols:
        if pd.api.types.is_numeric_dtype(df[col]):
            series = df_scaled[col].astype(float)
            if scaling_mode == "Normalizacja Min-Max [0, 1]":
                min_val, max_val = series.min(), series.max()
                df_scaled[col] = (series - min_val) / (max_val - min_val) if max_val != min_val else 0.0
            elif scaling_mode == "Standaryzacja (Z-Score)":
                mean, std = series.mean(), series.std()
                df_scaled[col] = (series - mean) / std if std != 0 else 0.0
    return df_scaled

# --- 4. RYSOWANIE WYKRESU (Matplotlib) ---
def draw_chart(df, x_col, y_cols, chart_config):
    fig, ax = plt.subplots(figsize=(10, 6), facecolor=DARK_BACKGROUND)
    ax.set_facecolor(DARK_BACKGROUND)
    
    # Kolory tekstu i osi (Białe dla ciemnego tła)
    TEXT_COLOR = 'white'
    plt.setp(ax.spines.values(), color='gray')
    ax.tick_params(colors=TEXT_COLOR)
    ax.yaxis.label.set_color(TEXT_COLOR)
    ax.xaxis.label.set_color(TEXT_COLOR)
    ax.title.set_color(TEXT_COLOR)

    # Dane
    color_cycle = plt.rcParams['axes.prop_cycle'].by_key()['color']
    for i, col in enumerate(y_cols):
        if col not in st.session_state.series_config:
            st.session_state.series_config[col] = {'color': color_cycle[i % len(color_cycle)], 'alias': col}
        
        cfg = st.session_state.series_config[col]
        ls = LINE_STYLE_MAP[chart_config['line_style']]
        
        if chart_config['type'] == "Liniowy":
            ax.plot(df[x_col], df[col], label=cfg['alias'], color=cfg['color'], 
                    linestyle=ls, linewidth=chart_config['width'], 
                    marker='o' if chart_config['markers'] else None)
        elif chart_config['type'] == "Punktowy":
            ax.scatter(df[x_col], df[col], label=cfg['alias'], color=cfg['color'])
        elif chart_config['type'] == "Słupkowy":
            ax.bar(df[x_col], df[col], label=cfg['alias'], color=cfg['color'], alpha=0.7)

    # Linie Referencyjne
    for line in st.session_state.ref_lines:
        style = LINE_STYLE_MAP.get(line.get('style', '-'), '-')
        if line['axis'] == 'X':
            ax.axvline(line['value'], color=line['color'], linestyle=style, linewidth=line['width'])
        else:
            ax.axhline(line['value'], color=line['color'], linestyle=style, linewidth=line['width'])

    # Adnotacje
    for note in st.session_state.annotations:
        ax.annotate(
            note['text'], xy=(note['x'], note['y']), xytext=(5, 5), textcoords="offset points",
            arrowprops=dict(arrowstyle="->", color=TEXT_COLOR),
            bbox=dict(boxstyle="round,pad=0.5", fc="#444444", ec=TEXT_COLOR),
            color=TEXT_COLOR
        )

    # Ustawienia
    if chart_config['log_x']: ax.set_xscale('log')
    if chart_config['log_y']: ax.set_yscale('log')
    if chart_config['grid']: ax.grid(True, linestyle='--', alpha=0.3)
    
    if chart_config['xlim'][0] is not None: ax.set_xlim(left=chart_config['xlim'][0])
    if chart_config['xlim'][1] is not None: ax.set_xlim(right=chart_config['xlim'][1])
    if chart_config['ylim'][0] is not None: ax.set_ylim(bottom=chart_config['ylim'][0])
    if chart_config['ylim'][1] is not None: ax.set_ylim(top=chart_config['ylim'][1])

    ax.set_title(chart_config['title'])
    ax.set_xlabel(x_col)
    if y_cols: ax.legend()
    
    return fig

# --- 5. INTERFEJS ---
st.title("📊 Chart Master Web")

# Panel Boczny
with st.sidebar:
    st.header("📂 Dane")
    uploaded_file = st.file_uploader("Wczytaj plik", type=['csv', 'xlsx'])
    if uploaded_file:
        df_new = process_uploaded_file(uploaded_file)
        if df_new is not None: st.session_state.df = df_new

    cols = st.session_state.df.columns.tolist()
    x_col = st.selectbox("Oś X", cols, index=0)
    y_cols = st.multiselect("Serie Y", [c for c in cols if c != x_col], default=[c for c in cols if c != x_col][:2])
    
    scaling = st.selectbox("Skalowanie", ["Brak (Original)", "Normalizacja Min-Max", "Standaryzacja"])
    
    st.divider()
    st.header("🎨 Wygląd")
    chart_type = st.selectbox("Typ", ["Liniowy", "Punktowy", "Słupkowy"])
    line_style = st.selectbox("Styl Linii", REF_LINE_STYLES)
    width = st.slider("Grubość", 0.5, 5.0, 2.0)
    markers = st.checkbox("Punkty", True)
    
    st.divider()
    log_x = st.checkbox("Log X")
    log_y = st.checkbox("Log Y")
    grid = st.checkbox("Siatka", True)
    
    with st.expander("Limity Osi"):
        c1, c2 = st.columns(2)
        xm = c1.number_input("X Min", value=None)
        xM = c2.number_input("X Max", value=None)
        ym = c1.number_input("Y Min", value=None)
        yM = c2.number_input("Y Max", value=None)

# Przygotowanie danych
df_chart = apply_scaling(st.session_state.df, y_cols, scaling)
if not df_chart.empty and pd.api.types.is_numeric_dtype(df_chart[x_col]):
    df_chart = df_chart.sort_values(x_col)

# Konfiguracja Wykresu
config = {
    'type': chart_type, 'line_style': line_style, 'width': width, 'markers': markers,
    'log_x': log_x, 'log_y': log_y, 'grid': grid,
    'xlim': (xm, xM), 'ylim': (ym, yM),
    'title': st.text_input("Tytuł Wykresu", "Mój Wykres")
}

# Układ Główny
col_main, col_tools = st.columns([3, 1])

with col_tools:
    st.subheader("Narzędzia")
    
    # ADNOTACJE
    with st.expander("📝 Adnotacje", expanded=True):
        with st.form("add_note"):
            # Domyślne wartości ze środka wykresu
            def_x = float(df_chart[x_col].mean()) if not df_chart.empty and pd.api.types.is_numeric_dtype(df_chart[x_col]) else 0.0
            
            nx = st.number_input("X", value=def_x)
            ny = st.number_input("Y", value=0.0)
            nt = st.text_input("Tekst")
            if st.form_submit_button("Dodaj"):
                st.session_state.annotations.append({'x': nx, 'y': ny, 'text': nt})
                st.rerun()
        
        if st.session_state.annotations:
            st.caption("Lista:")
            for i, note in enumerate(st.session_state.annotations):
                c1, c2 = st.columns([4, 1])
                c1.text(f"{i+1}. {note['text']}")
                if c2.button("X", key=f"dn{i}"):
                    st.session_state.annotations.pop(i)
                    st.rerun()

    # LINIE REF
    with st.expander("📏 Linie Ref.", expanded=True):
        with st.form("add_line"):
            la = st.selectbox("Oś", ["X", "Y"])
            lv = st.number_input("Wartość", value=0.0)
            if st.form_submit_button("Dodaj"):
                st.session_state.ref_lines.append({
                    'axis': la, 'value': lv, 'color': '#AAAAAA', 'style': '-', 'width': 1.0
                })
                st.rerun()
        
        if st.session_state.ref_lines:
            for i, line in enumerate(st.session_state.ref_lines):
                c1, c2 = st.columns([4, 1])
                val = c1.number_input(f"{line['axis']} {i+1}", value=float(line['value']), key=f"lv{i}")
                if val != line['value']:
                    st.session_state.ref_lines[i]['value'] = val
                    st.rerun()
                if c2.button("X", key=f"dl{i}"):
                    st.session_state.ref_lines.pop(i)
                    st.rerun()

# Wyświetlenie Wykresu
with col_main:
    fig = draw_chart(df_chart, x_col, y_cols, config)
    st.pyplot(fig)

    # Edycja Serii
    with st.expander("🎨 Edycja Serii (Kolory/Nazwy)"):
        cols = st.columns(3)
        for i, col in enumerate(y_cols):
            with cols[i % 3]:
                st.markdown(f"**{col}**")
                new_a = st.text_input("Nazwa", st.session_state.series_config[col]['alias'], key=f"a{col}")
                new_c = st.color_picker("Kolor", st.session_state.series_config[col]['color'], key=f"c{col}")
                if new_a != st.session_state.series_config[col]['alias'] or new_c != st.session_state.series_config[col]['color']:
                    st.session_state.series_config[col]['alias'] = new_a
                    st.session_state.series_config[col]['color'] = new_c
                    st.rerun()
