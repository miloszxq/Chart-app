import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import io

# --- 1. KONFIGURACJA I STAŁE ---
st.set_page_config(layout="wide", page_title="Chart Master Web (Interactive)")

# Domyślne style linii (dla Plotly używamy nazw CSS/SVG)
LINE_STYLES = {"Ciągła": "solid", "Kropkowana": "dot", "Przerywana": "dash", "Kreska-Kropka": "dashdot"}
DEFAULT_COLORS = ['#636EFA', '#EF553B', '#00CC96', '#AB63FA', '#FFA15A', '#19D3F3', '#FF6692', '#B6E880', '#FF97FF', '#FECB52']

# --- 2. ZARZĄDZANIE STANEM ---
if 'df' not in st.session_state:
    # Domyślne dane
    st.session_state.df = pd.DataFrame({
        "X": [1, 2, 3, 4, 5],
        "Y1": [10, 20, 15, 25, 30]
    })

if 'annotations' not in st.session_state:
    st.session_state.annotations = [] # Lista słowników {'x': float, 'y': float, 'text': str}
if 'ref_lines' not in st.session_state:
    st.session_state.ref_lines = [] # Lista słowników {'axis': 'x'/'y', 'value': float, ...}
if 'chart_config' not in st.session_state:
    st.session_state.chart_config = {
        'title': "Mój Wykres",
        'x_label': "Oś X",
        'y_label': "Oś Y",
        'show_grid': True,
        'chart_type': "Liniowy"
    }
    
# Obsługa kliknięć na wykresie (Plotly events)
# Streamlit natywnie obsługuje eventy z plotly_chart od wersji 1.31+ (poprzez st.plotly_chart(..., on_select="rerun"))
# Użyjemy tego mechanizmu do pobierania współrzędnych.

# --- 3. FUNKCJE POMOCNICZE ---

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
                df = pd.read_csv(uploaded_file)
        df.columns = df.columns.astype(str)
        return df
    except Exception as e:
        st.error(f"Błąd: {e}")
        return None

def create_plotly_figure(df, x_col_name, y_col_names, config, annotations, ref_lines):
    """Tworzy interaktywny wykres Plotly."""
    
    fig = go.Figure()

    # 1. Rysowanie Serii Danych
    for i, y_col in enumerate(y_col_names):
        if y_col in df.columns:
            color = DEFAULT_COLORS[i % len(DEFAULT_COLORS)]
            
            if config['chart_type'] == "Liniowy":
                fig.add_trace(go.Scatter(
                    x=df[x_col_name], y=df[y_col],
                    mode='lines+markers', name=y_col,
                    line=dict(color=color, width=2),
                    marker=dict(size=6)
                ))
            elif config['chart_type'] == "Punktowy":
                fig.add_trace(go.Scatter(
                    x=df[x_col_name], y=df[y_col],
                    mode='markers', name=y_col,
                    marker=dict(size=8, color=color)
                ))
            elif config['chart_type'] == "Słupkowy":
                fig.add_trace(go.Bar(
                    x=df[x_col_name], y=df[y_col],
                    name=y_col, marker_color=color
                ))

    # 2. Linie Referencyjne
    for line in ref_lines:
        if line['axis'] == 'x':
            fig.add_vline(x=line['value'], line_width=line['width'], line_dash=LINE_STYLES.get(line['style'], 'solid'), line_color=line['color'])
            # Etykieta dla linii pionowej
            fig.add_annotation(x=line['value'], y=1, yref="paper", text=f"x={line['value']}", showarrow=False, yanchor="bottom")
        else:
            fig.add_hline(y=line['value'], line_width=line['width'], line_dash=LINE_STYLES.get(line['style'], 'solid'), line_color=line['color'])
            # Etykieta dla linii poziomej
            fig.add_annotation(x=1, xref="paper", y=line['value'], text=f"y={line['value']}", showarrow=False, xanchor="left")

    # 3. Adnotacje Tekstowe
    for note in annotations:
        fig.add_annotation(
            x=note['x'], y=note['y'],
            text=note['text'],
            showarrow=True,
            arrowhead=2,
            arrowsize=1,
            arrowwidth=2,
            arrowcolor="#636363",
            ax=0, ay=-40, # Przesunięcie tekstu względem punktu
            bgcolor="#444", # Tło dymka (ciemne)
            bordercolor="#ffffff",
            font=dict(color="#ffffff")
        )

    # Ustawienia Wyglądu (Layout)
    fig.update_layout(
        title=config['title'],
        xaxis_title=config['x_label'],
        yaxis_title=config['y_label'],
        template="plotly_dark", # Ciemny motyw
        hovermode="closest",
        showlegend=True,
        margin=dict(l=40, r=40, t=40, b=40),
    )
    
    # Siatka
    fig.update_xaxes(showgrid=config['show_grid'], gridcolor='#444')
    fig.update_yaxes(showgrid=config['show_grid'], gridcolor='#444')

    return fig

