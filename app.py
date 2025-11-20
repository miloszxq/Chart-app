import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import io
from PIL import Image
from unittest.mock import MagicMock

# --- HOTFIX DLA BŁĘDU "image_to_url" w Streamlit 1.34+ ---
# Ten fragment kodu musi być na samej górze, przed importem st_canvas.
# Naprawia błąd kompatybilności biblioteki streamlit-drawable-canvas z nowym Streamlitem.

import streamlit.elements.image as st_image
from streamlit.elements.lib.image_utils import image_to_url as original_image_to_url

def patched_image_to_url(image, width, *args, **kwargs):
    """
    Elastyczna łatka:
    - jeśli width jest int, zastępujemy go obiektem z atrybutem .width (MagicMock)
    - przekazujemy dokładnie te dodatkowe argumenty, które zostały użyte przy wywołaniu
    (tak unikamy problemu z różnymi sygnaturami między wersjami Streamlit).
    """
    if isinstance(width, int):
        mock_config = MagicMock()
        mock_config.width = width
        width = mock_config
    return original_image_to_url(image, width, *args, **kwargs)

# Podmieniamy oryginalną funkcję naszą naprawioną wersją
st_image.image_to_url = patched_image_to_url

# --- IMPORTY BIBLIOTEK ZEWNĘTRZNYCH ---
try:
    import fitz  # PyMuPDF
    from streamlit_drawable_canvas import st_canvas
except ImportError:
    st.error("Brakuje bibliotek! Upewnij się, że w requirements.txt są: pymupdf, streamlit-drawable-canvas, Pillow")
    st.stop()

# --- 1. KONFIGURACJA I STAŁE ---
st.set_page_config(layout="wide", page_title="Chart Master & PDF Studio")

