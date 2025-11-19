import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import io

# --- 1. KONFIGURACJA I STAŁE ---
st.set_page_config(layout="wide", page_title="Chart Master Web")

REF_LINE_STYLES = ["Ciągła (-)", "Kropkowana (:)", "Przerywana (--)", "Kreska-Kropka (-.)"]
LINE_STYLE_MAP = {"Kropkowana (:)": ":", "Przerywana (--)": "--", "Ciągła (-)": "-", "Kreska-Kropka (-.)": "-."}
WIDTH_OPTIONS = [1.0, 2.0, 3.0, 4.0, 5.0] 
DEFAULT_REF_LINE_STYLE = "Ciągła (-)" 
DEFAULT_REF_LINE_WIDTH = 1.0 
DEFAULT_REF_LINE_COLOR = "#AAAAAA"
DARK_BACKGROUND = "#2A2A2A"
SERIES_NAMES = [f"Y{i+1}" for i in range(10)] 
POINTS_OPTIONS = list(range(1, 51))

# UPROSZCZONA STRUKTURA SYMBOLI
SPECIAL_SYMBOLS = {
    "Indeksy": ["¹", "²", "³", "⁴", "⁵", "⁶", "⁷", "⁸", "⁹", "⁰", "₁", "₂", "₃", "₄", "₅", "₆", "₇", "₈", "₉", "₀"],
    "Grecki": ["α", "β", "γ", "δ", "ε", "ζ", "η", "θ", "λ", "μ", "π", "ρ", "σ", "τ", "φ", "ω"],
    "Fizyczne": ["°C", "°", "Δ", "•", "Ω", "μ", "√", "=", "≥", "≤", "≈"],
    "Matematyczne": ["×", "÷", "∞", "∑", "∫", "%", "±", "≠"]
}


# --- 2. ZARZĄDZANIE STANEM ---

if 'num_series' not in st.session_state:
    st.session_state.num_series = 1
# Domyślnie 1 punkt
if 'num_points' not in st.session_state:
    st.session_state.num_points = 1

if 'df' not in st.session_state:
    # Domyślna DF ma 1 punkt
    st.session_state.df = pd.DataFrame({"X": [1.0], "Y1": [10.0]})

if 'annotations' not in st.session_state:
    st.session_state.annotations = []
if 'ref_lines' not in st.session_state:
    st.session_state.ref_lines = []
if 'series_config' not in st.session_state:
    st.session_state.series_config = {}

# --- 3. FUNKCJE POMOCNICZE ---

def process_uploaded_file(uploaded_file):
    """
    Obsługa CSV, Excel i TXT: ustandaryzowanie kolumn na 'X', 'Y1', 'Y2', ...
    """
    try:
        if uploaded_file.name.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(uploaded_file)
        else:
            uploaded_file.seek(0)
            try:
                # Próba odczytu z automatycznym wykrywaniem separatora
                df = pd.read_csv(uploaded_file, sep=None, engine='python')
            except:
                # Awaryjne odczytanie z automatycznym wykrywaniem spacji/tabulacji
                uploaded_file.seek(0)
                try:
                    df = pd.read_csv(uploaded_file, delim_whitespace=True)
                except:
                    # Ostateczna próba
                    uploaded_file.seek(0)
                    df = pd.read_csv(uploaded_file, sep=',')
        
        df.columns = [str(c) for c in df.columns]

        # Wyrzucenie wierszy, które są w całości puste lub nie są liczbowe
        df = df.replace(r'^\s*$', np.nan, regex=True).dropna(how='all')
        
        if df.shape[1] < 2:
             st.error("Wczytany plik powinien zawierać co najmniej dwie kolumny danych (X i Y).")
             return None
             
        if df.shape[1] > 11:
            df = df.iloc[:, :11]

        # Konwersja na float i ustandaryzowanie nazw kolumn
        new_cols = {}
        for i, col in enumerate(df.columns):
            if i == 0:
                new_col_name = 'X'
            else:
                new_col_name = f'Y{i}'
            
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
            new_cols[col] = new_col_name
        
        df = df.rename(columns=new_cols)

        # Usunięcie wierszy, które mają same zera w kolumnach Y (po konwersji)
        df = df[~(df.filter(regex='^Y\d+$') == 0).all(axis=1)].reset_index(drop=True)
        
        if df.empty:
             st.error("Plik wczytany, ale nie zawiera żadnych poprawnych danych liczbowych po oczyszczeniu.")
             return None

        return df
    except Exception as e:
        st.error(f"Błąd formatu pliku lub parsowania: {e}. Upewnij się, że dane są liczbowe i rozdzielone przecinkiem, średnikiem lub spacją/tabulatorem.")
        return None

