import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import io # Do obsługi zapisywania plików w pamięci

# --- 1. KONFIGURACJA I STAŁE ---
st.set_page_config(layout="wide", page_title="Chart Master Web")

REF_LINE_STYLES = ["Ciągła (-)", "Kropkowana (:)", "Przerywana (--)", "Kreska-Kropka (-.)"]
LINE_STYLE_MAP = {"Kropkowana (:)": ":", "Przerywana (--)": "--", "Ciągła (-)": "-", "Kreska-Kropka (-.)": "-."}
DEFAULT_REF_LINE_STYLE = "Ciągła (-)" 
DEFAULT_REF_LINE_WIDTH = 1.0
DEFAULT_REF_LINE_COLOR = "#AAAAAA"
DARK_BACKGROUND = "#2A2A2A"
SERIES_NAMES = [f"Y{i+1}" for i in range(10)]

# --- 2. ZARZĄDZANIE STANEM ---

# Inicjalizacja stanu bazowego dla dynamicznej tabeli
if 'num_series' not in st.session_state:
    st.session_state.num_series = 1
if 'num_points' not in st.session_state:
    st.session_state.num_points = 5

if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame({"X": [float(i+1) for i in range(st.session_state.num_points)], "Y1": [10.0, 20.0, 15.0, 25.0, 30.0]})

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
            uploaded_file.seek(0)
            try:
                df = pd.read_csv(uploaded_file, sep=None, engine='python')
            except:
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file)
        
        # Zmiana nazw kolumn na stringi
        df.columns = [str(c) for c in df.columns]
        
        # Ograniczenie kolumn Y do max 10
        if len(df.columns) > 11:
            df = df.iloc[:, :11]

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
    
    # === KONFIGURACJA OSI (0,0) ===
    if config['origin_at_zero']:
        # Ustawienie osi na przecinanie w (0,0)
        ax.spines['left'].set_position('zero')
        ax.spines['bottom'].set_position('zero')
        # Ukrycie górnej i prawej osi dla "czystszego" wykresu
        ax.spines['right'].set_visible(False)
        ax.spines['top'].set_visible(False)
        # Kolory osi
        for spine in ax.spines.values():
            spine.set_color(text_color)
    else:
        # Standardowe osie
        ax.spines['right'].set_visible(True)
        ax.spines['top'].set_visible(True)
        # Ustawienie kolorów dla standardowych osi
        for spine in ax.spines.values():
            spine.set_color(text_color)


    # Style osi (dla wszystkich stylów)
    ax.tick_params(colors=text_color)
    ax.yaxis.label.set_color(text_color)
    ax.xaxis.label.set_color(text_color)
    ax.title.set_color(text_color)

    # 1. DANE
    color_cycle = plt.rcParams['axes.prop_cycle'].by_key()['color']
    
    for i, col in enumerate(y_cols):
        if col not in df.columns: continue
        
        # Pobranie konfiguracji (jeśli brak, użyj domyślnej)
        cfg = st.session_state.series_config.get(col, {
            'color': color_cycle[i % len(color_cycle)], 
            'alias': col
        })
        alias = cfg['alias']
        
        if export_mode == 'print_bw':
            color = 'black'
            linestyle = ['-', '--', ':', '-.'][i % 4] # Różne linie dla B&W
        else:
            color = cfg['color']
            # Użyj symbolu Matplotlib, nie tekstu
            linestyle = LINE_STYLE_MAP.get(config['line_style'], '-') 

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
        # Konwersja przyjaznej nazwy na symbol Matplotlib
        l_style = LINE_STYLE_MAP.get(line.get('style', DEFAULT_REF_LINE_STYLE), '-')
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
    # Generujemy NOWĄ figurę specjalnie dla eksportu
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
                # W przypadku wczytania pliku, resetujemy stan i dostosowujemy rozmiar
                st.session_state.df = df_new
                st.session_state.annotations = []
                st.session_state.ref_lines = []
                st.session_state.series_config = {}
                st.session_state.num_series = len(df_new.columns) - 1 if len(df_new.columns) > 0 else 1
                st.session_state.num_points = len(df_new)
                st.success("Wczytano plik! Dostosuj kolumny/punkty obok.")
    
    # --- 2. Konfiguracja Danych ---
    st.header("2. Konfiguracja Danych")
    
    # Użycie selectbox (od 1 do 10) dla liczby serii
    num_series_input = st.selectbox("Liczba Serii (Y)", list(range(1, 11)), index=st.session_state.num_series - 1, key='sel_num_series')
    
    # Użycie slidera dla liczby punktów
    num_points_input = st.slider("Liczba Punktów Danych", 1, 50, st.session_state.num_points, key='sel_num_points')
    
    # Dynamiczna aktualizacja DF na podstawie nowej konfiguracji rozmiaru
    if num_series_input != st.session_state.num_series or num_points_input != st.session_state.num_points:
        st.session_state.num_series = num_series_input
        st.session_state.num_points = num_points_input

        current_cols = ['X'] + SERIES_NAMES[:st.session_state.num_series]
        old_df = st.session_state.df
        
        # Tworzenie nowej ramki danych, przenosząc stare dane
        new_df = pd.DataFrame(index=range(st.session_state.num_points))
        
        # Transfer i inicjalizacja danych
        for col in current_cols:
            if col in old_df.columns:
                series_data = old_df[col].head(st.session_state.num_points)
            else:
                # Domyślne dane dla nowej kolumny
                series_data = np.zeros(st.session_state.num_points)
            
            # Wypełnienie lub skrócenie serii do nowej liczby punktów
            if len(series_data) < st.session_state.num_points:
                 series_data = pd.concat([series_data, pd.Series(np.zeros(st.session_state.num_points - len(series_data)))], ignore_index=True)
            new_df[col] = series_data.head(st.session_state.num_points).fillna(0).astype(float)
        
        # Automatyczne uzupełnienie kolumny X jeśli pusta
        if (new_df['X'] == 0).all():
             new_df['X'] = np.arange(1, st.session_state.num_points + 1).astype(float)
            
        st.session_state.df = new_df
        st.rerun()

    # Zabezpieczenie przed brakiem danych
    if st.session_state.df.empty:
        st.warning("Brak danych. Dodaj punkty danych.")
        st.stop()
        
    # Ustalenie kolumn dla wykresu
    x_col = 'X'
    y_cols = SERIES_NAMES[:st.session_state.num_series]


    st.header("3. Opcje Wykresu")
    chart_type = st.selectbox("Typ", ["Liniowy", "Punktowy", "Słupkowy"], key='sel_type')
    
    # Opcja dla (0,0)
    origin_at_zero = st.checkbox("Oś w Punkcie (0,0)", False, key='sel_origin')
    
    # Styl Linii
    c1, c2 = st.columns(2)
    line_style = c1.selectbox("Styl Linii", REF_LINE_STYLES, key='sel_l_style')
    line_width = c2.slider("Grubość", 0.5, 5.0, 2.0, key='sel_l_width')
    show_markers = st.checkbox("Pokaż Markery (Punkty)", True, key='sel_markers')
    show_grid = st.checkbox("Siatka", True, key='sel_grid')

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

