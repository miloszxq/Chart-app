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
# Stan 'data_mode' nie jest potrzebny, wystarczy sprawdzenie 'data_source'
# if 'data_mode' not in st.session_state:
#     st.session_state.data_mode = "manual" # 'manual' lub 'upload'

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
            linestyle = LINE_STYLE_MAP.get(config['line_style'], '-') # Użyj .get dla bezpieczeństwa

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
        # Zabezpieczenie przed brakiem kluczy po starej konfiguracji
        l_color = 'black' if export_mode == 'print_bw' else line.get('color', DEFAULT_REF_LINE_COLOR)
        l_style = LINE_STYLE_MAP.get(line.get('style'), DEFAULT_REF_LINE_STYLE)
        l_width = line.get('width', DEFAULT_REF_LINE_WIDTH)
        
        if line['axis'] == 'X':
            ax.axvline(line['value'], color=l_color, linestyle=l_style, linewidth=l_width)
        else:
            ax.axhline(line['value'], color=l_color, linestyle=l_style, linewidth=l_width)

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
    ax.set_xlabel(config['x_label'] if config['x_label'] else x_col)
    ax.set_ylabel(config['y_label'] if config['y_label'] else "Wartość Y")
    if y_cols: ax.legend(facecolor=bg_color, labelcolor=text_color)
    
    fig.tight_layout()
    return fig

# Funkcja pomocnicza do pobierania pliku
def get_image_download_link(fig, format, mode, label, file_prefix):
    buf = io.BytesIO()
    # Generujemy NOWĄ figurę specjalnie dla eksportu z odpowiednimi kolorami
    fig_export = create_chart_figure(st.session_state.df_chart, 
                                     st.session_state.x_col, 
                                     st.session_state.y_cols, 
                                     st.session_state.chart_config, 
                                     export_mode=mode)
    fig_export.savefig(buf, format=format, dpi=300)
    plt.close(fig_export) # Ważne: zamykamy figurę, żeby zwolnić pamięć
    buf.seek(0)
    return st.download_button(
        label=label,
        data=buf,
        file_name=f"{file_prefix}_{mode}.{format}" if mode else f"{file_prefix}.{format}",
        mime=f"image/{format}"
    )

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
                # Resetowanie stanu dla nowych danych
                st.session_state.df = df_new
                st.session_state.annotations = []
                st.session_state.ref_lines = []
                st.session_state.series_config = {}
                st.success("Wczytano plik!")
    # else:
    #     st.info("Edytuj tabelę poniżej, aby zmienić dane wykresu.")

    st.header("2. Konfiguracja Osi")
    cols = st.session_state.df.columns.tolist()
    
    # Zabezpieczenie przed brakiem kolumn
    if not cols:
        st.warning("Brak danych. Dodaj kolumny w edytorze.")
        st.stop()

    # Wybór kolumn
    x_col = st.selectbox("Oś X", cols, index=0, key='sel_x_col')
    available_y = [c for c in cols if c != x_col]
    y_cols = st.multiselect("Serie Y", available_y, default=available_y[:5], key='sel_y_cols')
    
    scaling = st.selectbox("Skalowanie Y", ["Brak (Original)", "Normalizacja [0-1]", "Standaryzacja (Z-Score)"], key='sel_scaling')
    
    st.header("3. Opcje Wykresu")
    chart_type = st.selectbox("Typ", ["Liniowy", "Punktowy", "Słupkowy"], key='sel_type')
    show_grid = st.checkbox("Siatka", True, key='sel_grid')
    
    # Styl Linii
    c1, c2 = st.columns(2)
    line_style = c1.selectbox("Styl Linii", REF_LINE_STYLES, key='sel_l_style')
    line_width = c2.slider("Grubość", 0.5, 5.0, 2.0, key='sel_l_width')
    show_markers = st.checkbox("Pokaż Markery (Punkty)", True, key='sel_markers')

    # Logarytmiczne osie
    c3, c4 = st.columns(2)
    log_x = c3.checkbox("Oś X Logarytmiczna", False, key='sel_log_x')
    log_y = c4.checkbox("Oś Y Logarytmiczna", False, key='sel_log_y')

    # Granice i Etykiety
    with st.expander("Granice i Etykiety Osi"):
        c1, c2 = st.columns(2)
        xm = c1.number_input("X Min", value=None, key='sel_xmin')
        xM = c2.number_input("X Max", value=None, key='sel_xmax')
        ym = c1.number_input("Y Min", value=None, key='sel_ymin')
        yM = c2.number_input("Y Max", value=None, key='sel_ymax')
        
        x_label = st.text_input("Etykieta Osi X", value="", placeholder=x_col, key='sel_xlabel')
        y_label = st.text_input("Etykieta Osi Y", value="", placeholder="Wartość Y", key='sel_ylabel')
        

