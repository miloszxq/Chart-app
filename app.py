import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# --- 1. KONFIGURACJA I STAŁE (Z Twojego kodu) ---
st.set_page_config(layout="wide", page_title="Chart Master Web")

# Stałe stylów z Twojego pliku
REF_LINE_STYLES = ["Ciągła (-)", "Kropkowana (:)", "Przerywana (--)", "Kreska-Kropka (-.)"]
LINE_STYLE_MAP = {"Kropkowana (:)": ":", "Przerywana (--)": "--", "Ciągła (-)": "-", "Kreska-Kropka (-.)": "-."}
DEFAULT_REF_LINE_STYLE = "-" 
DEFAULT_REF_LINE_WIDTH = 1.0
DEFAULT_REF_LINE_COLOR = "#AAAAAA"

# --- 2. ZARZĄDZANIE STANEM APLIKACJI ---
if 'df' not in st.session_state:
    # Dane startowe (Dummy data z Twojego kodu)
    data = {'X': np.arange(0, 10, 0.5), 
            'Y1': np.sin(np.arange(0, 10, 0.5)) * 10 + 20, 
            'Y2': np.cos(np.arange(0, 10, 0.5)) * 5 + 25}
    st.session_state.df = pd.DataFrame(data)

if 'annotations' not in st.session_state:
    st.session_state.annotations = []
if 'ref_lines' not in st.session_state:
    st.session_state.ref_lines = []
if 'series_config' not in st.session_state:
    st.session_state.series_config = {} # Przechowuje kolory, aliasy, widoczność

# --- 3. FUNKCJE POMOCNICZE ---

def process_uploaded_file(uploaded_file):
    """Logika importu z Twojego kodu dostosowana do Streamlit."""
    try:
        if uploaded_file.name.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(uploaded_file)
        else:
            # Próba detekcji nagłówka tak jak w Twoim kodzie
            try:
                # Streamlit file buffer workaround
                uploaded_file.seek(0)
                df_test = pd.read_csv(uploaded_file, sep=None, engine='python', header=None, nrows=10)
                uploaded_file.seek(0)
                try:
                    float(str(df_test.iloc[0, 0]).replace(',', '.').strip())
                    has_header = False
                except ValueError:
                    has_header = True
                
                df = pd.read_csv(uploaded_file, sep=None, engine='python', header=0 if has_header else None)
            except Exception as e:
                st.error(f"Błąd formatu: {e}")
                return None

        if not has_header:
            cols = [f"Kolumna {i+1}" for i in range(len(df.columns))]
            df.columns = cols
        else:
            df.columns = df.columns.astype(str)
            # Obsługa duplikatów
            seen = {}
            new_cols = []
            for col in df.columns:
                if col in seen:
                    seen[col] += 1
                    new_cols.append(f"{col}_{seen[col]}")
                else:
                    seen[col] = 1
                    new_cols.append(col)
            df.columns = new_cols

        # Konwersja
        for col in df.columns:
            df[col] = df[col].astype(str).str.replace(',', '.', regex=False)
            try: df[col] = pd.to_numeric(df[col], errors='coerce')
            except: pass
            
        return df
    except Exception as e:
        st.error(f"Błąd importu: {e}")
        return None

def apply_scaling(df, y_cols, scaling_mode):
    """Logika skalowania z Twojego kodu."""
    if scaling_mode == "Brak (Original)" or df.empty: return df
    
    df_scaled = df.copy()
    for col in y_cols:
        if not pd.api.types.is_numeric_dtype(df[col]): continue
        series = df_scaled[col].astype(float)
        
        if scaling_mode == "Normalizacja Min-Max [0, 1]":
            min_val, max_val = series.min(), series.max()
            df_scaled[col] = (series - min_val) / (max_val - min_val) if max_val - min_val != 0 else 0.0
        elif scaling_mode == "Standaryzacja (Z-Score)":
            mean, std = series.mean(), series.std()
            df_scaled[col] = (series - mean) / std if std != 0 else 0.0
            
    return df_scaled

# --- 4. INTERFEJS UŻYTKOWNIKA ---

st.title("📊 Chart Master 7.0 (Web Edition)")