# 1. EDYTOR DANYCH (Tryb ręczny - Stabilny)
if data_source == "Wpisz Ręcznie":
    with st.expander("✏️ Edytor Danych", expanded=True):
        st.write(f"Wprowadź dane dla **{st.session_state.num_points}** punktów i **{st.session_state.num_series}** serii.")
        
        # Używamy st.form, aby uniknąć restartów przy wpisywaniu wartości
        with st.form("manual_data_form"):
            
            # Nagłówki
            header_cols = st.columns([1] + [1] * st.session_state.num_series)
            header_cols[0].markdown("**X**")
            for i in range(st.session_state.num_series):
                header_cols[i+1].markdown(f"**{y_cols[i]}**")
                
            new_df_data = {}

            # Wiersze inputów
            for r in range(st.session_state.num_points):
                row_cols = st.columns([1] + [1] * st.session_state.num_series)
                
                # Kolumna X
                new_x = row_cols[0].number_input(
                    f"X_{r}", 
                    value=float(st.session_state.df.loc[r, x_col]), 
                    key=f"data_X_{r}", 
                    format="%.2f", 
                    label_visibility="collapsed"
                )
                new_df_data[(r, x_col)] = new_x

                # Kolumny Y
                for c_idx in range(st.session_state.num_series):
                    y_col = y_cols[c_idx]
                    new_y = row_cols[c_idx + 1].number_input(
                        f"{y_col}_{r}", 
                        value=float(st.session_state.df.loc[r, y_col]), 
                        key=f"data_{y_col}_{r}", 
                        format="%.2f", 
                        label_visibility="collapsed"
                    )
                    new_df_data[(r, y_col)] = new_y

            if st.form_submit_button("Zastosuj Wprowadzone Dane (Wymagane!)"):
                # Aktualizacja DataFrame w session state
                temp_df = st.session_state.df.copy()
                for (r, col), val in new_df_data.items():
                    temp_df.loc[r, col] = val
                st.session_state.df = temp_df
                st.success("Dane zaktualizowane pomyślnie.")
                st.rerun() 
            
            st.info("UWAGA: Aby zmiany zostały zastosowane, **MUSISZ** kliknąć przycisk 'Zastosuj Wprowadzone Dane'.")