def create_chart_figure(df, x_col, y_cols, config, export_mode=None):
    """Generuje figurę Matplotlib."""
    
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
        ax.spines['left'].set_position('zero')
        ax.spines['bottom'].set_position('zero')
        ax.spines['right'].set_visible(False)
        ax.spines['top'].set_visible(False)
        for spine in ax.spines.values():
            spine.set_color(text_color)
    else:
        ax.spines['right'].set_visible(True)
        ax.spines['top'].set_visible(True)
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
        
        cfg = st.session_state.series_config.get(col, {
            'color': color_cycle[i % len(color_cycle)], 
            'alias': col
        })
        alias = cfg['alias']
        
        if export_mode == 'print_bw':
            color = 'black'
            linestyle = ['-', '--', ':', '-.'][i % 4] 
        else:
            color = cfg['color']
            linestyle = LINE_STYLE_MAP.get(config['line_style'], '-') 

        # Logika dla 1 punktu i/lub braku markerów
        if config['type'] == "Liniowy":
            if len(df) <= 1:
                # Zawsze pokazujemy marker dla pojedynczego punktu w trybie liniowym, aby coś było widać
                ax.plot(df[x_col], df[col], label=alias, color=color, 
                        linestyle='None', linewidth=config['width'], 
                        marker='o') 
            else:
                ax.plot(df[x_col], df[col], label=alias, color=color, 
                        linestyle=linestyle, linewidth=config['width'], 
                        marker='o' if config['markers'] else None)
        elif config['type'] == "Punktowy":
            ax.scatter(df[x_col], df[col], label=alias, color=color, s=30)
        elif config['type'] == "Słupkowy":
            ax.bar(df[x_col], df[col], label=alias, color=color, alpha=0.7)

    # 2. LINIE REFERENCYJNE
    for line in st.session_state.ref_lines:
        l_color = 'black' if export_mode == 'print_bw' else line.get('color', DEFAULT_REF_LINE_COLOR)
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