# --- GŁÓWNY OBSZAR: PRZYGOTOWANIE DANYCH ---

# 1. EDYTOR DANYCH
if data_source == "Wpisz Ręcznie":
    with st.expander("✏️ Edytor Danych (Kliknij, aby rozwinąć)", expanded=True):
        st.write("Możesz dodawać wiersze i edytować wartości. Zmiany są zapisywane po zakończeniu edycji komórki.")
        
        # Zabezpieczenie przed błędem zacinania:
        # 1. Używamy klucza 'data_editor_key'.
        # 2. Porównujemy, czy edytowany DF różni się od DF w stanie sesji.
        edited_df = st.data_editor(st.session_state.df, 
                                   num_rows="dynamic", 
                                   use_container_width=True, 
                                   key="data_editor_key")
        
        if not edited_df.equals(st.session_state.df):
            st.session_state.df = edited_df
            # NIE używamy st.rerun, aby uniknąć błędów 'None'

# Przygotowanie danych do wykresu (Zawsze po edytorze)
df_chart = st.session_state.df.copy()

# Skalowanie
if scaling != "Brak (Original)":
    for col in y_cols:
        if pd.api.types.is_numeric_dtype(df_chart[col]):
            if scaling == "Normalizacja [0-1]":
                min_val = df_chart[col].min()
                max_val = df_chart[col].max()
                if max_val != min_val:
                    df_chart[col] = (df_chart[col] - min_val) / (max_val - min_val)
                else:
                    df_chart[col] = 0 # Zapobieganie dzieleniu przez zero
            else:
                std_val = df_chart[col].std()
                if std_val != 0:
                    df_chart[col] = (df_chart[col] - df_chart[col].mean()) / std_val
                else:
                    df_chart[col] = 0

# Sortowanie dla liniowego/punktowego
if not df_chart.empty and x_col in df_chart.columns and pd.api.types.is_numeric_dtype(df_chart[x_col]):
    df_chart = df_chart.sort_values(x_col)

# Zapisanie aktualnych danych i konfiguracji do stanu sesji dla funkcji eksportu
st.session_state.df_chart = df_chart
st.session_state.x_col = x_col
st.session_state.y_cols = y_cols
st.session_state.chart_config = {
    'type': chart_type, 'line_style': line_style, 'width': line_width, 'markers': show_markers,
    'log_x': log_x, 'log_y': log_y, 'grid': show_grid,
    'xlim': (xm, xM), 'ylim': (ym, yM),
    'title': "", # Tytuł jest zarządzany poniżej w col_plot
    'x_label': x_label,
    'y_label': y_label
}

# --- KOLUMNY: NARZĘDZIA (LEWO) + WYKRES (PRAWO) ---
col_tools, col_plot = st.columns([1, 3]) # ODWRÓCONA KOLEJNOŚĆ I ZMIENIONE PROPORCJE