# --- 4. INTERFEJS UŻYTKOWNIKA ---

st.title("📊 Chart Master Web (Interactive)")

# --- PANEL BOCZNY ---
with st.sidebar:
    st.header("1. Dane")
    
    data_source = st.radio("Źródło:", ["Edytor", "Plik"], horizontal=True, label_visibility="collapsed")
    
    if data_source == "Plik":
        uploaded = st.file_uploader("Wgraj CSV/Excel/TXT", type=['csv', 'xlsx', 'txt'])
        if uploaded:
            new_df = process_uploaded_file(uploaded)
            if new_df is not None:
                st.session_state.df = new_df
                st.success("Wczytano!")
    
    st.divider()
    st.header("2. Konfiguracja Osi")
    
    # Wybór kolumn z danych do przypisania do osi
    all_cols = st.session_state.df.columns.tolist()
    
    # Kolumna Danych X (To, co steruje osią X)
    col_x_data = st.selectbox("Kolumna Danych X", all_cols, index=0)
    
    # Nazwa Osi X (Tekst wyświetlany) - ZGODNIE Z ŻYCZENIEM
    st.session_state.chart_config['x_label'] = st.text_input("Nazwa Osi X", value=st.session_state.chart_config['x_label'])
    
    st.divider()
    
    # Nazwa Osi Y (Tekst wyświetlany) - ZGODNIE Z ŻYCZENIEM
    st.session_state.chart_config['y_label'] = st.text_input("Nazwa Osi Y", value=st.session_state.chart_config['y_label'])

    # Wybór Serii Danych (Multiselect działa jak 'Dodaj serię')
    # Domyślnie wybieramy wszystkie kolumny numeryczne poza X
    default_y = [c for c in all_cols if c != col_x_data][:1]
    selected_y_cols = st.multiselect("Wybierz Serie Danych (Osie Y)", [c for c in all_cols if c != col_x_data], default=default_y)
    
    if not selected_y_cols:
        st.warning("Wybierz przynajmniej jedną serię danych!")


# --- GŁÓWNY EKRAN ---

# 1. EDYTOR DANYCH (Wąski, z plusem)
with st.expander("✏️ Edytor Danych", expanded=(data_source == "Edytor")):
    # num_rows="dynamic" dodaje przycisk "+" na dole tabeli
    # use_container_width=False sprawia, że tabela nie jest rozciągnięta na całą szerokość
    col_table, col_void = st.columns([1, 2]) # Tabela zajmie 1/3 szerokości
    with col_table:
        edited_df = st.data_editor(st.session_state.df, num_rows="dynamic", key="data_editor")
        st.session_state.df = edited_df

# Przygotowanie danych (sortowanie)
df_plot = st.session_state.df.copy()
if col_x_data in df_plot.columns and pd.api.types.is_numeric_dtype(df_plot[col_x_data]):
    df_plot = df_plot.sort_values(by=col_x_data)

# --- KOLUMNY: WYKRES + NARZĘDZIA ---
col_main, col_tools = st.columns([3, 1])

# Rysowanie wykresu (przed wyświetleniem, aby przechwycić eventy)
fig = create_plotly_figure(df_plot, col_x_data, selected_y_cols, st.session_state.chart_config, st.session_state.annotations, st.session_state.ref_lines)