def get_image_download_link(fig, format, mode, label, file_prefix):
    """Obsługuje eksport wykresu."""
    buf = io.BytesIO()
    fig_export = create_chart_figure(st.session_state.df_chart, 
                                     st.session_state.x_col, 
                                     st.session_state.y_cols, 
                                     st.session_state.chart_config, 
                                     export_mode=mode)
    fig_export.savefig(buf, format=format, dpi=300)
    plt.close(fig_export) 
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
    st.header("1. Źródło Danych i Rozmiar")
    
    is_manual_mode = (st.session_state.get('data_source', "Wpisz Ręcznie") == "Wpisz Ręcznie")

    # 1. ŹRÓDŁO DANYCH
    with st.container(border=True):
        st.subheader("Opcje Danych")
        data_source = st.radio("Wybierz tryb:", ["Wpisz Ręcznie", "Wgraj Plik"], horizontal=True, key='data_source')
        
        if data_source == "Wgraj Plik":
            uploaded_file = st.file_uploader("Obsługuje: Excel, CSV, TXT", type=['csv', 'txt', 'xlsx', 'xls'])
            if uploaded_file:
                if 'last_upload_hash' not in st.session_state or st.session_state.last_upload_hash != uploaded_file.file_id:
                    df_new = process_uploaded_file(uploaded_file)
                    if df_new is not None: 
                        st.session_state.df = df_new
                        st.session_state.annotations = []
                        st.session_state.ref_lines = []
                        st.session_state.series_config = {}
                        
                        y_cols_count = len([col for col in df_new.columns if col.startswith('Y')])
                        st.session_state.num_series = y_cols_count
                        st.session_state.num_points = len(df_new)
                        
                        st.session_state.last_upload_hash = uploaded_file.file_id
                        st.success(f"Wczytano plik! ({st.session_state.num_points} punktów, {st.session_state.num_series} serii). Wykres został zaktualizowany.")
                        st.rerun() 

    # 2. KONFIGURACJA ROZMIARU
    with st.container(border=True):
        st.subheader("Rozmiar Danych")
        
        if is_manual_mode:
            c_size1, c_size2 = st.columns(2)
            
            num_series_input = c_size1.selectbox(
                "Liczba Serii (Y)", 
                list(range(1, 11)), 
                index=st.session_state.num_series - 1, 
                key='sel_num_series'
            )
            
            try:
                current_index = POINTS_OPTIONS.index(st.session_state.num_points)
            except ValueError:
                current_index = POINTS_OPTIONS.index(1) 
                
            num_points_input = c_size2.selectbox(
                "Liczba Punktów (X)", 
                POINTS_OPTIONS, 
                index=current_index, 
                key='sel_num_points'
            )

            if num_series_input != st.session_state.num_series or num_points_input != st.session_state.num_points:
                st.session_state.num_series = num_series_input
                st.session_state.num_points = num_points_input

                current_cols = ['X'] + SERIES_NAMES[:st.session_state.num_series]
                old_df = st.session_state.df
                
                new_df = pd.DataFrame(index=range(st.session_state.num_points))
                
                for col in current_cols:
                    if col in old_df.columns:
                        series_data = old_df[col].astype(float)
                    else:
                        series_data = pd.Series(np.zeros(len(old_df))).astype(float)
                    
                    if len(series_data) < st.session_state.num_points:
                        missing_rows = st.session_state.num_points - len(series_data)
                        new_data = pd.concat([series_data, pd.Series(np.zeros(missing_rows)).astype(float)], ignore_index=True)
                    else:
                        new_data = series_data.head(st.session_state.num_points)
                    
                    new_df[col] = new_data.fillna(0).astype(float)
                
                if (new_df['X'] == 0).all() or len(new_df['X']) != st.session_state.num_points:
                    new_df['X'] = np.arange(1, st.session_state.num_points + 1).astype(float)
                    
                st.session_state.df = new_df
                st.rerun()
        else:
            st.caption("Rozmiar danych jest automatycznie ustalany na podstawie wczytanego pliku.")
            c_size1, c_size2 = st.columns(2)
            c_size1.metric("Liczba Serii (Y)", st.session_state.num_series)
            c_size2.metric("Liczba Punktów (X)", st.session_state.num_points)

    if st.session_state.df.empty:
        st.warning("Brak danych. Dodaj punkty danych.")
        st.stop()
        
    x_col = 'X'
    y_cols = [col for col in st.session_state.df.columns if col.startswith('Y')]


    st.header("2. Opcje Wykresu")
    
    # 2.1. TYP I ETYKIETY
    with st.container(border=True):
        st.subheader("Typ i Etykiety")
        chart_type = st.selectbox("Typ", ["Liniowy", "Punktowy", "Słupkowy"], key='sel_type')
        origin_at_zero = st.checkbox("Oś w Punkcie (0,0)", False, key='sel_origin')
        
        st.markdown("---")
        x_label = st.text_input("Etykieta Osi X", value="", placeholder="Kolumna X", key='sel_xlabel')
        y_label = st.text_input("Etykieta Osi Y", value="", placeholder="Wartość Y", key='sel_ylabel')
    
    # 2.2. GRANICE OSI
    with st.container(border=True):
        st.subheader("Granice Osi")
        st.caption("Wprowadź wartości graniczne (opcjonalnie)")
        c_min, c_max = st.columns(2)
        
        xm = c_min.number_input("X Min", value=None, key='sel_xmin', format="%f", label_visibility="collapsed", placeholder="X Min")
        xM = c_max.number_input("X Max", value=None, key='sel_xmax', format="%f", label_visibility="collapsed", placeholder="X Max")
        ym = c_min.number_input("Y Min", value=None, key='sel_ymin', format="%f", label_visibility="collapsed", placeholder="Y Min")
        yM = c_max.number_input("Y Max", value=None, key='sel_ymax', format="%f", label_visibility="collapsed", placeholder="Y Max")

    # 2.3. STYLE WYKRESU
    with st.container(border=True):
        st.subheader("Style Wykresu")
        c_s1, c_s2 = st.columns(2)
        
        line_style = c_s1.selectbox("Styl Linii", REF_LINE_STYLES, key='sel_l_style')
        line_width = c_s2.selectbox("Grubość Linii", WIDTH_OPTIONS, index=WIDTH_OPTIONS.index(2.0) if 2.0 in WIDTH_OPTIONS else 1, key='sel_l_width')
        
        c_log1, c_log2 = st.columns(2)
        log_x = c_log1.checkbox("Oś X Logarytmiczna", False, key='sel_log_x')
        log_y = c_log2.checkbox("Oś Y Logarytmiczna", False, key='sel_log_y')
        
        # Domyślnie markery wyłączone
        show_markers = st.checkbox("Pokaż Markery (Punkty)", False, key='sel_markers')
        show_grid = st.checkbox("Siatka", True, key='sel_grid')
    
    # ZNAKI SPECJALNE
    with st.expander("✨ Znaki Specjalne i Symbole"):
        
        st.markdown("**Kliknij w pole z symbolem, zaznacz go i skopiuj (Ctrl+C).**")
        st.markdown("---")
        
        for category, symbols in SPECIAL_SYMBOLS.items():
            st.caption(f"**{category}**")
            num_cols = 8 
            cols = st.columns([1] * num_cols) 
            col_index = 0
            for symbol in symbols:
                key = f"sym_input_{category}_{symbol}"
                
                # POPRAWKA: Jeśli użytkownik zmienił symbol, przywróć go
                if key in st.session_state and st.session_state[key] != symbol:
                    st.session_state[key] = symbol
                
                cols[col_index%num_cols].text_input(
                    symbol, 
                    value=symbol, 
                    key=key, 
                    label_visibility="collapsed", 
                    max_chars=len(symbol), 
                )
                col_index += 1