# Konfiguracja do rysowania (Zbieranie wszystkich ustawień)
chart_config = {
    'type': chart_type, 'line_style': line_style, 'width': line_width, 'markers': show_markers,
    'log_x': log_x, 'log_y': log_y, 'grid': show_grid,
    'xlim': (xm, xM), 'ylim': (ym, yM),
    'title': "", 
    'x_label': x_label,
    'y_label': y_label,
    'origin_at_zero': origin_at_zero
}

# Zapisanie aktualnych danych i konfiguracji do stanu sesji dla funkcji eksportu
st.session_state.df_chart = st.session_state.df.copy()
st.session_state.x_col = x_col
st.session_state.y_cols = y_cols
st.session_state.chart_config = chart_config

# --- KOLUMNY: NARZĘDZIA (LEWO) + WYKRES (PRAWO) ---
col_tools, col_plot = st.columns([1, 3]) 

with col_tools:
    st.subheader("🛠️ Edycja Elementów")

    # C. KONFIGURACJA SERII (KOLORY I ALIASY)
    with st.expander("🎨 Konfiguracja Serii (Y)", expanded=True):
        default_colors = plt.rcParams['axes.prop_cycle'].by_key()['color']
        
        for i, col in enumerate(y_cols):
            # Ustawienie domyślnej konfiguracji, jeśli jej brakuje
            if col not in st.session_state.series_config:
                 st.session_state.series_config[col] = {
                     'color': default_colors[i % len(default_colors)], 
                     'alias': col
                 }
            
            cfg = st.session_state.series_config[col]
            
            st.caption(f"Seria **{col}** (Wykres: {cfg['alias']})")
            c1_s, c2_s = st.columns([1, 2])
            
            # Kolor
            new_color = c1_s.color_picker("Kolor", cfg['color'], key=f"color_{col}", label_visibility="collapsed")
            
            # Alias
            new_alias = c2_s.text_input("Nazwa", cfg['alias'], key=f"alias_{col}", label_visibility="collapsed")
            
            # Update if changed
            if new_color != cfg['color'] or new_alias != cfg['alias']:
                st.session_state.series_config[col]['color'] = new_color
                st.session_state.series_config[col]['alias'] = new_alias
                st.rerun() # Wymuszamy rerun, aby kolor/alias na wykresie się zaktualizował

    # A. ZARZĄDZANIE ADNOTACJAMI (Użycie data_editor jest stabilne dla małych list słowników)
    with st.expander("📝 Adnotacje", expanded=True):
        if not st.session_state.df_chart.empty and len(y_cols)>0:
            def_x = float(st.session_state.df_chart[x_col].mean())
            def_y = float(st.session_state.df_chart[y_cols[0]].mean())
        else:
             def_x, def_y = 0.0, 0.0
        
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
            st.write("**Edytuj/Usuń:**")
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
            if edited_notes != st.session_state.annotations:
                 st.session_state.annotations = edited_notes
                 st.rerun() 
                 
    # B. LINIE REFERENCYJNE (Użycie data_editor jest stabilne dla małych list słowników)
    with st.expander("📏 Linie Referencyjne", expanded=True):
        with st.form("new_line"):
            l_ax = st.selectbox("Oś", ["X", "Y"])
            l_val = st.number_input("Wartość", value=0.0)
            l_style = st.selectbox("Styl", REF_LINE_STYLES, index=0)
            
            if st.form_submit_button("➕ Dodaj Linię"):
                st.session_state.ref_lines.append({
                    'axis': l_ax, 
                    'value': l_val, 
                    'color': DEFAULT_REF_LINE_COLOR, 
                    'style': l_style, # Przechowujemy tekstową nazwę stylu
                    'width': DEFAULT_REF_LINE_WIDTH
                })
                st.rerun()
        
        # Lista edycji
        if st.session_state.ref_lines:
            st.write("**Edytuj/Usuń:**")
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
            
            if edited_lines != st.session_state.ref_lines:
                st.session_state.ref_lines = edited_lines
                st.rerun()

with col_plot:
    # Tytuł Wykresu
    chart_title = st.text_input("Tytuł Wykresu", "Mój Wykres", label_visibility="collapsed", placeholder="Wpisz tytuł...")
    st.session_state.chart_config['title'] = chart_title
    
    # Generowanie i wyświetlanie wykresu
    fig_screen = create_chart_figure(st.session_state.df_chart, x_col, y_cols, st.session_state.chart_config, export_mode=None)
    st.pyplot(fig_screen)

    st.divider()
    
    # --- SEKCJA EKSPORTU ---
    st.subheader("💾 Eksport (PNG / PDF)")
    
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
