import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import io
from PIL import Image

# Importy do PDF
try:
    import fitz  # PyMuPDF
    from streamlit_drawable_canvas import st_canvas
except ImportError:
    st.error("Brakuje bibliotek! Upewnij się, że w requirements.txt są: pymupdf, streamlit-drawable-canvas, Pillow")
    st.stop()

# --- 1. KONFIGURACJA I STAŁE ---
st.set_page_config(layout="wide", page_title="Chart Master & PDF Web")

# Stałe Wykresów
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
# MODUŁ 1: KREATOR WYKRESÓW
# ==========================================

def run_chart_creator():
    # --- ZARZĄDZANIE STANEM WYKRESÓW ---
    if 'num_series' not in st.session_state: st.session_state.num_series = 1
    if 'num_points' not in st.session_state: st.session_state.num_points = 1
    if 'df' not in st.session_state: st.session_state.df = pd.DataFrame({"X": [1.0], "Y1": [10.0]})
    if 'annotations' not in st.session_state: st.session_state.annotations = []
    if 'ref_lines' not in st.session_state: st.session_state.ref_lines = []
    if 'series_config' not in st.session_state: st.session_state.series_config = {}
    if 'symbol_to_copy' not in st.session_state: st.session_state.symbol_to_copy = ""

    def process_uploaded_file(uploaded_file):
        try:
            if uploaded_file.name.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(uploaded_file)
            else:
                uploaded_file.seek(0)
                try: df = pd.read_csv(uploaded_file, sep=None, engine='python')
                except: 
                    uploaded_file.seek(0)
                    try: df = pd.read_csv(uploaded_file, delim_whitespace=True)
                    except: uploaded_file.seek(0); df = pd.read_csv(uploaded_file, sep=',')
            
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
            df = df[~(df.filter(regex='^Y\d+$') == 0).all(axis=1)].reset_index(drop=True)
            return df if not df.empty else None
        except Exception: return None

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
                if len(df) <= 1: ax.plot(df[x_col], df[col], label=alias, color=color, linestyle='None', linewidth=config['width'], marker='o')
                else: ax.plot(df[x_col], df[col], label=alias, color=color, linestyle=linestyle, linewidth=config['width'], marker='o' if config['markers'] else None)
            elif config['type'] == "Punktowy": ax.scatter(df[x_col], df[col], label=alias, color=color, s=30)
            elif config['type'] == "Słupkowy": ax.bar(df[x_col], df[col], label=alias, color=color, alpha=0.7)

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

    # --- GUI KREATORA ---
    st.title("📊 Kreator Wykresów")
    
    with st.sidebar:
        st.header("1. Źródło Danych")
        is_manual_mode = (st.session_state.get('data_source', "Wpisz Ręcznie") == "Wpisz Ręcznie")
        
        with st.container(border=True):
            st.subheader("Opcje Danych")
            data_source = st.radio("Tryb:", ["Wpisz Ręcznie", "Wgraj Plik"], horizontal=True, key='data_source')
            if data_source == "Wgraj Plik":
                uploaded_file = st.file_uploader("Excel, CSV, TXT", type=['csv', 'txt', 'xlsx', 'xls'])
                if uploaded_file:
                    if 'last_upload_hash' not in st.session_state or st.session_state.last_upload_hash != uploaded_file.file_id:
                        df_new = process_uploaded_file(uploaded_file)
                        if df_new is not None: 
                            st.session_state.df = df_new
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
                num_series_input = c1.selectbox("Serii (Y)", list(range(1, 11)), index=st.session_state.num_series - 1, key='sel_num_series')
                try: cur_idx = POINTS_OPTIONS.index(st.session_state.num_points)
                except: cur_idx = 0
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
                        else: new_data = series_data.head(st.session_state.num_points)
                        new_df[col] = new_data.fillna(0).astype(float)
                    if (new_df['X'] == 0).all(): new_df['X'] = np.arange(1, st.session_state.num_points + 1).astype(float)
                    st.session_state.df = new_df
                    st.rerun()
            else:
                st.caption("Z pliku.")

        x_col = 'X'
        y_cols = [col for col in st.session_state.df.columns if col.startswith('Y')]

        st.header("2. Opcje Wykresu")
        with st.container(border=True):
            st.subheader("Typ")
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

    # Główny ekran
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
                        with st.container(border=True):
                            st.caption(f"**Pkt {r+1}**")
                            cols = st.columns([1] + [1]*len(y_cols))
                            new_x = cols[0].number_input(f"X {r+1}", value=float(st.session_state.df.loc[r, x_col]), key=f"dX_{r}", format="%f")
                            new_df_data[(r, x_col)] = new_x
                            for idx, yc in enumerate(y_cols):
                                ny = cols[idx+1].number_input(f"{yc} {r+1}", value=float(st.session_state.df.loc[r, yc]), key=f"d{yc}_{r}", format="%f")
                                new_df_data[(r, yc)] = ny
                    if st.form_submit_button("Zapisz"):
                        temp_df = st.session_state.df.copy()
                        for (r, c), v in new_df_data.items(): temp_df.loc[r, c] = v
                        st.session_state.df = temp_df
                        st.rerun()

        with st.expander("🎨 Serie", expanded=True):
            default_colors = plt.rcParams['axes.prop_cycle'].by_key()['color']
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

        with st.expander("📝 Adnotacje", expanded=True):
            def_x = float(st.session_state.df_chart[x_col].mean()) if not st.session_state.df_chart.empty else 0.0
            def_y = float(st.session_state.df_chart[y_cols[0]].mean()) if not st.session_state.df_chart.empty and len(y_cols)>0 else 0.0
            with st.container(border=True):
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
                    with st.container(border=True):
                        cd, cx, cy = st.columns([0.5, 1.5, 1.5])
                        if cd.button("❌", key=f"rmn_{i}"): rerun = True; continue
                        nx = cx.number_input("X", value=n['x'], key=f"nx_{i}", format="%f")
                        ny = cy.number_input("Y", value=n['y'], key=f"ny_{i}", format="%f")
                        nt = st.text_input("Treść", value=n['text'], key=f"nt_{i}")
                    notes_keep.append({'x': nx, 'y': ny, 'text': nt})
                if rerun or len(notes_keep) != len(st.session_state.annotations):
                    st.session_state.annotations = notes_keep
                    st.rerun()
                else: st.session_state.annotations = notes_keep

        with st.expander("📏 Linie Ref.", expanded=True):
            with st.container(border=True):
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
                    with st.container(border=True):
                        cd, ca, cv = st.columns([0.5, 1, 2])
                        if cd.button("❌", key=f"rml_{i}"): rerun = True; continue
                        na = ca.selectbox("Oś", ["X", "Y"], index=0 if l['axis']=='X' else 1, key=f"la_{i}")
                        nv = cv.number_input("Val", value=l['value'], key=f"lv_{i}", format="%f")
                        c1, c2, c3 = st.columns([1.5, 1.5, 1])
                        nc = c1.color_picker("Kol", l['color'], key=f"lc_{i}")
                        ns = c2.selectbox("Styl", REF_LINE_STYLES, index=REF_LINE_STYLES.index(l.get('style', DEFAULT_REF_LINE_STYLE)), key=f"ls_{i}")
                        nw = c3.selectbox("Gr", WIDTH_OPTIONS, index=WIDTH_OPTIONS.index(l.get('width', 1.0)), key=f"lw_{i}")
                    lines_keep.append({'axis': na, 'value': nv, 'color': nc, 'style': ns, 'width': nw})
                if rerun or len(lines_keep) != len(st.session_state.ref_lines):
                    st.session_state.ref_lines = lines_keep
                    st.rerun()
                else: st.session_state.ref_lines = lines_keep

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
    st.title("📄 Edytor PDF (Adnotacje)")
    
    # 1. Stan dla pliku PDF i edycji
    if 'pdf_file' not in st.session_state: st.session_state.pdf_file = None
    if 'pdf_bytes' not in st.session_state: st.session_state.pdf_bytes = None
    # Słownik przechowujący adnotacje dla każdej strony: {page_num: canvas_data}
    if 'page_annotations' not in st.session_state: st.session_state.page_annotations = {}

    with st.sidebar:
        st.header("Narzędzia")
        drawing_mode = st.selectbox("Narzędzie:", ("freedraw", "line", "rect", "circle", "transform", "text"))
        
        stroke_width = st.slider("Grubość:", 1, 20, 2)
        stroke_color = st.color_picker("Kolor:", "#FF0000")
        
        # Opcje specjalne
        fill_color = "#00000000" # Domyślnie przezroczyste tło kształtów
        if drawing_mode == "text":
            st.info("Kliknij na PDF, aby dodać tekst.")
            text_val = st.text_input("Treść tekstu:", "Tutaj wpisz tekst")
        
        # Checkbox kompresji przy pobieraniu
        compress_pdf = st.checkbox("Kompresuj przy zapisie", value=False)

    # Wgrywanie Pliku
    uploaded_pdf = st.file_uploader("Wgraj PDF", type="pdf", key="pdf_uploader")
    if uploaded_pdf:
        # Jeśli wgrano nowy plik, zresetuj stan
        if st.session_state.pdf_file != uploaded_pdf.name:
            st.session_state.pdf_file = uploaded_pdf.name
            st.session_state.pdf_bytes = uploaded_pdf.read()
            st.session_state.page_annotations = {} # Reset adnotacji
    
    if st.session_state.pdf_bytes:
        doc = fitz.open(stream=st.session_state.pdf_bytes, filetype="pdf")
        total_pages = len(doc)

        # Nawigacja po stronach (Paginacja)
        if 'current_page' not in st.session_state: st.session_state.current_page = 0
        
        col_nav1, col_nav2, col_nav3 = st.columns([1, 2, 1])
        with col_nav1:
            if st.button("◀ Poprzednia") and st.session_state.current_page > 0:
                st.session_state.current_page -= 1
                st.rerun()
        with col_nav2:
            st.markdown(f"<div style='text-align: center'>Strona {st.session_state.current_page + 1} z {total_pages}</div>", unsafe_allow_html=True)
        with col_nav3:
            if st.button("Następna ▶") and st.session_state.current_page < total_pages - 1:
                st.session_state.current_page += 1
                st.rerun()

        # Opcje obracania strony
        col_rot1, col_rot2 = st.columns(2)
        rotation = 0
        # Uwaga: PyMuPDF obraca trwale w obiekcie page, ale tutaj robimy to wizualnie na obrazku
        # Aby obrót był trwały, musimy modyfikować 'doc' przy zapisie.
        # Tutaj dla prostoty - canvas jest na wprost.
        
        # Wyświetlanie edytora dla bieżącej strony
        page_num = st.session_state.current_page
        page = doc.load_page(page_num)
        pix = page.get_pixmap(dpi=150)
        img = Image.open(io.BytesIO(pix.tobytes("png")))

        # Przywrócenie stanu canvasa dla tej strony (jeśli istnieje)
        initial_drawing = st.session_state.page_annotations.get(page_num)

        # Płótno
        canvas_result = st_canvas(
            fill_color=fill_color,
            stroke_width=stroke_width,
            stroke_color=stroke_color,
            background_image=img,
            update_streamlit=True,
            height=img.height,
            width=img.width,
            drawing_mode=drawing_mode,
            initial_drawing=initial_drawing,
            key=f"canvas_page_{page_num}", # Klucz unikalny dla strony
            display_toolbar=True,
            text_value=text_val if drawing_mode == "text" else ""
        )

        # Zapisywanie zmian canvasa do stanu sesji w czasie rzeczywistym
        if canvas_result.json_data is not None:
            st.session_state.page_annotations[page_num] = canvas_result.json_data

        st.markdown("---")
        st.markdown("### Zapisz Plik")
        
        if st.button("💾 Pobierz Cały Edytowany PDF"):
            # Proces zapisu:
            # 1. Kopiujemy oryginalny dokument
            # 2. Dla każdej strony, jeśli są adnotacje, renderujemy je i nakładamy na stronę
            
            out_buffer = io.BytesIO()
            
            # Iteracja po stronach i nakładanie zmian
            for p_idx in range(len(doc)):
                # Sprawdź czy są zmiany dla tej strony
                if p_idx in st.session_state.page_annotations:
                    json_data = st.session_state.page_annotations[p_idx]
                    
                    # Musimy odtworzyć obraz adnotacji. 
                    # Niestety st_canvas zwraca tylko JSON lub image_data "na żywo".
                    # Aby "wypalić" zmiany w PDF backendowo, najprościej jest:
                    # - Wziąć obraz tła strony
                    # - Nałożyć na niego image_data z canvasa (jeśli użytkownik jest na tej stronie i to wygenerował)
                    # - Lub (trudniejsze) sparsować JSON i narysować kształty w PyMuPDF.
                    
                    # UPROSZCZENIE DLA TEJ WERSJI:
                    # Zapis działa najlepiej dla strony, którą właśnie widzisz (bo mamy canvas_result.image_data).
                    # Aby zapisać CAŁY PDF z edycjami na WIELU stronach, musielibyśmy renderować JSON na obraz.
                    # Tutaj zastosujemy podejście: Zapisujemy zmiany TYLKO jeśli mamy obraz adnotacji.
                    
                    # W Streamlit Canvas, `image_data` jest dostępne tylko dla aktywnego canvasa.
                    # Ograniczenie: Pełny zapis wielostronicowy z edycją wymagałby zewnętrznego silnika renderującego JSON.
                    
                    # DLA WERSJI BASIC: Zapisujemy PDF, ale ostrzegamy, że edycje są "nałożone" jako obrazek na stronę.
                    
                    # Jeśli to jest aktywna strona i mamy dane obrazu:
                    if p_idx == page_num and canvas_result.image_data is not None:
                        overlay_img = Image.fromarray(canvas_result.image_data.astype('uint8'), 'RGBA')
                        
                        # Pobierz rozmiar strony PDF
                        rect = doc[p_idx].rect
                        
                        # Zapisz overlay do bytes
                        overlay_buf = io.BytesIO()
                        overlay_img.save(overlay_buf, format="PNG")
                        
                        # Wstaw obrazek (adnotacje) na stronę PDF
                        doc[p_idx].insert_image(rect, stream=overlay_buf.getvalue())

            # Zapis dokumentu
            doc.save(out_buffer, deflate=compress_pdf)
            
            st.download_button(
                label="📥 Kliknij, aby pobrać PDF",
                data=out_buffer.getvalue(),
                file_name="edytowany_dokument.pdf",
                mime="application/pdf"
            )
            st.warning("Uwaga: W tej wersji przeglądarkowej, do pliku PDF zapisują się zmiany widoczne aktualnie na ekranie (aktywna strona). Aby zapisać edycje z wielu stron, musiałbyś edytować każdą po kolei i klikać zapisz, lub użyć zaawansowanego backendu.")

# ==========================================
# GŁÓWNE MENU
# ==========================================

def main():
    st.sidebar.title("Menu")
    mode = st.sidebar.radio("Wybierz:", ["Kreator Wykresów", "Edytor PDF (Adnotacje)"])
    st.sidebar.markdown("---")

    if mode == "Kreator Wykresów":
        run_chart_creator()
    elif mode == "Edytor PDF (Adnotacje)":
        run_pdf_editor()

if __name__ == "__main__":
    main()