# --- GŁÓWNY OBSZAR: PRZYGOTOWANIE DANYCH ---

# Tworzenie obiektu konfiguracji do przekazania
chart_config = {
    'type': chart_type, 'line_style': line_style, 'width': line_width, 'markers': show_markers,
    'log_x': log_x, 'log_y': log_y, 'grid': show_grid,
    'xlim': (xm, xM), 'ylim': (ym, yM),
    'title': "", 
    'x_label': x_label,
    'y_label': y_label,
    'origin_at_zero': origin_at_zero
}

st.session_state.df_chart = st.session_state.df.copy()
st.session_state.x_col = x_col
st.session_state.y_cols = y_cols
st.session_state.chart_config = chart_config

# --- KOLUMNY: NARZĘDZIA (LEWO) + WYKRES (PRAWO) ---
col_tools, col_plot = st.columns([1, 3]) 

with col_tools:
    st.subheader("🛠️ Edycja Elementów Wykresu")
    st.markdown("---")

    # 1. EDYTOR DANYCH (Tryb ręczny) - POPRAWKA DLA MOBILNYCH
    if data_source == "Wpisz Ręcznie":
        with st.expander("✏️ Edytor Danych", expanded=True):
            st.write(f"Wprowadź dane dla **{st.session_state.num_points}** punktów i **{st.session_state.num_series}** serii.")
            
            with st.form("manual_data_form"):
                
                new_df_data = {}

                for r in range(st.session_state.num_points):
                    # Używamy kontenera z ramką dla jasnego grupowania wierszy (Punktów)
                    with st.container(border=True):
                        st.caption(f"**Punkt {r+1}**")
                        
                        # Utrzymujemy kolumny, ale z widocznymi etykietami (lepsze na mobilne)
                        row_cols = st.columns([1] + [1] * st.session_state.num_series)
                        
                        # Kolumna X
                        new_x = row_cols[0].number_input(
                            f"X: Punkt {r+1}", 
                            value=float(st.session_state.df.loc[r, x_col]), 
                            key=f"data_X_{r}", 
                            format="%f", 
                            label_visibility="visible", # Etykieta widoczna dla lepszej czytelności na urządzeniach mobilnych
                            help="Wartość na osi X"
                        )
                        new_df_data[(r, x_col)] = new_x

                        # Kolumny Y
                        for c_idx in range(st.session_state.num_series):
                            y_col = y_cols[c_idx]
                            new_y = row_cols[c_idx + 1].number_input(
                                f"{y_col}: Punkt {r+1}", 
                                value=float(st.session_state.df.loc[r, y_col]), 
                                key=f"data_{y_col}_{r}", 
                                format="%f", 
                                label_visibility="visible", # Etykieta widoczna dla lepszej czytelności na urządzeniach mobilnych
                                help=f"Wartość Y dla serii {y_col}"
                            )
                            new_df_data[(r, y_col)] = new_y

                if st.form_submit_button("Zastosuj Wprowadzone Dane"):
                    temp_df = st.session_state.df.copy()
                    for (r, col), val in new_df_data.items():
                        temp_df.loc[r, col] = val
                    st.session_state.df = temp_df
                    st.success("Dane zaktualizowane.")
                    st.rerun() 
                
                st.caption("Pamiętaj o kliknięciu przycisku powyżej, aby zapisać zmiany w tabeli.")
    
    # 2. KONFIGURACJA SERII (KOLORY I ALIASY)
    with st.expander("🎨 Konfiguracja Serii (Y)", expanded=True):
        default_colors = plt.rcParams['axes.prop_cycle'].by_key()['color']
        
        for i, col in enumerate(y_cols):
            if col not in st.session_state.series_config:
                 st.session_state.series_config[col] = {
                     'color': default_colors[i % len(default_colors)], 
                     'alias': col
                 }
            
            cfg = st.session_state.series_config[col]
            
            st.markdown(f"**{col}** (Alias: {cfg['alias']})")
            with st.container(border=True):
                c1_s, c2_s = st.columns([1, 2])
                
                new_color = c1_s.color_picker("Kolor", cfg['color'], key=f"color_{col}", label_visibility="collapsed")
                new_alias = c2_s.text_input("Alias", cfg['alias'], key=f"alias_{col}", label_visibility="collapsed")
            
            if new_color != cfg['color'] or new_alias != cfg['alias']:
                st.session_state.series_config[col]['color'] = new_color
                st.session_state.series_config[col]['alias'] = new_alias

    # 3. ADNOTACJE (Dodawanie)
    with st.expander("📝 Adnotacje", expanded=True):
        
        if not st.session_state.df_chart.empty and len(y_cols)>0:
            def_x = float(st.session_state.df_chart[x_col].mean())
            def_y = float(st.session_state.df_chart[y_cols[0]].mean())
        else:
             def_x, def_y = 0.0, 0.0
        
        # Formularz Dodawania
        with st.container(border=True):
            with st.form("new_note", clear_on_submit=True):
                st.markdown("**Dodaj Nową Adnotację**")
                c1_n, c2_n = st.columns(2)
                new_x = c1_n.number_input("Poz X", value=def_x, key="nx", format="%f") 
                new_y = c2_n.number_input("Poz Y", value=def_y, key="ny", format="%f")
                new_txt = st.text_input("Tekst Adnotacji", "Punkt A")
                
                if st.form_submit_button("➕ Dodaj Adnotację"):
                    st.session_state.annotations.append({'x': new_x, 'y': new_y, 'text': new_txt})
                    st.rerun()

        # Edytor/Usuwanie
        if st.session_state.annotations:
            st.markdown("---")
            st.subheader("Edytuj / Usuń")
            
            notes_to_keep = []
            
            for i, note in enumerate(st.session_state.annotations):
                
                with st.container(border=True): 
                    col_del, col_x, col_y = st.columns([0.5, 1.5, 1.5]) 
                    
                    if col_del.button("❌", key=f"an_del_{i}", help="Usuń adnotację"):
                        continue 
                        
                    new_x = col_x.number_input("X:", value=note['x'], key=f"an_x_{i}", format="%f", label_visibility="collapsed")
                    new_y = col_y.number_input("Y:", value=note['y'], key=f"an_y_{i}", format="%f", label_visibility="collapsed")
                    
                    st.text_input("Tekst:", value=note['text'], key=f"an_txt_{i}", label_visibility="collapsed")
                    
                updated_note = {'x': new_x, 'y': new_y, 'text': st.session_state[f"an_txt_{i}"]}
                notes_to_keep.append(updated_note)
                
            if len(notes_to_keep) != len(st.session_state.annotations):
                 st.session_state.annotations = notes_to_keep
                 st.rerun()
            else:
                 st.session_state.annotations = notes_to_keep 


    # 4. LINIE REFERENCYJNE (Dodawanie)
    with st.expander("📏 Linie Referencyjne", expanded=True):
        
        # Formularz Dodawania
        with st.container(border=True):
            with st.form("new_line", clear_on_submit=True):
                st.markdown("**Dodaj Nową Linię**")
                c_top1, c_top2 = st.columns(2)
                l_ax = c_top1.selectbox("Oś", ["X", "Y"], key="nl_ax")
                l_val = c_top2.number_input("Wartość", value=0.0, format="%f", key="nl_val") 
                
                c_bot1, c_bot2 = st.columns(2)
                l_style = c_bot1.selectbox("Styl", REF_LINE_STYLES, index=0, key="nl_style")
                l_width = c_bot2.selectbox("Grubość", WIDTH_OPTIONS, index=WIDTH_OPTIONS.index(1.0), key="nl_width")
                
                if st.form_submit_button("➕ Dodaj Linię"):
                    st.session_state.ref_lines.append({
                        'axis': l_ax, 
                        'value': l_val, 
                        'color': DEFAULT_REF_LINE_COLOR, 
                        'style': l_style,
                        'width': l_width 
                    })
                    st.rerun()
        
        # Edytor/Usuwanie
        if st.session_state.ref_lines:
            st.markdown("---")
            st.subheader("Edytuj / Usuń")
            
            lines_to_keep = []
            
            for i, line in enumerate(st.session_state.ref_lines):
                
                with st.container(border=True): 
                    # Wiersz 1: Usuwanie, Oś, Wartość
                    col_del, col_ax, col_val = st.columns([0.5, 1, 2])
                    
                    if col_del.button("❌", key=f"rl_del_{i}", help="Usuń linię"):
                        continue 
                    
                    new_ax = col_ax.selectbox("Oś", ["X", "Y"], index=0 if line['axis'] == 'X' else 1, key=f"rl_ax_{i}", label_visibility="collapsed")
                    new_val = col_val.number_input(f"{new_ax} Wartość:", value=line['value'], key=f"rl_val_{i}", format="%f", label_visibility="collapsed")
                    
                    # Wiersz 2: Kolor, Styl, Grubość
                    col_color, col_style, col_width = st.columns([1.5, 1.5, 1])
                    
                    new_color = col_color.color_picker("Kolor", line['color'], key=f"rl_color_{i}", label_visibility="collapsed")
                    
                    try:
                        style_index = REF_LINE_STYLES.index(line.get('style', DEFAULT_REF_LINE_STYLE))
                    except ValueError:
                        style_index = 0
                        
                    new_style = col_style.selectbox("Styl", REF_LINE_STYLES, index=style_index, key=f"rl_style_{i}", label_visibility="collapsed")
                    
                    try:
                        width_index = WIDTH_OPTIONS.index(line['width'])
                    except ValueError:
                        width_index = 0
                        
                    new_width = col_width.selectbox("Grubość", WIDTH_OPTIONS, index=width_index, key=f"rl_width_{i}", label_visibility="collapsed")
                
                updated_line = {
                    'axis': new_ax,
                    'value': new_val,
                    'color': new_color,
                    'style': new_style,
                    'width': new_width
                }
                lines_to_keep.append(updated_line)
                
            if len(lines_to_keep) != len(st.session_state.ref_lines):
                st.session_state.ref_lines = lines_to_keep
                st.rerun()
            else:
                 st.session_state.ref_lines = lines_to_keep 

