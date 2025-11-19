import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import io # Do obsługi zapisywania plików w pamięci

# --- 1. KONFIGURACJA I STAŁE ---
st.set_page_config(layout="wide", page_title="Chart Master Web")

REF_LINE_STYLES = ["Ciągła (-)", "Kropkowana (:)", "Przerywana (--)", "Kreska-Kropka (-.)"]
LINE_STYLE_MAP = {"Kropkowana (:)": ":", "Przerywana (--)": "--", "Ciągła (-)": "-", "Kreska-Kropka (-.)": "-."}
DEFAULT_REF_LINE_STYLE = "-" 
DEFAULT_REF_LINE_WIDTH = 1.0
DEFAULT_REF_LINE_COLOR = "#AAAAAA"
DARK_BACKGROUND = "#2A2A2A"

# --- 2. ZARZĄDZANIE STANEM ---
if 'data_mode' not in st.session_state:
    st.session_state.data_mode = "manual" # 'manual' lub 'upload'

if 'df' not in st.session_state:
    # Pusta ramka danych na start dla trybu manualnego
    st.session_state.df = pd.DataFrame({"X": [1, 2, 3, 4, 5], "Y1": [10, 20, 15, 25, 30]})

if 'annotations' not in st.session_state:
    st.session_state.annotations = []
if 'ref_lines' not in st.session_state:
    st.session_state.ref_lines = []
if 'series_config' not in st.session_state:
    st.session_state.series_config = {}

# --- 3. FUNKCJE POMOCNICZE ---

def process_uploaded_file(uploaded_file):
    """Obsługa CSV, Excel i TXT."""
    try:
        if uploaded_file.name.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(uploaded_file)
        else:
            # Obsługa CSV i TXT
            uploaded_file.seek(0)
            try:
                # Próba z automatycznym separatorem (dla txt/csv)
                df = pd.read_csv(uploaded_file, sep=None, engine='python')
            except:
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file) # Domyślny przecinek
        
        df.columns = df.columns.astype(str)
        return df
    except Exception as e:
        st.error(f"Błąd formatu pliku: {e}")
        return None

