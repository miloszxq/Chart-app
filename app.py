import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import io
from PIL import Image
from unittest.mock import MagicMock

# --- KONFIGURACJA BIBLIOTEK DLA EDYTORA PDF ---
try:
    from pypdf import PdfReader, PdfWriter 
    from reportlab.pdfgen import canvas as reportlab_canvas
    from reportlab.lib.pagesizes import letter
except ImportError:
    st.error("Błąd: Brakuje bibliotek pypdf lub reportlab. Zainstaluj je za pomocą: `pip install pypdf reportlab`")
    st.stop()


# --- 1. HOTFIX: NAPRAWA KOMPATYBILNOŚCI STREAMLIT 1.34+ (Potrzebny, jeśli używamy st_canvas, ale zostawiamy prewencyjnie) ---
import streamlit.elements.image as st_image
try:
    from streamlit.elements.lib.image_utils import image_to_url as original_image_to_url
except ImportError:
    # Alternatywa dla starszych/innych wersji Streamlit
    try:
        from streamlit.elements.image import image_to_url as original_image_to_url
    except ImportError:
        def original_image_to_url(*args, **kwargs): return "mock_url"

def patched_image_to_url(image, width, *args, **kwargs):
    # Patch zamienia int width na mock object, który jest oczekiwany przez nowsze wersje st.image_to_url
    if isinstance(width, int):
        mock_config = MagicMock()
        mock_config.width = width
        width = mock_config
    return original_image_to_url(image, width, *args, **kwargs)

try:
    st_image.image_to_url = patched_image_to_url
except AttributeError:
    pass


# --- KONFIGURACJA STRONY ---
st.set_page_config(layout="wide", page_title="Chart Master & PDF Studio")