with col_main:
    # Tytuł Wykresu
    new_title = st.text_input("Tytuł Wykresu", value=st.session_state.chart_config['title'], label_visibility="collapsed", placeholder="Wpisz tytuł...")
    st.session_state.chart_config['title'] = new_title
    
    # INTERAKTYWNY WYKRES
    # on_select="rerun" sprawia, że kliknięcie odświeża aplikację i zwraca dane w 'selection'
    selection = st.plotly_chart(fig, use_container_width=True, on_select="rerun", selection_mode="points")

    # --- LOGIKA KLIKNIĘCIA NA WYKRESIE (DODAWANIE ADNOTACJI) ---
    # Sprawdzamy, czy użytkownik kliknął w jakiś punkt
    if selection and len(selection["points"]) > 0:
        point = selection["points"][0]
        clicked_x = point["x"]
        clicked_y = point["y"]
        
        # Wyświetlamy formularz dodania adnotacji DOKŁADNIE w miejscu kliknięcia (logicznie)
        with st.form(key=f"add_note_click_{clicked_x}_{clicked_y}"):
            st.write(f"**Dodaj adnotację w punkcie:** ({clicked_x}, {clicked_y})")
            note_text = st.text_input("Tekst", value=f"Punkt {clicked_x}")
            if st.form_submit_button("Zapisz Adnotację"):
                st.session_state.annotations.append({'x': clicked_x, 'y': clicked_y, 'text': note_text})
                st.rerun()


with col_tools:
    st.subheader("🛠️ Edycja")
    
    # ZARZĄDZANIE ADNOTACJAMI (Edycja i przesuwanie)
    with st.expander("📝 Adnotacje (Edycja)", expanded=True):
        if not st.session_state.annotations:
            st.info("Kliknij na punkt na wykresie, aby dodać adnotację!")
        
        for i, note in enumerate(st.session_state.annotations):
            with st.popover(f"✏️ {note['text'][:10]}..."):
                # Edycja współrzędnych = PRZESUWANIE
                new_x = st.number_input(f"X##{i}", value=float(note['x']), key=f"nx_{i}")
                new_y = st.number_input(f"Y##{i}", value=float(note['y']), key=f"ny_{i}")
                new_t = st.text_input(f"Tekst##{i}", value=note['text'], key=f"nt_{i}")
                
                if new_x != note['x'] or new_y != note['y'] or new_t != note['text']:
                    st.session_state.annotations[i] = {'x': new_x, 'y': new_y, 'text': new_t}
                    st.rerun()
                
                if st.button("Usuń", key=f"rm_note_{i}"):
                    st.session_state.annotations.pop(i)
                    st.rerun()

    # LINIE REFERENCYJNE
    with st.expander("📏 Linie Referencyjne", expanded=False):
        with st.form("add_line"):
            ax_type = st.selectbox("Oś", ["x", "y"])
            val = st.number_input("Wartość", value=0.0)
            if st.form_submit_button("Dodaj"):
                st.session_state.ref_lines.append({'axis': ax_type, 'value': val, 'color': 'white', 'style': 'Przerywana', 'width': 1})
                st.rerun()
        
        if st.session_state.ref_lines:
            st.write("---")
            for i, line in enumerate(st.session_state.ref_lines):
                c1, c2 = st.columns([3, 1])
                # Przesuwanie wartością
                new_v = c1.number_input(f"{line['axis'].upper()}", value=float(line['value']), key=f"lv_{i}")
                if new_v != line['value']:
                    st.session_state.ref_lines[i]['value'] = new_v
                    st.rerun()
                
                if c2.button("X", key=f"rm_line_{i}"):
                    st.session_state.ref_lines.pop(i)
                    st.rerun()

# --- EKSPORT ---
st.divider()
with st.expander("💾 Eksport (Pobierz Wykres)"):
    col_e1, col_e2 = st.columns(2)
    
    # Generowanie statycznego obrazka do pobrania (wysoka jakość)
    img_bytes = fig.to_image(format="png", width=1200, height=800, scale=2)
    pdf_bytes = fig.to_image(format="pdf", width=1200, height=800) # Plotly PDF export

    col_e1.download_button("Pobierz PNG", data=img_bytes, file_name="wykres.png", mime="image/png")
    col_e2.download_button("Pobierz PDF", data=pdf_bytes, file_name="wykres.pdf", mime="application/pdf")