def create_chart_figure(df, x_col, y_cols, config, export_mode=None):
    """
    Generuje figurę Matplotlib.
    export_mode: None (ekran), 'print_color' (białe tło), 'print_bw' (czarno-białe)
    """
    
    # Ustawienia kolorów w zależności od trybu
    if export_mode in ['print_color', 'print_bw']:
        bg_color = "white"
        text_color = "black"
        grid_color = "lightgray"
    else:
        bg_color = DARK_BACKGROUND
        text_color = "white"
        grid_color = "gray"

    fig, ax = plt.subplots(figsize=(10, 6), facecolor=bg_color)
    ax.set_facecolor(bg_color)
    
    # Style osi
    for spine in ax.spines.values():
        spine.set_color(text_color)
    ax.tick_params(colors=text_color)
    ax.yaxis.label.set_color(text_color)
    ax.xaxis.label.set_color(text_color)
    ax.title.set_color(text_color)

    # 1. DANE
    color_cycle = plt.rcParams['axes.prop_cycle'].by_key()['color']
    
    for i, col in enumerate(y_cols):
        if col not in df.columns: continue
        
        # Pobranie konfiguracji (jeśli brak, użyj domyślnej)
        if col not in st.session_state.series_config:
             st.session_state.series_config[col] = {'color': color_cycle[i % len(color_cycle)], 'alias': col}
        
        cfg = st.session_state.series_config[col]
        alias = cfg['alias']
        
        if export_mode == 'print_bw':
            color = 'black'
            linestyle = ['-', '--', ':', '-.'][i % 4] # Różne linie dla B&W
        else:
            color = cfg['color']
            linestyle = LINE_STYLE_MAP[config['line_style']]

        if config['type'] == "Liniowy":
            ax.plot(df[x_col], df[col], label=alias, color=color, 
                    linestyle=linestyle, linewidth=config['width'], 
                    marker='o' if config['markers'] else None)
        elif config['type'] == "Punktowy":
            ax.scatter(df[x_col], df[col], label=alias, color=color, s=30)
        elif config['type'] == "Słupkowy":
            ax.bar(df[x_col], df[col], label=alias, color=color, alpha=0.7)

    # 2. LINIE REFERENCYJNE
    for line in st.session_state.ref_lines:
        l_color = 'black' if export_mode == 'print_bw' else line['color']
        l_style = LINE_STYLE_MAP.get(line.get('style', '-'), '-')
        
        if line['axis'] == 'X':
            ax.axvline(line['value'], color=l_color, linestyle=l_style, linewidth=line['width'])
        else:
            ax.axhline(line['value'], color=l_color, linestyle=l_style, linewidth=line['width'])

    # 3. ADNOTACJE
    for note in st.session_state.annotations:
        n_color = 'black' if export_mode in ['print_color', 'print_bw'] else 'white'
        box_bg = 'white' if export_mode in ['print_color', 'print_bw'] else '#444444'
        
        ax.annotate(
            note['text'], 
            xy=(note['x'], note['y']), 
            xytext=(5, 5), textcoords="offset points",
            arrowprops=dict(arrowstyle="->", color=n_color),
            bbox=dict(boxstyle="round,pad=0.5", fc=box_bg, ec=n_color),
            color=n_color
        )

    # Ustawienia Osi
    if config['xlim'][0] is not None: ax.set_xlim(left=config['xlim'][0])
    if config['xlim'][1] is not None: ax.set_xlim(right=config['xlim'][1])
    if config['ylim'][0] is not None: ax.set_ylim(bottom=config['ylim'][0])
    if config['ylim'][1] is not None: ax.set_ylim(top=config['ylim'][1])
    
    if config['log_x']: ax.set_xscale('log')
    if config['log_y']: ax.set_yscale('log')
    
    if config['grid']:
        ax.grid(True, linestyle='--', alpha=0.3, color=grid_color)
    else:
        ax.grid(False)
        
    ax.set_title(config['title'])
    ax.set_xlabel(x_col)
    if y_cols: ax.legend(facecolor=bg_color, labelcolor=text_color)
    
    fig.tight_layout()
    return fig

# --- 4. INTERFEJS UŻYTKOWNIKA ---

st.title("📊 Chart Master Web")

# --- PANEL BOCZNY (DANE) ---
with st.sidebar:
    st.header("1. Źródło Danych")
    
    data_source = st.radio("Wybierz tryb:", ["Wpisz Ręcznie", "Wgraj Plik"], horizontal=True)
    
    if data_source == "Wgraj Plik":
        uploaded_file = st.file_uploader("Obsługuje: Excel, CSV, TXT", type=['csv', 'txt', 'xlsx', 'xls'])
        if uploaded_file:
            df_new = process_uploaded_file(uploaded_file)
            if df_new is not None: 
                st.session_state.df = df_new
                st.success("Wczytano plik!")
    else:
        st.info("Edytuj tabelę poniżej, aby zmienić dane wykresu.")

    st.header("2. Konfiguracja Osi")
    cols = st.session_state.df.columns.tolist()
    
    # Zabezpieczenie przed brakiem kolumn
    if not cols:
        st.warning("Brak danych. Dodaj kolumny w edytorze.")
        st.stop()

    x_col = st.selectbox("Oś X", cols, index=0)
    available_y = [c for c in cols if c != x_col]
    y_cols = st.multiselect("Serie Y", available_y, default=available_y[:5])
    
    scaling = st.selectbox("Skalowanie Y", ["Brak (Original)", "Normalizacja [0-1]", "Standaryzacja (Z-Score)"])
    
    st.header("3. Styl")
    chart_type = st.selectbox("Typ", ["Liniowy", "Punktowy", "Słupkowy"])
    show_grid = st.checkbox("Siatka", True)
    
    # Limity Osi
    with st.expander("Granice Osi (Limity)"):
        c1, c2 = st.columns(2)
        xm = c1.number_input("X Min", value=None)
        xM = c2.number_input("X Max", value=None)
        ym = c1.number_input("Y Min", value=None)
        yM = c2.number_input("Y Max", value=None)