# --- CSS (STYLIZACJA) ---
st.markdown("""
<style>
    /* Wygląd przycisków w lewym panelu */
    div[data-testid="stVerticalBlock"] > div > button {
        width: 100%;
        text-align: left;
        justify-content: flex-start;
        border-radius: 5px;
        margin-bottom: 2px;
    }
    /* Ukrycie stopki */
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# --- STAŁE ---
REF_LINE_STYLES = ["Ciągła (-)", "Kropkowana (:)", "Przerywana (--)", "Kreska-Kropka (-.)"]
LINE_STYLE_MAP = {"Kropkowana (:)": ":", "Przerywana (--)": "--", "Ciągła (-)": "-", "Kreska-Kropka (-.)": "-."}
WIDTH_OPTIONS = [1.0, 2.0, 3.0, 4.0, 5.0] 
DEFAULT_REF_LINE_STYLE = "Ciągła (-)" 
DEFAULT_REF_LINE_WIDTH = 1.0 
DEFAULT_REF_LINE_COLOR = "#AAAAAA"
DARK_BACKGROUND = "#2A2A2A"
SERIES_NAMES = [f"Y{i+1}" for i in range(10)] 
POINTS_OPTIONS = list(range(1, 51))

SPECIAL_SYMBOLS = {
    "Indeksy": ["¹", "²", "³", "⁴", "⁵", "⁶", "⁷", "⁸", "⁹", "⁰", "₁", "₂", "₃", "₄", "₅", "₆", "₇", "₈", "₉", "₀"],
    "Grecki": ["α", "β", "γ", "δ", "ε", "ζ", "η", "θ", "λ", "μ", "π", "ρ", "σ", "τ", "φ", "ω"],
    "Fizyczne": ["°C", "°", "Δ", "•", "Ω", "μ", "√", "=", "≥", "≤", "≈"],
    "Matematyczne": ["×", "÷", "∞", "∑", "∫", "%", "±", "≠"]
}

# ==========================================
# ZARZĄDZANIE STANEM (NAWIGACJA)
# ==========================================

if 'current_view' not in st.session_state:
    st.session_state.current_view = "home"

def go_home():
    st.session_state.current_view = "home"
    st.rerun()

def go_chart():
    st.session_state.current_view = "chart_creator"
    # Inicjalizacja stanu dla Kreatora Wykresów
    if 'num_series' not in st.session_state: st.session_state.num_series = 1
    if 'num_points' not in st.session_state: st.session_state.num_points = 10
    if 'df' not in st.session_state: st.session_state.df = pd.DataFrame({"X": np.arange(1, 11).astype(float), "Y1": np.random.rand(10) * 10})
    if 'annotations' not in st.session_state: st.session_state.annotations = []
    if 'ref_lines' not in st.session_state: st.session_state.ref_lines = []
    if 'series_config' not in st.session_state: 
        default_colors = plt.rcParams['axes.prop_cycle'].by_key()['color']
        st.session_state.series_config = {"Y1": {'color': default_colors[0], 'alias': 'Y1'}}
    if 'symbol_to_copy' not in st.session_state: st.session_state.symbol_to_copy = ""
    st.rerun()

def go_pdf():
    st.session_state.current_view = "pdf_editor"
    # Inicjalizacja stanu dla Edytora PDF
    if 'pdf_bytes' not in st.session_state: st.session_state.pdf_bytes = None
    if 'current_pdf_annotations' not in st.session_state: st.session_state.current_pdf_annotations = []
    if 'last_pdf' not in st.session_state: st.session_state.last_pdf = "dokument.pdf"
    st.rerun()


# ==========================================
# MODUŁ 1: KREATOR WYKRESÓW (Pełna wersja)
# ==========================================

def run_chart_creator():
    c_back, c_tit = st.columns([1, 10])
    with c_back:
        if st.button("🏠 Menu", use_container_width=True): go_home()
    with c_tit:
        st.subheader("📊 Kreator Wykresów")

    # Inicjalizacja stanu (tylko na wypadek bezpośredniego dostępu)
    if 'num_series' not in st.session_state: go_chart() 
    
    def process_uploaded_file(uploaded_file):
        """Wczytuje i przetwarza pliki danych (Excel, CSV, TXT)."""
        try:
            if uploaded_file.name.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(uploaded_file)
            else:
                uploaded_file.seek(0)
                # Próba wczytania z różnymi separatorami
                try: df = pd.read_csv(uploaded_file, sep=None, engine='python')
                except: 
                    uploaded_file.seek(0)
                    try: df = pd.read_csv(uploaded_file, delim_whitespace=True)
                    except: uploaded_file.seek(0); df = pd.read_csv(uploaded_file, sep=',')
            
            df.columns = [str(c) for c in df.columns]
            df = df.replace(r'^\s*$', np.nan, regex=True).dropna(how='all')
            if df.shape[1] < 2: return None
            if df.shape[1] > 11: df = df.iloc[:, :11] # Max 10 serii Y + 1 X

            new_cols = {}
            for i, col in enumerate(df.columns):
                if i == 0: new_col_name = 'X'
                else: new_col_name = f'Y{i}'
                # Konwersja na float i zastąpienie błędnych wartości zerem
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
                new_cols[col] = new_col_name
            
            df = df.rename(columns=new_cols)
            # Usuń wiersze, gdzie wszystkie kolumny Y są zerowe
            df = df[~(df.filter(regex=r'^Y\d+$') == 0).all(axis=1)].reset_index(drop=True)
            return df if not df.empty else None
        except Exception: 
            return None

    def create_chart_figure(df, x_col, y_cols, config, export_mode=None):
        """Generuje obiekt Matplotlib Figure na podstawie danych i konfiguracji."""
        if export_mode in ['print_color', 'print_bw']:
            bg_color, text_color, grid_color = "white", "black", "lightgray"
        else:
            bg_color, text_color, grid_color = DARK_BACKGROUND, "white", "gray"

        fig, ax = plt.subplots(figsize=(10, 6), facecolor=bg_color)
        ax.set_facecolor(bg_color)
        
        # Obsługa osi w punkcie (0,0)
        if config['origin_at_zero']:
            ax.spines['left'].set_position('zero')
            ax.spines['bottom'].set_position('zero')
            ax.spines['right'].set_visible(False)
            ax.spines['top'].set_visible(False)
        else:
            ax.spines['right'].set_visible(True)
            ax.spines['top'].set_visible(True)
        
        for spine in ax.spines.values(): spine.set_color(text_color)
        ax.tick_params(colors=text_color)
        ax.yaxis.label.set_color(text_color)
        ax.xaxis.label.set_color(text_color)
        ax.title.set_color(text_color)

        color_cycle = plt.rcParams['axes.prop_cycle'].by_key()['color']
        
        # Rysowanie serii
        for i, col in enumerate(y_cols):
            if col not in df.columns: continue
            cfg = st.session_state.series_config.get(col, {'color': color_cycle[i % len(color_cycle)], 'alias': col})
            alias = cfg['alias']
            
            if export_mode == 'print_bw':
                # W trybie B/W używamy tylko czarnego koloru i różnych stylów linii
                color, linestyle = 'black', ['-', '--', ':', '-.'][i % 4]
            else:
                color, linestyle = cfg['color'], LINE_STYLE_MAP.get(config['line_style'], '-')

            if config['type'] == "Liniowy":
                # Specjalna obsługa dla pojedynczego punktu
                if len(df) <= 1: 
                    ax.plot(df[x_col], df[col], label=alias, color=color, linestyle='None', linewidth=config['width'], marker='o')
                else: 
                    ax.plot(df[x_col], df[col], label=alias, color=color, linestyle=linestyle, linewidth=config['width'], marker='o' if config['markers'] else None)
            elif config['type'] == "Punktowy": 
                ax.scatter(df[x_col], df[col], label=alias, color=color, s=30)
            elif config['type'] == "Słupkowy": 
                ax.bar(df[x_col], df[col], label=alias, color=color, alpha=0.7)

        # Rysowanie linii referencyjnych
        for line in st.session_state.ref_lines:
            l_color = 'black' if export_mode == 'print_bw' else line.get('color', DEFAULT_REF_LINE_COLOR)
            l_style = LINE_STYLE_MAP.get(line.get('style', DEFAULT_REF_LINE_STYLE), '-')
            l_width = line.get('width', DEFAULT_REF_LINE_WIDTH)
            if line['axis'] == 'X': ax.axvline(line['value'], color=l_color, linestyle=l_style, linewidth=l_width)
            else: ax.axhline(line['value'], color=l_color, linestyle=l_style, linewidth=l_width)

        # Rysowanie adnotacji
        for note in st.session_state.annotations:
            n_color = 'black' if export_mode in ['print_color', 'print_bw'] else 'white'
            box_bg = 'white' if export_mode in ['print_color', 'print_bw'] else '#444444'
            ax.annotate(note['text'], xy=(note['x'], note['y']), xytext=(5, 5), textcoords="offset points", arrowprops=dict(arrowstyle="->", color=n_color), bbox=dict(boxstyle="round,pad=0.5", fc=box_bg, ec=n_color), color=n_color)

        # Ustawianie limitów osi
        if config['xlim'][0] is not None: ax.set_xlim(left=config['xlim'][0])
        if config['xlim'][1] is not None: ax.set_xlim(right=config['xlim'][1])
        if config['ylim'][0] is not None: ax.set_ylim(bottom=config['ylim'][0])
        if config['ylim'][1] is not None: ax.set_ylim(top=config['ylim'][1])
        
        # Skala logarytmiczna i siatka
        if config['log_x']: ax.set_xscale('log')
        if config['log_y']: ax.set_yscale('log')
        if config['grid']: ax.grid(True, linestyle='--', alpha=0.3, color=grid_color)
        else: ax.grid(False)
            
        # Tytuły i legendy
        ax.set_title(config['title'])
        ax.set_xlabel(config['x_label'] if config['x_label'] else x_col)
        ax.set_ylabel(config['y_label'] if config['y_label'] else "Wartość Y")
        if y_cols: ax.legend(facecolor=bg_color, labelcolor=text_color)
        fig.tight_layout()
        return fig

    def get_image_download_link(fig, format, mode, label, file_prefix):
        """Generuje przycisk pobierania dla wykresu."""
        buf = io.BytesIO()
        # Musimy ponownie wygenerować fig_export, aby zastosować styl eksportu (B/W, Kolor)
        fig_export = create_chart_figure(st.session_state.df_chart, st.session_state.x_col, st.session_state.y_cols, st.session_state.chart_config, export_mode=mode)
        fig_export.savefig(buf, format=format, dpi=300)
        plt.close(fig_export) 
        buf.seek(0)
        return st.download_button(label=label, data=buf, file_name=f"{file_prefix}_{mode}.{format}" if mode else f"{file_prefix}.{format}", mime=f"image/{format}")

    def set_symbol_to_copy(symbol):
        """Aktualizuje stan do skopiowania symbolu."""
        st.session_state.symbol_to_copy = symbol
        st.toast(f"Wybrano: {symbol}", icon='📋')

    with st.sidebar:
        st.header("1. Źródło Danych")
        is_manual_mode = (st.session_state.get('data_source', "Wpisz Ręcznie") == "Wpisz Ręcznie")
        
        with st.container(border=True):
            st.subheader("Opcje Danych")
            data_source = st.radio("Tryb:", ["Wpisz Ręcznie", "Wgraj Plik"], horizontal=True, key='data_source')
            if data_source == "Wgraj Plik":
                uploaded_file = st.file_uploader("Excel, CSV, TXT", type=['csv', 'txt', 'xlsx', 'xls'])
                if uploaded_file:
                    # Sprawdzenie, czy to ten sam plik, aby uniknąć zbędnego rerunu
                    if 'last_upload_hash' not in st.session_state or st.session_state.last_upload_hash != uploaded_file.file_id:
                        df_new = process_uploaded_file(uploaded_file)
                        if df_new is not None: 
                            st.session_state.df = df_new
                            # Reset stanu
                            st.session_state.annotations = []
                            st.session_state.ref_lines = []
                            st.session_state.series_config = {}
                            st.session_state.num_series = len([col for col in df_new.columns if col.startswith('Y')])
                            st.session_state.num_points = len(df_new)
                            st.session_state.last_upload_hash = uploaded_file.file_id
                            st.success(f"Wczytano! ({st.session_state.num_points} pkt).")
                            st.rerun()

        with st.container(border=True):
            st.subheader("Rozmiar")
            if is_manual_mode:
                c1, c2 = st.columns(2)
                # Upewnienie się, że index jest poprawny
                num_series_index = max(0, min(st.session_state.num_series - 1, 9))
                num_series_input = c1.selectbox("Serii (Y)", list(range(1, 11)), index=num_series_index, key='sel_num_series')
                
                try: cur_idx = POINTS_OPTIONS.index(st.session_state.num_points)
                except: cur_idx = 0
                num_points_input = c2.selectbox("Punktów (X)", POINTS_OPTIONS, index=cur_idx, key='sel_num_points')

                if num_series_input != st.session_state.num_series or num_points_input != st.session_state.num_points:
                    st.session_state.num_series = num_series_input
                    st.session_state.num_points = num_points_input
                    current_cols = ['X'] + SERIES_NAMES[:st.session_state.num_series]
                    
                    old_df = st.session_state.df
                    new_df = pd.DataFrame(index=range(st.session_state.num_points))
                    
                    # Dostosowanie rozmiaru i kolumn
                    for col in current_cols:
                        # Wczytaj istniejące dane lub utwórz nowe zerowe
                        series_data = old_df[col].astype(float) if col in old_df.columns else pd.Series(np.zeros(len(old_df))).astype(float)
                        
                        if len(series_data) < st.session_state.num_points:
                             # Powiększenie, dodanie zer
                             new_data = pd.concat([series_data, pd.Series(np.zeros(st.session_state.num_points - len(series_data))).astype(float)], ignore_index=True)
                        else: 
                            # Przycięcie
                            new_data = series_data.head(st.session_state.num_points)
                            
                        new_df[col] = new_data.fillna(0).astype(float)
                        
                    # Upewnij się, że kolumna X nie jest pusta (użyj indeksu jeśli jest)
                    if (new_df['X'] == 0).all(): new_df['X'] = np.arange(1, st.session_state.num_points + 1).astype(float)
                    
                    st.session_state.df = new_df
                    st.rerun()
            else:
                st.caption(f"Wczytano z pliku ({st.session_state.num_points} pkt, {st.session_state.num_series} serii).")

        x_col = 'X'
        y_cols = [col for col in st.session_state.df.columns if col.startswith('Y')]

        st.header("2. Opcje Wykresu")
        with st.container(border=True):
            st.subheader("Typ i Oznaczenia")
            chart_type = st.selectbox("Typ", ["Liniowy", "Punktowy", "Słupkowy"], key='sel_type')
            origin_at_zero = st.checkbox("Oś w (0,0)", False, key='sel_origin')
            st.markdown("---")
            x_label = st.text_input("Label X", "", placeholder="Kolumna X", key='sel_xlabel')
            y_label = st.text_input("Label Y", "", placeholder="Wartość Y", key='sel_ylabel')

        with st.container(border=True):
            st.subheader("Granice")
            c1, c2 = st.columns(2)
            xm = c1.number_input("X Min", value=None, format="%f")
            xM = c2.number_input("X Max", value=None, format="%f")
            ym = c1.number_input("Y Min", value=None, format="%f")
            yM = c2.number_input("Y Max", value=None, format="%f")

        with st.container(border=True):
            st.subheader("Skala i Styl")
            c1, c2 = st.columns(2)
            line_style = c1.selectbox("Linia", REF_LINE_STYLES, key='sel_l_style')
            # Upewnienie się, że index jest poprawny
            try: line_width_index = WIDTH_OPTIONS.index(st.session_state.get('chart_config', {}).get('width', 2.0))
            except ValueError: line_width_index = 1
            line_width = c2.selectbox("Grubość", WIDTH_OPTIONS, index=line_width_index, key='sel_l_width')
            c3, c4 = st.columns(2)
            log_x = c3.checkbox("Log X", False, key='sel_log_x')
            log_y = c4.checkbox("Log Y", False, key='sel_log_y')
            show_markers = st.checkbox("Markery (tylko liniowy)", False, key='sel_markers')
            show_grid = st.checkbox("Siatka", True, key='sel_grid')

        with st.expander("✨ Symbole (Kopiuj)"):
            st.markdown("Zaznacz i skopiuj:")
            st.text_area("Symbol:", st.session_state.symbol_to_copy, key="copy_area", height=35)
            for cat, syms in SPECIAL_SYMBOLS.items():
                st.caption(f"**{cat}**")
                cols = st.columns(6) 
                for i, s in enumerate(syms):
                    cols[i%6].button(s, key=f"s_{cat}_{s}", on_click=set_symbol_to_copy, args=(s,))

    # Zapis konfiguracji do stanu sesji
    chart_config = {'type': chart_type, 'line_style': line_style, 'width': line_width, 'markers': show_markers, 'log_x': log_x, 'log_y': log_y, 'grid': show_grid, 'xlim': (xm, xM), 'ylim': (ym, yM), 'title': "", 'x_label': x_label, 'y_label': y_label, 'origin_at_zero': origin_at_zero}
    st.session_state.df_chart = st.session_state.df.copy()
    st.session_state.x_col = x_col
    st.session_state.y_cols = y_cols
    st.session_state.chart_config = chart_config

    col_tools, col_plot = st.columns([1, 3])
    with col_tools:
        st.subheader("🛠️ Edycja")
        
        # --- EDYCJA DANYCH ---
        if data_source == "Wpisz Ręcznie":
            with st.expander("✏️ Dane", expanded=True):
                with st.form("data_form"):
                    new_df_data = {}
                    for r in range(st.session_state.num_points):
                        with st.container(border=True):
                            st.caption(f"**Pkt {r+1}**")
                            cols = st.columns([1] + [1]*len(y_cols))
                            new_x = cols[0].number_input(f"X {r+1}", value=float(st.session_state.df.loc[r, x_col]), key=f"dX_{r}", format="%f")
                            new_df_data[(r, x_col)] = new_x
                            for idx, yc in enumerate(y_cols):
                                ny = cols[idx+1].number_input(f"{yc} {r+1}", value=float(st.session_state.df.loc[r, yc]), key=f"d{yc}_{r}", format="%f")
                                new_df_data[(r, yc)] = ny
                    if st.form_submit_button("Zapisz Zmiany Danych"):
                        temp_df = st.session_state.df.copy()
                        for (r, c), v in new_df_data.items(): temp_df.loc[r, c] = v
                        st.session_state.df = temp_df
                        st.rerun()

        # --- KONFIGURACJA SERII ---
        with st.expander("🎨 Serie", expanded=True):
            default_colors = plt.rcParams['axes.prop_cycle'].by_key()['color']
            
            # Wyczyść konfigurację dla usuniętych serii
            st.session_state.series_config = {k:v for k,v in st.session_state.series_config.items() if k in y_cols}
            
            for i, col in enumerate(y_cols):
                if col not in st.session_state.series_config: st.session_state.series_config[col] = {'color': default_colors[i % len(default_colors)], 'alias': col}
                cfg = st.session_state.series_config[col]
                st.markdown(f"**{col}**")
                with st.container(border=True):
                    c1, c2 = st.columns([1, 2])
                    nc = c1.color_picker("Kol", cfg['color'], key=f"c_{col}")
                    na = c2.text_input("Nazwa", cfg['alias'], key=f"a_{col}")
                if nc != cfg['color'] or na != cfg['alias']:
                    st.session_state.series_config[col].update({'color': nc, 'alias': na})

        # --- ADNOTACJE ---
        with st.expander("📝 Adnotacje", expanded=True):
            # Ustalenie domyślnych wartości na średniej
            def_x = float(st.session_state.df_chart[x_col].mean()) if not st.session_state.df_chart.empty else 0.0
            def_y = float(st.session_state.df_chart[y_cols[0]].mean()) if not st.session_state.df_chart.empty and len(y_cols)>0 else 0.0
            
            with st.container(border=True):
                with st.form("add_note", clear_on_submit=True):
                    c1, c2 = st.columns(2)
                    nx = c1.number_input("X", value=def_x, format="%f")
                    ny = c2.number_input("Y", value=def_y, format="%f")
                    nt = st.text_input("Tekst Adnotacji")
                    if st.form_submit_button("➕ Dodaj Adnotację"):
                        st.session_state.annotations.append({'x': nx, 'y': ny, 'text': nt})
                        st.rerun()
            
            if st.session_state.annotations:
                st.markdown("---")
                notes_keep = []
                rerun = False
                st.caption("Kliknij ❌, aby usunąć lub edytuj i odśwież widok.")
                
                for i, n in enumerate(st.session_state.annotations):
                    with st.container(border=True):
                        cd, cx, cy = st.columns([0.5, 1.5, 1.5])
                        if cd.button("❌", key=f"rmn_{i}"): rerun = True; continue
                        
                        # Edytowalne pola adnotacji
                        nx_val = cx.number_input("X", value=n['x'], key=f"nx_{i}", format="%f", label_visibility="collapsed")
                        ny_val = cy.number_input("Y", value=n['y'], key=f"ny_{i}", format="%f", label_visibility="collapsed")
                        nt_val = st.text_input("Treść", value=n['text'], key=f"nt_{i}")
                        
                        notes_keep.append({'x': nx_val, 'y': ny_val, 'text': nt_val})
                        
                if rerun or len(notes_keep) != len(st.session_state.annotations) or any(n['x'] != st.session_state.annotations[i]['x'] for i, n in enumerate(notes_keep)):
                    st.session_state.annotations = notes_keep
                    if rerun: st.rerun() 
                else: 
                    st.session_state.annotations = notes_keep

        # --- LINIE REFERENCYJNE ---
        with st.expander("📏 Linie Ref.", expanded=True):
            with st.container(border=True):
                with st.form("add_line", clear_on_submit=True):
                    c1, c2 = st.columns(2)
                    lx = c1.selectbox("Oś", ["X", "Y"])
                    lv = c2.number_input("Wartość", 0.0, format="%f")
                    c3, c4, c5 = st.columns(3)
                    ls = c3.selectbox("Styl", REF_LINE_STYLES)
                    lw = c4.selectbox("Grubość", WIDTH_OPTIONS)
                    lc = c5.color_picker("Kolor", DEFAULT_REF_LINE_COLOR)
                    
                    if st.form_submit_button("➕ Dodaj Linię"):
                        st.session_state.ref_lines.append({'axis': lx, 'value': lv, 'color': lc, 'style': ls, 'width': lw})
                        st.rerun()
            
            if st.session_state.ref_lines:
                st.markdown("---")
                lines_keep = []
                rerun = False
                st.caption("Kliknij ❌, aby usunąć lub edytuj i odśwież widok.")
                
                for i, l in enumerate(st.session_state.ref_lines):
                    with st.container(border=True):
                        cd, ca, cv = st.columns([0.5, 1, 2])
                        if cd.button("❌", key=f"rml_{i}"): rerun = True; continue
                        
                        na = ca.selectbox("Oś", ["X", "Y"], index=0 if l['axis']=='X' else 1, key=f"la_{i}", label_visibility="collapsed")
                        nv = cv.number_input("Val", value=l['value'], key=f"lv_{i}", format="%f", label_visibility="collapsed")
                        
                        c1, c2, c3 = st.columns([1.5, 1.5, 1])
                        nc = c1.color_picker("Kol", l['color'], key=f"lc_{i}", label_visibility="collapsed")
                        ns = c2.selectbox("Styl", REF_LINE_STYLES, index=REF_LINE_STYLES.index(l.get('style', DEFAULT_REF_LINE_STYLE)) if l.get('style') in REF_LINE_STYLES else 0, key=f"ls_{i}", label_visibility="collapsed")
                        nw = c3.selectbox("Gr", WIDTH_OPTIONS, index=WIDTH_OPTIONS.index(l.get('width', 1.0)) if l.get('width') in WIDTH_OPTIONS else 0, key=f"lw_{i}", label_visibility="collapsed")
                        
                    lines_keep.append({'axis': na, 'value': nv, 'color': nc, 'style': ns, 'width': nw})
                    
                if rerun or len(lines_keep) != len(st.session_state.ref_lines) or any(l['value'] != st.session_state.ref_lines[i]['value'] for i, l in enumerate(lines_keep)):
                    st.session_state.ref_lines = lines_keep
                    if rerun: st.rerun()
                else: 
                    st.session_state.ref_lines = lines_keep

    with col_plot:
        chart_title = st.text_input("Tytuł Wykresu", st.session_state.chart_config.get('title', "Mój Wykres"), key='title_input', placeholder="Tytuł")
        st.session_state.chart_config['title'] = chart_title
        
        # Generowanie wykresu do podglądu
        fig_screen = create_chart_figure(st.session_state.df_chart, x_col, y_cols, st.session_state.chart_config, export_mode=None)
        st.pyplot(fig_screen)
        
        st.divider()
        st.subheader("💾 Pobierz Wykres")
        c1, c2, c3 = st.columns(3)
        fp = chart_title.replace(" ", "_").lower() if chart_title else "wykres"
        
        with c1:
            st.markdown("**Ekran (Tło Ciemne)**")
            get_image_download_link(fig_screen, "png", None, "PNG", fp)
            get_image_download_link(fig_screen, "pdf", None, "PDF", fp)
        with c2:
            st.markdown("**Druk (Tło Białe / Kolor)**")
            get_image_download_link(fig_screen, "png", "print_color", "PNG", fp)
            get_image_download_link(fig_screen, "pdf", "print_color", "PDF", fp)
        with c3:
            st.markdown("**Druk (Tło Białe / Cz-B)**")
            get_image_download_link(fig_screen, "png", "print_bw", "PNG", fp)
            get_image_download_link(fig_screen, "pdf", "print_bw", "PDF", fp)

# ==========================================
# MODUŁ 2: EDYTOR PDF (Naprawiony - pypdf + reportlab)
# ==========================================

def run_pdf_editor():
    c_back, c_tit = st.columns([1, 10])
    with c_back:
        if st.button("🏠 Menu", use_container_width=True): go_home()
    with c_tit:
        st.subheader("📄 Edytor PDF (Tryb Strukturalny - Text)")

    if 'pdf_bytes' not in st.session_state: st.session_state.pdf_bytes = None
    if 'current_pdf_annotations' not in st.session_state: st.session_state.current_pdf_annotations = []
    if 'last_pdf' not in st.session_state: st.session_state.last_pdf = "dokument.pdf"
    
    col_tools, col_workspace = st.columns([1, 3])
    
    # Ustalanie liczby stron do ograniczenia pola wyboru
    num_pages = 1
    if st.session_state.pdf_bytes:
        try:
            reader_check = PdfReader(io.BytesIO(st.session_state.pdf_bytes))
            num_pages = len(reader_check.pages)
        except Exception:
            num_pages = 1 

    with col_tools:
        st.markdown("### 🛠️ Narzędzia Edycji")
        
        # --- KONTROLKI DODAWANIA TEKSTU ---
        st.caption("Dodaj Adnotację Tekstową")
        with st.form("text_annotation_form", clear_on_submit=True):
            text_content = st.text_area("Tekst Adnotacji", "Wpisz swój tekst tutaj.")
            
            page_to_annotate = st.number_input(f"Strona (1-{num_pages})", min_value=1, max_value=num_pages, value=1)
            
            st.markdown("**Pozycja na stronie (punkty)**")
            c_x, c_y = st.columns(2)
            # Domyślny rozmiar strony Letter: ~612x792 pt. 50, 750 to górny lewy róg.
            pos_x = c_x.number_input("Pozycja X (od lewej)", min_value=0, max_value=600, value=50)
            pos_y = c_y.number_input("Pozycja Y (od dołu)", min_value=0, max_value=780, value=750)
            text_size = st.number_input("Rozmiar Tekstu", min_value=8, max_value=40, value=12)

            if st.form_submit_button("➕ Dodaj do Listy Adnotacji", type="primary"):
                if not st.session_state.pdf_bytes:
                    st.warning("Najpierw wczytaj plik PDF.")
                else:
                    st.session_state.current_pdf_annotations.append({
                        'text': text_content,
                        'page': int(page_to_annotate),
                        'x': int(pos_x),
                        'y': int(pos_y),
                        'size': int(text_size)
                    })
                    st.toast(f"Dodano adnotację na stronę {page_to_annotate}!")
                    st.rerun()
        
        # --- LISTA ADNOTACJI ---
        if st.session_state.current_pdf_annotations:
            st.markdown("---")
            st.subheader("Lista Oczekujących Adnotacji")
            for i, ann in enumerate(st.session_state.current_pdf_annotations):
                 st.caption(f"**Strona {ann['page']}** (X={ann['x']}, Y={ann['y']}): *{ann['text'][:30]}...*")

        st.markdown("---")
        if st.button("🗑️ Wyczyść Listę Adnotacji"):
            st.session_state.current_pdf_annotations = []
            st.rerun()

    with col_workspace:
        uploaded_pdf = st.file_uploader("Wgraj plik PDF", type="pdf", label_visibility="collapsed")
        
        if uploaded_pdf:
            # Wczytanie pliku
            st.session_state.pdf_bytes = uploaded_pdf.read()
            st.session_state.last_pdf = uploaded_pdf.name
            st.session_state.current_pdf_annotations = [] # Wyczyść stare adnotacje przy nowym pliku
            st.success(f"Plik **{uploaded_pdf.name}** wczytany. Liczba stron: {num_pages}.")
            st.rerun() 

        if st.session_state.pdf_bytes:
            st.subheader("Podgląd i Zapis")
            
            # Podgląd oryginalnego pliku (Streamlit nie osadza PDF, więc oferujemy pobieranie)
            st.download_button(
                label="👁️ Pobierz Oryginalny PDF (Podgląd)",
                data=st.session_state.pdf_bytes,
                file_name=st.session_state.last_pdf,
                mime="application/pdf",
                help="Kliknij, aby otworzyć w przeglądarce i sprawdzić strony/pozycje."
            )

            # 2. GENEROWANIE NOWEGO PDF
            if st.button("💾 Zastosuj Adnotacje i Pobierz Nowy PDF", type="primary"):
                
                if not st.session_state.current_pdf_annotations:
                    st.warning("Nie dodano żadnych adnotacji do zastosowania.")
                    st.stop()
                
                with st.spinner("Generowanie nowego pliku PDF..."):
                    try:
                        reader = PdfReader(io.BytesIO(st.session_state.pdf_bytes))
                        writer = PdfWriter()

                        for i, page in enumerate(reader.pages):
                            page_num = i + 1
                            current_page = page
                            
                            # Filtrowanie adnotacji dla bieżącej strony
                            annotations_to_add = [
                                ann for ann in st.session_state.current_pdf_annotations 
                                if ann['page'] == page_num
                            ]
                            
                            if annotations_to_add:
                                # Utworzenie warstwy z adnotacjami za pomocą ReportLab
                                overlay_buffer = io.BytesIO()
                                # ReportLab używa domyślnie 72 DPI, pagesize=letter (612x792 pt)
                                overlay_pdf = reportlab_canvas.Canvas(overlay_buffer, pagesize=letter)
                                
                                # Dodanie adnotacji
                                for ann in annotations_to_add:
                                    # ReportLab rysuje od dołu do góry (0,0 to lewy dolny róg)
                                    overlay_pdf.setFont("Helvetica", ann['size'])
                                    # Użycie drawString do dodania tekstu
                                    overlay_pdf.drawString(ann['x'], ann['y'], ann['text'])

                                overlay_pdf.save()
                                
                                # Scalenie warstwy z oryginalną stroną za pomocą pypdf
                                overlay_reader = PdfReader(overlay_buffer)
                                overlay_page = overlay_reader.pages[0]
                                
                                current_page.merge_page(overlay_page)

                            writer.add_page(current_page)
                        
                        final_buffer = io.BytesIO()
                        writer.write(final_buffer)
                        final_buffer.seek(0)

                        st.download_button(
                            label="📥 Pobierz Edytowany PDF",
                            data=final_buffer.getvalue(),
                            file_name=f"edytowany_{st.session_state.last_pdf}",
                            mime="application/pdf"
                        )
                        st.success("PDF został wygenerowany z adnotacjami!")
                        st.session_state.current_pdf_annotations = [] # Wyczyść listę po zapisie
                        st.rerun() 

                    except Exception as e:
                        st.error(f"Wystąpił nieoczekiwany błąd podczas edycji PDF: {e}")
                        
# ==========================================
# EKRAN STARTOWY (MENU)
# ==========================================

def home_screen():
    st.markdown("<div style='height: 100px;'></div>", unsafe_allow_html=True)
    st.markdown("<h1 style='text-align: center; margin-bottom: 50px;'>Wybierz Narzędzie</h1>", unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns([1, 2, 1])
    
    with c2:
        if st.button("📊 KREATOR WYKRESÓW", use_container_width=True, help="Tworzenie i eksportowanie wykresów Matplotlib"):
            go_chart()
        
        st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
        
        if st.button("📄 EDYTOR PDF (Tekst i Struktura)", use_container_width=True, help="Wczytywanie i dodawanie tekstu do plików PDF (pypdf)"):
            go_pdf()

# ==========================================
# GŁÓWNY ROUTER
# ==========================================

def main():
    if st.session_state.current_view == "home":
        home_screen()
    elif st.session_state.current_view == "chart_creator":
        run_chart_creator()
    elif st.session_state.current_view == "pdf_editor":
        run_pdf_editor()

if __name__ == "__main__":
    main()