# --- SIDEBAR (Panel Boczny) ---
with st.sidebar:
    st.header("📂 Dane")
    
    # 1. Import Pliku
    uploaded_file = st.file_uploader("Wczytaj plik (Excel/CSV)", type=['csv', 'txt', 'xlsx', 'xls'])
    if uploaded_file is not None:
        df_new = process_uploaded_file(uploaded_file)
        if df_new is not None:
            st.session_state.df = df_new
            # Reset konfiguracji przy nowym pliku
            st.session_state.series_config = {}

    # 2. Wybór Kolumn
    cols = st.session_state.df.columns.tolist()
    
    # Domyślny X
    default_x_idx = 0
    x_col = st.selectbox("Oś X", cols, index=default_x_idx)
    
    # Domyślne Y (wszystkie poza X)
    available_y = [c for c in cols if c != x_col]
    y_cols = st.multiselect("Serie Y", available_y, default=available_y[:5]) # Domyślnie pierwsze 5
    
    # 3. Skalowanie
    scaling_mode = st.selectbox("Skalowanie", ["Brak (Original)", "Normalizacja Min-Max [0, 1]", "Standaryzacja (Z-Score)"])
    
    st.divider()
    st.header("🎨 Wygląd")
    
    # Styl Wykresu
    chart_type = st.selectbox("Typ Wykresu", ["Liniowy", "Punktowy", "Słupkowy"])
    line_style_name = st.selectbox("Styl Linii", REF_LINE_STYLES)
    line_width = st.slider("Grubość Linii", 0.5, 5.0, 2.0)
    show_markers = st.checkbox("Pokaż Punkty", value=True)
    
    st.divider()
    st.header("⚙️ Osie")
    log_x = st.checkbox("Logarytmiczna Oś X")
    log_y = st.checkbox("Logarytmiczna Oś Y")
    show_grid = st.checkbox("Pokaż Siatkę", value=True)
    
    # Limity Osi (Zamiast wpisywania AUTO, zostaw puste dla auto)
    col1, col2 = st.columns(2)
    with col1:
        x_min = st.number_input("X Min", value=None, placeholder="Auto")
        y_min = st.number_input("Y Min", value=None, placeholder="Auto")
    with col2:
        x_max = st.number_input("X Max", value=None, placeholder="Auto")
        y_max = st.number_input("Y Max", value=None, placeholder="Auto")


# --- GŁÓWNE OKNO ---

# Przygotowanie Danych
df_chart = apply_scaling(st.session_state.df, y_cols, scaling_mode)

# Sortowanie po X dla wykresu liniowego
if not df_chart.empty and pd.api.types.is_numeric_dtype(df_chart[x_col]):
    df_chart = df_chart.sort_values(x_col)

# Konfiguracja Kolorów i Aliasów (Expandery pod wykresem lub obok)
col_main, col_tools = st.columns([3, 1])