with col_tools:
    st.subheader("🛠️ Edycja Elementów")
    
    # A. ZARZĄDZANIE ADNOTACJAMI
    with st.expander("📝 Adnotacje", expanded=True):
        # Domyślne współrzędne (środek danych)
        def_x = float(df_chart[x_col].mean()) if not df_chart.empty and pd.api.types.is_numeric_dtype(df_chart[x_col]) else 0.0
        def_y = float(df_chart[y_cols[0]].mean()) if not df_chart.empty and len(y_cols)>0 and pd.api.types.is_numeric_dtype(df_chart[y_cols[0]]) else 0.0
        
        # Formularz dodawania
        with st.form("new_note"):
            st.write("Dodaj nową:")
            c1_n, c2_n = st.columns(2)
            new_x = c1_n.number_input("Poz X", value=def_x, key="nx", format="%.2f")
            new_y = c2_n.number_input("Poz Y", value=def_y, key="ny", format="%.2f")
            new_txt = st.text_input("Tekst", "Punkt A")
            
            if st.form_submit_button("➕ Dodaj Adnotację"):
                st.session_state.annotations.append({'x': new_x, 'y': new_y, 'text': new_txt})
                st.rerun()

        # Lista edycji istniejących
        if st.session_state.annotations:
            st.write("**Edytuj istniejące:**")
            # Używamy st.data_editor do edycji listy słowników - wygodniej
            edited_notes = st.data_editor(
                st.session_state.annotations,
                column_config={
                    "x": st.column_config.NumberColumn("Poz X", format="%.2f"),
                    "y": st.column_config.NumberColumn("Poz Y", format="%.2f"),
                    "text": st.column_config.TextColumn("Tekst"),
                },
                num_rows="dynamic",
                hide_index=True,
                key="notes_editor"
            )
            # Aktualizacja tylko, jeśli dane się zmieniły
            if edited_notes != st.session_state.annotations:
                 st.session_state.annotations = edited_notes
                 st.rerun() # Wymuszamy rerun, aby adnotacje na wykresie się zaktualizowały

    # B. LINIE REFERENCYJNE
    with st.expander("📏 Linie Referencyjne", expanded=True):
        with st.form("new_line"):
            l_ax = st.selectbox("Oś", ["X", "Y"])
            l_val = st.number_input("Wartość", value=0.0)
            if st.form_submit_button("➕ Dodaj Linię"):
                st.session_state.ref_lines.append({
                    'axis': l_ax, 
                    'value': l_val, 
                    'color': DEFAULT_REF_LINE_COLOR, 
                    'style': DEFAULT_REF_LINE_STYLE, 
                    'width': DEFAULT_REF_LINE_WIDTH
                })
                st.rerun()
        
        # Lista edycji (Użycie data_editor jest bardziej Streamlitowe i łatwiejsze)
        if st.session_state.ref_lines:
            st.write("**Edytuj istniejące:**")
            edited_lines = st.data_editor(
                st.session_state.ref_lines,
                column_config={
                    "axis": st.column_config.SelectboxColumn("Oś", options=["X", "Y"]),
                    "value": st.column_config.NumberColumn("Wartość", format="%.2f"),
                    "color": st.column_config.ColorPickerColumn("Kolor"),
                    "style": st.column_config.SelectboxColumn("Styl", options=REF_LINE_STYLES, default="Ciągła (-)"),
                    "width": st.column_config.NumberColumn("Grubość", min_value=0.5, max_value=5.0, step=0.5),
                },
                num_rows="dynamic",
                hide_index=True,
                key="lines_editor"
            )
            
            # Wymiana stylu tekstowego na symbol Matplotlib
            for line in edited_lines:
                if line['style'] in LINE_STYLE_MAP:
                    line['style'] = LINE_STYLE_MAP[line['style']]
            
            if edited_lines != st.session_state.ref_lines:
                st.session_state.ref_lines = edited_lines
                st.rerun() # Wymuszamy rerun, aby linie na wykresie się zaktualizowały

with col_plot:
    # Tytuł Wykresu
    chart_title = st.text_input("Tytuł Wykresu", "Mój Wykres", label_visibility="collapsed", placeholder="Wpisz tytuł...")
    st.session_state.chart_config['title'] = chart_title
    
    # Generowanie i wyświetlanie wykresu
    fig_screen = create_chart_figure(df_chart, x_col, y_cols, st.session_state.chart_config, export_mode=None)
    st.pyplot(fig_screen)

    st.divider()
    
    # --- SEKCJA EKSPORTU ---
    st.subheader("💾 Eksport")
    st.markdown("Pamiętaj, że adnotacje i linie ref. są zachowane w każdym formacie, ale styl (kolor tła/linii) jest dostosowany do trybu.")
    
    e_col1, e_col2, e_col3 = st.columns(3)
    
    file_prefix = chart_title.replace(" ", "_").lower() if chart_title else "wykres"
    
    with e_col1:
        st.markdown("**1. Ekran (Ciemny)**")
        get_image_download_link(fig_screen, "png", None, "Pobierz PNG", file_prefix)
        get_image_download_link(fig_screen, "pdf", None, "Pobierz PDF", file_prefix)
        
    with e_col2:
        st.markdown("**2. Druk (Kolor)**")
        get_image_download_link(fig_screen, "png", "print_color", "Pobierz PNG", file_prefix)
        get_image_download_link(fig_screen, "pdf", "print_color", "Pobierz PDF", file_prefix)

    with e_col3:
        st.markdown("**3. Druk (Cz-B)**")
        get_image_download_link(fig_screen, "png", "print_bw", "Pobierz PNG", file_prefix)
        get_image_download_link(fig_screen, "pdf", "print_bw", "Pobierz PDF", file_prefix)