# --- GŁÓWNY OBSZAR ---

# 1. EDYTOR DANYCH (Widoczny zawsze lub tylko w trybie ręcznym)
if data_source == "Wpisz Ręcznie":
    with st.expander("✏️ Edytor Danych (Kliknij, aby rozwinąć)", expanded=True):
        st.write("Możesz dodawać wiersze i edytować wartości. Zmiany od razu widać na wykresie.")
        # data_editor pozwala na pełną edycję jak w Excelu
        edited_df = st.data_editor(st.session_state.df, num_rows="dynamic", use_container_width=True)
        st.session_state.df = edited_df

# Przygotowanie danych do wykresu
df_chart = st.session_state.df.copy()
# Skalowanie
if scaling != "Brak (Original)":
    for col in y_cols:
        if pd.api.types.is_numeric_dtype(df_chart[col]):
            if scaling == "Normalizacja [0-1]":
                df_chart[col] = (df_chart[col] - df_chart[col].min()) / (df_chart[col].max() - df_chart[col].min())
            else:
                df_chart[col] = (df_chart[col] - df_chart[col].mean()) / df_chart[col].std()

if not df_chart.empty and x_col in df_chart.columns and pd.api.types.is_numeric_dtype(df_chart[x_col]):
    df_chart = df_chart.sort_values(x_col)

# Konfiguracja do rysowania
chart_config = {
    'type': chart_type, 'line_style': 'Ciągła (-)', 'width': 2.0, 'markers': True,
    'log_x': False, 'log_y': False, 'grid': show_grid,
    'xlim': (xm, xM), 'ylim': (ym, yM),
    'title': ""
}

# --- KOLUMNY: WYKRES + NARZĘDZIA ---
col_plot, col_tools = st.columns([3, 1])

with col_tools:
    st.subheader("🛠️ Edycja Elementów")
    
    # A. ZARZĄDZANIE ADNOTACJAMI
    with st.expander("📝 Adnotacje", expanded=True):
        # Formularz dodawania
        with st.form("new_note"):
            # Domyślne współrzędne (środek danych)
            def_x = float(df_chart[x_col].mean()) if not df_chart.empty and pd.api.types.is_numeric_dtype(df_chart[x_col]) else 0.0
            def_y = float(df_chart[y_cols[0]].mean()) if not df_chart.empty and len(y_cols)>0 else 0.0
            
            st.write("Dodaj nową:")
            c1, c2 = st.columns(2)
            new_x = c1.number_input("Poz X", value=def_x, key="nx")
            new_y = c2.number_input("Poz Y", value=def_y, key="ny")
            new_txt = st.text_input("Tekst", "Punkt A")
            
            if st.form_submit_button("➕ Dodaj"):
                st.session_state.annotations.append({'x': new_x, 'y': new_y, 'text': new_txt})
                st.rerun()

        # Lista edycji istniejących
        if st.session_state.annotations:
            st.write("**Edytuj istniejące:**")
            for i, note in enumerate(st.session_state.annotations):
                with st.popover(f"✏️ {note['text'][:10]}..."):
                    # Edycja wartości = PRZESUWANIE
                    e_x = st.number_input(f"X##{i}", value=float(note['x']))
                    e_y = st.number_input(f"Y##{i}", value=float(note['y']))
                    e_txt = st.text_input(f"Tekst##{i}", value=note['text'])
                    
                    # Zapisz zmiany od razu po zmianie wartości (Streamlit rerunuje po zmianie inputu)
                    if e_x != note['x'] or e_y != note['y'] or e_txt != note['text']:
                        st.session_state.annotations[i] = {'x': e_x, 'y': e_y, 'text': e_txt}
                        st.rerun()
                        
                    if st.button("Usuń", key=f"rm_note_{i}"):
                        st.session_state.annotations.pop(i)
                        st.rerun()

    # B. LINIE REFERENCYJNE
    with st.expander("📏 Linie Referencyjne", expanded=True):
        with st.form("new_line"):
            l_ax = st.selectbox("Oś", ["X", "Y"])
            l_val = st.number_input("Wartość", value=0.0)
            if st.form_submit_button("➕ Dodaj Linię"):
                st.session_state.ref_lines.append({
                    'axis': l_ax, 'value': l_val, 
                    'color': '#AAAAAA', 'style': '-', 'width': 1.0
                })
                st.rerun()
        
        # Lista edycji (Przesuwanie suwakami/liczbami)
        if st.session_state.ref_lines:
            st.write("**Przesuń / Edytuj:**")
            for i, line in enumerate(st.session_state.ref_lines):
                st.caption(f"Linia {i+1} ({line['axis']})")
                c1, c2 = st.columns([3, 1])
                # To działa jak przesuwanie - zmiana wartości odświeża wykres
                new_v = c1.number_input("Poz", value=float(line['value']), key=f"lv_{i}", label_visibility="collapsed")
                
                if new_v != line['value']:
                    st.session_state.ref_lines[i]['value'] = new_v
                    st.rerun()
                    
                if c2.button("X", key=f"rm_line_{i}"):
                    st.session_state.ref_lines.pop(i)
                    st.rerun()
                
                with st.popover("Styl"):
                    c = st.color_picker("Kolor", line['color'], key=f"lc_{i}")
                    s = st.selectbox("Typ", REF_LINE_STYLES, key=f"ls_{i}")
                    w = st.slider("Grubość", 0.5, 5.0, line['width'], key=f"lw_{i}")
                    # Zapis stylu
                    st.session_state.ref_lines[i].update({'color': c, 'style': LINE_STYLE_MAP[s], 'width': w})