with col_tools:
    st.subheader("🛠️ Narzędzia")
    
    # --- ADNOTACJE ---
    with st.expander("📝 Adnotacje", expanded=True):
        # Formularz dodawania
        with st.form("add_note"):
            st.write("Dodaj notatkę:")
            n_x = st.number_input("X", value=float(df_chart[x_col].iloc[len(df_chart)//2]) if not df_chart.empty and pd.api.types.is_numeric_dtype(df_chart[x_col]) else 0.0)
            n_y = st.number_input("Y", value=0.0)
            n_text = st.text_input("Tekst")
            if st.form_submit_button("Dodaj"):
                st.session_state.annotations.append({'x': n_x, 'y': n_y, 'text': n_text})
                st.rerun()
        
        # Lista adnotacji do usuwania
        if st.session_state.annotations:
            st.write("---")
            for i, note in enumerate(st.session_state.annotations):
                c1, c2 = st.columns([4, 1])
                c1.caption(f"{i+1}. {note['text']} ({note['x']:.1f}, {note['y']:.1f})")
                if c2.button("❌", key=f"del_note_{i}"):
                    st.session_state.annotations.pop(i)
                    st.rerun()

    # --- LINIE REFERENCYJNE ---
    with st.expander("📏 Linie Referencyjne", expanded=True):
        # Formularz dodawania
        with st.form("add_line"):
            l_axis = st.selectbox("Oś", ["X", "Y"])
            l_val = st.number_input("Wartość", value=0.0)
            if st.form_submit_button("Dodaj Linię"):
                st.session_state.ref_lines.append({
                    'axis': l_axis, 'value': l_val, 
                    'color': DEFAULT_REF_LINE_COLOR, 
                    'style': DEFAULT_REF_LINE_STYLE, 
                    'width': DEFAULT_REF_LINE_WIDTH
                })
                st.rerun()
        
        # Lista linii do edycji (Zamiast Drag&Drop - edycja wartości)
        if st.session_state.ref_lines:
            st.write("---")
            for i, line in enumerate(st.session_state.ref_lines):
                st.caption(f"Linia {i+1} ({line['axis']})")
                col_val, col_del = st.columns([3, 1])
                
                # Interaktywna zmiana wartości (zastępuje przeciąganie)
                new_val = col_val.number_input(f"Val {i}", value=float(line['value']), key=f"line_val_{i}", label_visibility="collapsed")
                if new_val != line['value']:
                    st.session_state.ref_lines[i]['value'] = new_val
                    st.rerun()
                    
                if col_del.button("❌", key=f"del_line_{i}"):
                    st.session_state.ref_lines.pop(i)
                    st.rerun()
                
                # Opcje stylu dla linii (w rozwijanym menu, żeby nie zaśmiecać)
                with st.popover("Styl"):
                    new_c = st.color_picker("Kolor", line['color'], key=f"lc_{i}")
                    new_s = st.selectbox("Styl", REF_LINE_STYLES, index=0, key=f"ls_{i}")
                    st.session_state.ref_lines[i]['color'] = new_c
                    st.session_state.ref_lines[i]['style'] = LINE_STYLE_MAP[new_s]


# --- RYSOWANIE WYKRESU ---
with col_main:
    # Tytuł Wykresu (Edytowalny)
    chart_title = st.text_input("Tytuł Wykresu", value="Wykres Danych")
    
    # Rysowanie Figury Matplotlib
    # Używamy ciemnego tła, aby pasowało do 'ctk dark'
    bg_color = "#2A2A2A"
    text_color = "white"
    
    fig, ax = plt.subplots(figsize=(10, 6))
    fig.patch.set_facecolor(bg_color)
    ax.set_facecolor(bg_color)
    
    # Style osi
    ax.spines['bottom'].set_color(text_color)
    ax.spines['top'].set_color(text_color)
    ax.spines['left'].set_color(text_color)
    ax.spines['right'].set_color(text_color)
    ax.tick_params(axis='x', colors=text_color)
    ax.tick_params(axis='y', colors=text_color)
    ax.yaxis.label.set_color(text_color)
    ax.xaxis.label.set_color(text_color)
    ax.title.set_color(text_color)
    
    # 1. Dane
    color_cycle = plt.rcParams['axes.prop_cycle'].by_key()['color']
    
    for i, col in enumerate(y_cols):
        # Zarządzanie kolorami sesji
        if col not in st.session_state.series_config:
            st.session_state.series_config[col] = {'color': color_cycle[i % len(color_cycle)], 'alias': col}
        
        cfg = st.session_state.series_config[col]
        
        ls = LINE_STYLE_MAP[line_style_name]
        
        if chart_type == "Liniowy":
            ax.plot(df_chart[x_col], df_chart[col], label=cfg['alias'], color=cfg['color'], 
                    linestyle=ls, linewidth=line_width, 
                    marker='o' if show_markers else None)
        elif chart_type == "Punktowy":
            ax.scatter(df_chart[x_col], df_chart[col], label=cfg['alias'], color=cfg['color'], s=30)
        elif chart_type == "Słupkowy":
            ax.bar(df_chart[x_col], df_chart[col], label=cfg['alias'], color=cfg['color'], alpha=0.7)

    # 2. Linie Referencyjne
    for line in st.session_state.ref_lines:
        if line['axis'] == 'X':
            ax.axvline(line['value'], color=line['color'], linestyle=line['style'], linewidth=line['width'])
        else:
            ax.axhline(line['value'], color=line['color'], linestyle=line['style'], linewidth=line['width'])

    # 3. Adnotacje
    for note in st.session_state.annotations:
        ax.annotate(
            note['text'], 
            xy=(note['x'], note['y']), 
            xytext=(5, 5), textcoords="offset points",
            arrowprops=dict(arrowstyle="->", connectionstyle="arc3,rad=0.2", color=text_color),
            bbox=dict(boxstyle="round,pad=0.5", fc="#444444", alpha=0.9, ec=text_color),
            color=text_color
        )

    # Ustawienia Osi i Siatki
    if x_min: ax.set_xlim(left=x_min)
    if x_max: ax.set_xlim(right=x_max)
    if y_min: ax.set_ylim(bottom=y_min)
    if y_max: ax.set_ylim(top=y_max)
    
    if log_x: ax.set_xscale('log')
    if log_y: ax.set_yscale('log')
    
    if show_grid:
        ax.grid(True, linestyle='--', alpha=0.3, color='gray')
    else:
        ax.grid(False)
        
    ax.set_title(chart_title)
    ax.set_xlabel(x_col)
    ax.set_ylabel("Wartość")
    if y_cols: ax.legend()
    
    st.pyplot(fig)
    
    # --- Sekcja Konfiguracji Serii (Pod wykresem) ---
    with st.expander("🎨 Konfiguracja Serii (Kolory i Nazwy)"):
        cols_cfg = st.columns(len(y_cols)) if len(y_cols) > 0 else [st]
        for i, col in enumerate(y_cols):
            with cols_cfg[i % len(cols_cfg)]:
                st.markdown(f"**{col}**")
                new_alias = st.text_input(f"Nazwa dla {col}", value=st.session_state.series_config[col]['alias'], key=f"alias_{col}")
                new_color = st.color_picker(f"Kolor {col}", value=st.session_state.series_config[col]['color'], key=f"color_{col}")
                
                if new_alias != st.session_state.series_config[col]['alias'] or new_color != st.session_state.series_config[col]['color']:
                    st.session_state.series_config[col]['alias'] = new_alias
                    st.session_state.series_config[col]['color'] = new_color
                    st.rerun()