with col_plot:
    st.markdown("## 📈 Wynikowy Wykres")
    
    # Tytuł Wykresu - umieszczony bliżej wykresu
    chart_title = st.text_input("Tytuł Wykresu", "Mój Wykres", key='chart_title_input', placeholder="Wpisz tytuł...", label_visibility="collapsed")
    st.session_state.chart_config['title'] = chart_title
    
    # Generowanie i wyświetlanie wykresu
    fig_screen = create_chart_figure(st.session_state.df_chart, x_col, y_cols, st.session_state.chart_config, export_mode=None)
    st.pyplot(fig_screen)

    st.divider()
    
    # --- SEKCJA EKSPORTU ---
    st.markdown("## 💾 Opcje Eksportu")
    
    e_col1, e_col2, e_col3 = st.columns(3)
    
    file_prefix = chart_title.replace(" ", "_").lower() if chart_title else "wykres"
    
    with e_col1:
        st.markdown("**1. Ekran (Ciemne Tło)**")
        get_image_download_link(fig_screen, "png", None, "Pobierz PNG", file_prefix)
        get_image_download_link(fig_screen, "pdf", None, "Pobierz PDF", file_prefix)
        
    with e_col2:
        st.markdown("**2. Druk (Jasne Tło / Kolor)**")
        get_image_download_link(fig_screen, "png", "print_color", "Pobierz PNG", file_prefix)
        get_image_download_link(fig_screen, "pdf", "print_color", "Pobierz PDF", file_prefix)

    with e_col3:
        st.markdown("**3. Druk (Czarno-Biały)**")
        get_image_download_link(fig_screen, "png", "print_bw", "Pobierz PNG", file_prefix)
        get_image_download_link(fig_screen, "pdf", "print_bw", "Pobierz PDF", file_prefix)