with col_plot:
    # Tytuł i Wykres
    chart_title = st.text_input("Tytuł Wykresu", "Mój Wykres", label_visibility="collapsed", placeholder="Wpisz tytuł...")
    chart_config['title'] = chart_title
    
    # Generowanie wykresu (Ekran)
    fig_screen = create_chart_figure(df_chart, x_col, y_cols, chart_config, export_mode=None)
    st.pyplot(fig_screen)

    st.divider()
    
    # --- SEKCJA EKSPORTU ---
    st.subheader("💾 Eksport")
    
    e_col1, e_col2, e_col3 = st.columns(3)
    
    # Funkcja pomocnicza do pobierania pliku
    def get_image_download_link(fig, format, mode, label):
        buf = io.BytesIO()
        # Generujemy NOWĄ figurę specjalnie dla eksportu z odpowiednimi kolorami
        fig_export = create_chart_figure(df_chart, x_col, y_cols, chart_config, export_mode=mode)
        fig_export.savefig(buf, format=format, dpi=300)
        plt.close(fig_export) # Ważne: zamykamy figurę, żeby zwolnić pamięć
        buf.seek(0)
        return st.download_button(
            label=label,
            data=buf,
            file_name=f"wykres_{mode}.{format}",
            mime=f"image/{format}"
        )

    with e_col1:
        st.markdown("**1. Ekran (Ciemny)**")
        get_image_download_link(fig_screen, "png", None, "Pobierz PNG")
        get_image_download_link(fig_screen, "pdf", None, "Pobierz PDF")
        
    with e_col2:
        st.markdown("**2. Druk (Kolor)**")
        get_image_download_link(fig_screen, "png", "print_color", "Pobierz PNG")
        get_image_download_link(fig_screen, "pdf", "print_color", "Pobierz PDF")

    with e_col3:
        st.markdown("**3. Druk (Cz-B)**")
        get_image_download_link(fig_screen, "png", "print_bw", "Pobierz PNG")
        get_image_download_link(fig_screen, "pdf", "print_bw", "Pobierz PDF")