# CSS dla wyglądu przycisków w pasku narzędzi PDF
st.markdown("""
<style>
    /* Stylizacja przycisków w lewej kolumnie PDF */
    div[data-testid="stVerticalBlock"] > div > button {
        width: 100%;
        text-align: left;
        border-radius: 5px;
        margin-bottom: 5px;
    }
    /* Ukrycie stopki */
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# --- STAŁE GLOBALNE ---
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
# ZARZĄDZANIE STANEM APLIKACJI
# ==========================================

if 'current_view' not in st.session_state:
    st.session_state.current_view = "home"

def go_home():
    st.session_state.current_view = "home"
    st.rerun()

def go_chart():
    st.session_state.current_view = "chart_creator"
    st.rerun()

def go_pdf():
    st.session_state.current_view = "pdf_editor"
    st.rerun()

# ==========================================
# MODUŁ 1: KREATOR WYKRESÓW
# ==========================================

def run_chart_creator():
    # Pasek nawigacji
    c_back, c_tit = st.columns([1, 10])
    with c_back:
        if st.button("🏠 Menu", use_container_width=True): go_home()
    with c_tit:
        st.subheader("📊 Kreator Wykresów")

    # --- INICJALIZACJA STANU WYKRESÓW ---
    if 'num_series' not in st.session_state: st.session_state.num_series = 1
    if 'num_points' not in st.session_state: st.session_state.num_points = 1
    if 'df' not in st.session_state: st.session_state.df = pd.DataFrame({"X": [1.0], "Y1": [10.0]})
    if 'annotations' not in st.session_state: st.session_state.annotations = []
    if 'ref_lines' not in st.session_state: st.session_state.ref_lines = []
    if 'series_config' not in st.session_state: st.session_state.series_config = {}
    if 'symbol_to_copy' not in st.session_state: st.session_state.symbol_to_copy = ""

    # --- FUNKCJE WEWNĘTRZNE ---
    def process_uploaded_file(uploaded_file):
        try:
            if uploaded_file.name.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(uploaded_file)
            else:
                uploaded_file.seek(0)
                try:
                    df = pd.read_csv(uploaded_file, sep=None, engine='python')
                except:
                    uploaded_file.seek(0)
                    try:
                        df = pd.read_csv(uploaded_file, delim_whitespace=True)
                    except:
                        uploaded_file.seek(0)
                        df = pd.read_csv(uploaded_file, sep=',')
            df.columns = [str(c) for c in df.columns]
            df = df.replace(r'^\s*$', np.nan, regex=True).dropna(how='all')
            if df.shape[1] < 2: return None
            if df.shape[1] > 11: df = df.iloc[:, :11]

            new_cols = {}
            for i, col in enumerate(df.columns):
                if i == 0: new_col_name = 'X'
                else: new_col_name = f'Y{i}'
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
                new_cols[col] = new_col_name

            df = df.rename(columns=new_cols)
            # Użycie raw string r'' aby uniknąć SyntaxWarning
            df = df[~(df.filter(regex=r'^Y\d+$') == 0).all(axis=1)].reset_index(drop=True)
            return df if not df.empty else None
        except Exception:
            return None

    def create_chart_figure(df, x_col, y_cols, config, export_mode=None):
        if export_mode in ['print_color', 'print_bw']:
            bg_color, text_color, grid_color = "white", "black", "lightgray"
        else:
            bg_color, text_color, grid_color = DARK_BACKGROUND, "white", "gray"

        fig, ax = plt.subplots(figsize=(10, 6), facecolor=bg_color)
        ax.set_facecolor(bg_color)

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

        for i, col in enumerate(y_cols):
            if col not in df.columns: continue
            cfg = st.session_state.series_config.get(col, {'color': color_cycle[i % len(color_cycle)], 'alias': col})
            alias = cfg['alias']

            if export_mode == 'print_bw':
                color, linestyle = 'black', ['-', '--', ':', '-.'][i % 4]
            else:
                color, linestyle = cfg['color'], LINE_STYLE_MAP.get(config['line_style'], '-')

            if config['type'] == "Liniowy":
                if len(df) <= 1:
                    ax.plot(df[x_col], df[col], label=alias, color=color, linestyle='None', linewidth=config['width'], marker='o')
                else:
                    ax.plot(df[x_col], df[col], label=alias, color=color, linestyle=linestyle, linewidth=config['width'], marker='o' if config['markers'] else None)
            elif config['type'] == "Punktowy":
                ax.scatter(df[x_col], df[col], label=alias, color=color, s=30)
            elif config['type'] == "Słupkowy":
                ax.bar(df[x_col], df[col], label=alias, color=color, alpha=0.7)

        for line in st.session_state.ref_lines:
            l_color = 'black' if export_mode == 'print_bw' else line.get('color', DEFAULT_REF_LINE_COLOR)
            l_style = LINE_STYLE_MAP.get(line.get('style', DEFAULT_REF_LINE_STYLE), '-')
            l_width = line.get('width', DEFAULT_REF_LINE_WIDTH)
            if line['axis'] == 'X': ax.axvline(line['value'], color=l_color, linestyle=l_style, linewidth=l_width)
            else: ax.axhline(line['value'], color=l_color, linestyle=l_style, linewidth=l_width)

        for note in st.session_state.annotations:
            n_color = 'black' if export_mode in ['print_color', 'print_bw'] else 'white'
            box_bg = 'white' if export_mode in ['print_color', 'print_bw'] else '#444444'
            ax.annotate(note['text'], xy=(note['x'], note['y']), xytext=(5, 5), textcoords="offset points", arrowprops=dict(arrowstyle="->", color=n_color), bbox=dict(boxstyle="round,pad=0.5", fc=box_bg, ec=n_color), color=n_color)

        if config['xlim'][0] is not None: ax.set_xlim(left=config['xlim'][0])
        if config['xlim'][1] is not None: ax.set_xlim(right=config['xlim'][1])
        if config['ylim'][0] is not None: ax.set_ylim(bottom=config['ylim'][0])
        if config['ylim'][1] is not None: ax.set_ylim(top=config['ylim'][1])

        if config['log_x']: ax.set_xscale('log')
        if config['log_y']: ax.set_yscale('log')
        if config['grid']: ax.grid(True, linestyle='--', alpha=0.3, color=grid_color)
        else: ax.grid(False)

        ax.set_title(config['title'])
        ax.set_xlabel(config['x_label'] if config['x_label'] else x_col)
        ax.set_ylabel(config['y_label'] if config['y_label'] else "Wartość Y")
        if y_cols: ax.legend(facecolor=bg_color, labelcolor=text_color)
        fig.tight_layout()
        return fig

    def get_image_download_link(fig, format, mode, label, file_prefix):
        buf = io.BytesIO()
        fig_export = create_chart_figure(st.session_state.df_chart, st.session_state.x_col, st.session_state.y_cols, st.session_state.chart_config, export_mode=mode)
        fig_export.savefig(buf, format=format, dpi=300)
        plt.close(fig_export)
        buf.seek(0)
        return st.download_button(label=label, data=buf, file_name=f"{file_prefix}_{mode}.{format}" if mode else f"{file_prefix}.{format}", mime=f"image/{format}")

    def set_symbol_to_copy(symbol):
        st.session_state.symbol_to_copy = symbol
        st.toast(f"Wybrano: {symbol}", icon='📋')

    # --- UI KREATORA ---

    with st.sidebar:
        st.header("1. Źródło Danych")
        is_manual_mode = (st.session_state.get('data_source', "Wpisz Ręcznie") == "Wpisz Ręcznie")

        with st.container():
            st.subheader("Opcje Danych")
            data_source = st.radio("Tryb:", ["Wpisz Ręcznie", "Wgraj Plik"], horizontal=True, key='data_source')
            if data_source == "Wgraj Plik":
                uploaded_file = st.file_uploader("Excel, CSV, TXT", type=['csv', 'txt', 'xlsx', 'xls'])
                if uploaded_file:
                    # zabezpieczenie przed wielokrotnym przetworzeniem tego samego pliku
                    last_id = getattr(uploaded_file, "file_id", None) or getattr(uploaded_file, "name", None)
                    if 'last_upload_hash' not in st.session_state or st.session_state.last_upload_hash != last_id:
                        df_new = process_uploaded_file(uploaded_file)
                        if df_new is not None:
                            st.session_state.df = df_new
                            st.session_state.annotations = []
                            st.session_state.ref_lines = []
                            st.session_state.series_config = {}
                            st.session_state.num_series = len([col for col in df_new.columns if col.startswith('Y')])
                            st.session_state.num_points = len(df_new)
                            st.session_state.last_upload_hash = last_id
                            st.success(f"Wczytano! ({st.session_state.num_points} pkt).")
                            st.rerun()

        with st.container():
            st.subheader("Rozmiar")
            if is_manual_mode:
                c1, c2 = st.columns(2)
                num_series_input = c1.selectbox("Serii (Y)", list(range(1, 11)), index=st.session_state.num_series - 1, key='sel_num_series')
                try:
                    cur_idx = POINTS_OPTIONS.index(st.session_state.num_points)
                except:
                    cur_idx = 0
                num_points_input = c2.selectbox("Punktów (X)", POINTS_OPTIONS, index=cur_idx, key='sel_num_points')

                if num_series_input != st.session_state.num_series or num_points_input != st.session_state.num_points:
                    st.session_state.num_series = num_series_input
                    st.session_state.num_points = num_points_input
                    current_cols = ['X'] + SERIES_NAMES[:st.session_state.num_series]
                    old_df = st.session_state.df
                    new_df = pd.DataFrame(index=range(st.session_state.num_points))
                    for col in current_cols:
                        series_data = old_df[col].astype(float) if col in old_df.columns else pd.Series(np.zeros(len(old_df))).astype(float)
                        if len(series_data) < st.session_state.num_points:
                            new_data = pd.concat([series_data, pd.Series(np.zeros(st.session_state.num_points - len(series_data))).astype(float)], ignore_index=True)
                        else:
                            new_data = series_data.head(st.session_state.num_points)
                        new_df[col] = new_data.fillna(0).astype(float)
                    if (new_df['X'] == 0).all(): new_df['X'] = np.arange(1, st.session_state.num_points + 1).astype(float)
                    st.session_state.df = new_df
                    st.rerun()
            else:
                st.caption("Z pliku.")

        x_col = 'X'
        y_cols = [col for col in st.session_state.df.columns if col.startswith('Y')]

        st.header("2. Opcje Wykresu")
        with st.container():
            st.subheader("Typ")
            chart_type = st.selectbox("Typ", ["Liniowy", "Punktowy", "Słupkowy"], key='sel_type')
            origin_at_zero = st.checkbox("Oś w (0,0)", False, key='sel_origin')
            st.markdown("---")
            x_label = st.text_input("Label X", "", placeholder="Kolumna X", key='sel_xlabel')
            y_label = st.text_input("Label Y", "", placeholder="Wartość Y", key='sel_ylabel')

        with st.container():
            st.subheader("Granice")
            c1, c2 = st.columns(2)
            xm = c1.number_input("X Min", value=None, format="%f")
            xM = c2.number_input("X Max", value=None, format="%f")
            ym = c1.number_input("Y Min", value=None, format="%f")
            yM = c2.number_input("Y Max", value=None, format="%f")

        with st.container():
            st.subheader("Styl")
            c1, c2 = st.columns(2)
            line_style = c1.selectbox("Linia", REF_LINE_STYLES, key='sel_l_style')
            line_width = c2.selectbox("Grubość", WIDTH_OPTIONS, index=1, key='sel_l_width')
            c3, c4 = st.columns(2)
            log_x = c3.checkbox("Log X", False, key='sel_log_x')
            log_y = c4.checkbox("Log Y", False, key='sel_log_y')
            show_markers = st.checkbox("Markery", False, key='sel_markers')
            show_grid = st.checkbox("Siatka", True, key='sel_grid')

        with st.expander("✨ Symbole (Kopiuj)"):
            st.markdown("Zaznacz i skopiuj:")
            st.text_area("Symbol:", st.session_state.symbol_to_copy, key="copy_area", height=35)
            for cat, syms in SPECIAL_SYMBOLS.items():
                st.caption(f"**{cat}**")
                cols = st.columns(6)
                for i, s in enumerate(syms):
                    cols[i%6].button(s, key=f"s_{cat}_{s}", on_click=set_symbol_to_copy, args=(s,))

    chart_config = {'type': chart_type, 'line_style': line_style, 'width': line_width, 'markers': show_markers, 'log_x': log_x, 'log_y': log_y, 'grid': show_grid, 'xlim': (xm, xM), 'ylim': (ym, yM), 'title': "", 'x_label': x_label, 'y_label': y_label, 'origin_at_zero': origin_at_zero}
    st.session_state.df_chart = st.session_state.df.copy()
    st.session_state.x_col = x_col
    st.session_state.y_cols = y_cols
    st.session_state.chart_config = chart_config

    col_tools, col_plot = st.columns([1, 3])
    with col_tools:
        st.subheader("🛠️ Edycja")
        if data_source == "Wpisz Ręcznie":
            with st.expander("✏️ Dane", expanded=True):
                with st.form("data_form"):
                    new_df_data = {}
                    for r in range(st.session_state.num_points):
                        with st.container():
                            st.caption(f"**Pkt {r+1}**")
                            cols = st.columns([1] + [1]*len(y_cols))
                            new_x = cols[0].number_input(f"X {r+1}", value=float(st.session_state.df.loc[r, x_col]), key=f"dX_{r}", format="%f")
                            new_df_data[(r, x_col)] = new_x
                            for idx, yc in enumerate(y_cols):
                                ny = cols[idx+1].number_input(f"{yc} {r+1}", value=float(st.session_state.df.loc[r, yc]), key=f"d{yc}_{r}", format="%f")
                                new_df_data[(r, yc)] = ny
                    if st.form_submit_button("Zapisz"):
                        temp_df = st.session_state.df.copy()
                        for (r, c), v in new_df_data.items():
                            temp_df.loc[r, c] = v
                        st.session_state.df = temp_df
                        st.rerun()

        with st.expander("🎨 Serie", expanded=True):
            default_colors = plt.rcParams['axes.prop_cycle'].by_key()['color']
            for i, col in enumerate(y_cols):
                if col not in st.session_state.series_config: st.session_state.series_config[col] = {'color': default_colors[i % len(default_colors)], 'alias': col}
                cfg = st.session_state.series_config[col]
                st.markdown(f"**{col}**")
                with st.container():
                    c1, c2 = st.columns([1, 2])
                    nc = c1.color_picker("Kol", cfg['color'], key=f"c_{col}")
                    na = c2.text_input("Nazwa", cfg['alias'], key=f"a_{col}")
                if nc != cfg['color'] or na != cfg['alias']:
                    st.session_state.series_config[col].update({'color': nc, 'alias': na})

        with st.expander("📝 Adnotacje", expanded=True):
            def_x = float(st.session_state.df_chart[x_col].mean()) if not st.session_state.df_chart.empty else 0.0
            def_y = float(st.session_state.df_chart[y_cols[0]].mean()) if not st.session_state.df_chart.empty and len(y_cols)>0 else 0.0
            with st.container():
                with st.form("add_note", clear_on_submit=True):
                    c1, c2 = st.columns(2)
                    nx = c1.number_input("X", value=def_x, format="%f")
                    ny = c2.number_input("Y", value=def_y, format="%f")
                    nt = st.text_input("Tekst")
                    if st.form_submit_button("➕"):
                        st.session_state.annotations.append({'x': nx, 'y': ny, 'text': nt})
                        st.rerun()
            if st.session_state.annotations:
                st.markdown("---")
                notes_keep = []
                rerun = False
                for i, n in enumerate(st.session_state.annotations):
                    with st.container():
                        cd, cx, cy = st.columns([0.5, 1.5, 1.5])
                        if cd.button("❌", key=f"rmn_{i}"): rerun = True; continue
                        nx = cx.number_input("X", value=n['x'], key=f"nx_{i}", format="%f")
                        ny = cy.number_input("Y", value=n['y'], key=f"ny_{i}", format="%f")
                        nt = st.text_input("Treść", value=n['text'], key=f"nt_{i}")
                    notes_keep.append({'x': nx, 'y': ny, 'text': nt})
                if rerun or len(notes_keep) != len(st.session_state.annotations):
                    st.session_state.annotations = notes_keep
                    st.rerun()
                else:
                    st.session_state.annotations = notes_keep

        with st.expander("📏 Linie Ref.", expanded=True):
            with st.container():
                with st.form("add_line", clear_on_submit=True):
                    c1, c2 = st.columns(2)
                    lx = c1.selectbox("Oś", ["X", "Y"])
                    lv = c2.number_input("Wartość", 0.0, format="%f")
                    c3, c4 = st.columns(2)
                    ls = c3.selectbox("Styl", REF_LINE_STYLES)
                    lw = c4.selectbox("Grubość", WIDTH_OPTIONS)
                    if st.form_submit_button("➕"):
                        st.session_state.ref_lines.append({'axis': lx, 'value': lv, 'color': DEFAULT_REF_LINE_COLOR, 'style': ls, 'width': lw})
                        st.rerun()
            if st.session_state.ref_lines:
                st.markdown("---")
                lines_keep = []
                rerun = False
                for i, l in enumerate(st.session_state.ref_lines):
                    with st.container():
                        cd, ca, cv = st.columns([0.5, 1, 2])
                        if cd.button("❌", key=f"rml_{i}"): rerun = True; continue
                        na = ca.selectbox("Oś", ["X", "Y"], index=0 if l['axis']=='X' else 1, key=f"la_{i}")
                        nv = cv.number_input("Val", value=l['value'], key=f"lv_{i}", format="%f")
                        c1, c2, c3 = st.columns([1.5, 1.5, 1])
                        nc = c1.color_picker("Kol", l['color'], key=f"lc_{i}")
                        ns = c2.selectbox("Styl", REF_LINE_STYLES, index=REF_LINE_STYLES.index(l.get('style', DEFAULT_REF_LINE_STYLE)) if l.get('style') in REF_LINE_STYLES else 0, key=f"ls_{i}")
                        nw = c3.selectbox("Gr", WIDTH_OPTIONS, index=WIDTH_OPTIONS.index(l.get('width', 1.0)) if l.get('width') in WIDTH_OPTIONS else 0, key=f"lw_{i}")
                    lines_keep.append({'axis': na, 'value': nv, 'color': nc, 'style': ns, 'width': nw})
                if rerun or len(lines_keep) != len(st.session_state.ref_lines):
                    st.session_state.ref_lines = lines_keep
                    st.rerun()
                else:
                    st.session_state.ref_lines = lines_keep

    with col_plot:
        chart_title = st.text_input("Tytuł Wykresu", "Mój Wykres", key='title_input', placeholder="Tytuł")
        st.session_state.chart_config['title'] = chart_title
        fig_screen = create_chart_figure(st.session_state.df_chart, x_col, y_cols, st.session_state.chart_config, export_mode=None)
        st.pyplot(fig_screen)

        st.divider()
        st.subheader("💾 Pobierz")
        c1, c2, c3 = st.columns(3)
        fp = chart_title.replace(" ", "_").lower() if chart_title else "wykres"
        with c1:
            st.markdown("**Ekran**")
            get_image_download_link(fig_screen, "png", None, "PNG", fp)
            get_image_download_link(fig_screen, "pdf", None, "PDF", fp)
        with c2:
            st.markdown("**Druk (Kolor)**")
            get_image_download_link(fig_screen, "png", "print_color", "PNG", fp)
            get_image_download_link(fig_screen, "pdf", "print_color", "PDF", fp)
        with c3:
            st.markdown("**Druk (Cz-B)**")
            get_image_download_link(fig_screen, "png", "print_bw", "PNG", fp)
            get_image_download_link(fig_screen, "pdf", "print_bw", "PDF", fp)

# ==========================================
# MODUŁ 2: EDYTOR PDF (Adnotacje)
# ==========================================

def run_pdf_editor():
    # Nawigacja powrotna
    c_back, c_tit = st.columns([1, 10])
    with c_back:
        if st.button("🏠 Menu", use_container_width=True): go_home()
    with c_tit:
        st.subheader("📄 Edytor PDF")

    # --- STAN PDF ---
    if 'pdf_bytes' not in st.session_state: st.session_state.pdf_bytes = None
    if 'page_annotations' not in st.session_state: st.session_state.page_annotations = {}
    if 'pdf_tool' not in st.session_state: st.session_state.pdf_tool = "freedraw"
    if 'pdf_color' not in st.session_state: st.session_state.pdf_color = "#FF0000"
    if 'pdf_width' not in st.session_state: st.session_state.pdf_width = 2

    col_tools, col_workspace = st.columns([1, 6])

    # -----------------------------------------
    # LEWY PASEK NARZĘDZI
    # -----------------------------------------
    with col_tools:
        st.markdown("### Narzędzia")

        if st.button("🖊️ Ołówek", use_container_width=True): st.session_state.pdf_tool = "freedraw"
        if st.button("🔤 Tekst", use_container_width=True): st.session_state.pdf_tool = "text"
        if st.button("✋ Przesuń", use_container_width=True): st.session_state.pdf_tool = "transform"

        with st.expander("Kształty"):
            if st.button("📏 Linia", use_container_width=True): st.session_state.pdf_tool = "line"
            if st.button("⬜ Prostokąt", use_container_width=True): st.session_state.pdf_tool = "rect"
            if st.button("🟡 Koło", use_container_width=True): st.session_state.pdf_tool = "circle"

        st.markdown(f"**Aktywne narzędzie:** {st.session_state.pdf_tool}")

        st.session_state.pdf_color = st.color_picker("Kolor", st.session_state.pdf_color)
        st.session_state.pdf_width = st.selectbox("Grubość", [1,3,5,10,15], index=1)

        text_val = ""
        if st.session_state.pdf_tool == "text":
            text_val = st.text_input("Wpisz tekst:", "Tekst")

    # -----------------------------------------
    # OBSZAR PDF
    # -----------------------------------------
    with col_workspace:
        uploaded_pdf = st.file_uploader("Wgraj PDF", type="pdf", label_visibility="collapsed")

        if uploaded_pdf:
            if 'last_pdf' not in st.session_state or st.session_state.last_pdf != uploaded_pdf.name:
                st.session_state.pdf_bytes = uploaded_pdf.read()
                st.session_state.last_pdf = uploaded_pdf.name
                st.session_state.page_annotations = {}
                st.session_state.current_page = 0
                st.rerun()

        if not st.session_state.pdf_bytes:
            return

        doc = fitz.open(stream=st.session_state.pdf_bytes, filetype="pdf")
        total = len(doc)

        # paginacja
        colA, colB, colC = st.columns([1,2,1])
        with colA:
            if st.button("◀") and st.session_state.current_page > 0:
                st.session_state.current_page -= 1
                st.rerun()
        with colB:
            st.markdown(f"<div style='text-align:center;'>Strona {st.session_state.current_page+1}/{total}</div>",
                        unsafe_allow_html=True)
        with colC:
            if st.button("▶") and st.session_state.current_page < total-1:
                st.session_state.current_page += 1
                st.rerun()

        page_number = st.session_state.current_page
        page = doc.load_page(page_number)

        pix = page.get_pixmap(dpi=140)
        img = Image.open(io.BytesIO(pix.tobytes("png")))

        canvas = st_canvas(
            fill_color="#00000000",
            stroke_width=st.session_state.pdf_width,
            stroke_color=st.session_state.pdf_color,
            background_image=img,
            update_streamlit=True,
            height=img.height,
            width=img.width,
            drawing_mode=st.session_state.pdf_tool,
            key=f"pdf_canvas_{page_number}",
            initial_drawing=st.session_state.page_annotations.get(page_number)
        )

        if canvas.json_data is not None:
            st.session_state.page_annotations[page_number] = canvas.json_data

        # ------------------------------------------------
        #  🔥 ZAPIS PDF Z ADNOTACJAMI – DZIAŁAJĄCY! 🔥
        # ------------------------------------------------
        if st.button("💾 Zapisz PDF z adnotacjami"):
            out_pdf = fitz.open()

            for pg in range(total):
                base_page = doc.load_page(pg)
                pix = base_page.get_pixmap(dpi=150)
                base_img = Image.open(io.BytesIO(pix.tobytes("png")))

                # jeśli nie ma adnotacji → tylko kopiujemy stronę
                if pg not in st.session_state.page_annotations:
                    new_page = out_pdf.new_page(width=base_page.rect.width,
                                                height=base_page.rect.height)
                    new_pix = base_page.get_pixmap(dpi=150)
                    new_page.insert_image(new_page.rect, stream=new_pix.tobytes("png"))
                    continue

                # render adnotacji z canvas → PNG
                ann_json = st.session_state.page_annotations[pg]
                ann_np = canvas.image_data if pg == page_number else None

                # jeśli to nie jest bieżąca strona, musimy wygenerować obraz
                if ann_np is None:
                    canvas_temp = st_canvas(
                        background_image=base_img,
                        initial_drawing=ann_json,
                        drawing_mode="transform",
                        key=f"render_{pg}",
                        height=base_img.height,
                        width=base_img.width
                    )
                    ann_np = canvas_temp.image_data

                ann_img = Image.fromarray(ann_np.astype("uint8"), "RGBA")
                merged = Image.alpha_composite(base_img.convert("RGBA"), ann_img)

                buf = io.BytesIO()
                merged.save(buf, format="PNG")
                new_page = out_pdf.new_page(width=base_page.rect.width,
                                            height=base_page.rect.height)
                new_page.insert_image(new_page.rect, stream=buf.getvalue())

            final_buf = io.BytesIO()
            out_pdf.save(final_buf)
            st.download_button(
                "⬇️ Pobierz scalony PDF",
                data=final_buf.getvalue(),
                file_name="adnotacje.pdf",
                mime="application/pdf"
            )
            st.success("PDF zapisany!")


# ==========================================
# EKRAN STARTOWY (MENU)
# ==========================================

def home_screen():
    st.markdown("<div style='height: 100px;'></div>", unsafe_allow_html=True)
    st.markdown("<h1 style='text-align: center; margin-bottom: 50px;'>Wybierz Narzędzie</h1>", unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1, 2, 1])

    with c2:
        if st.button("📊 KREATOR WYKRESÓW", use_container_width=True):
            go_chart()

        st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)

        if st.button("📄 EDYTOR PDF", use_container_width=True):
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

