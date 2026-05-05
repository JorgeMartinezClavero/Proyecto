import pandas as pd
import streamlit as st
import datetime
import matplotlib.pyplot as plt
import seaborn as sns
import altair as alt
import numpy as np
from datetime import timedelta 
import plotly.graph_objects as go 

import db_utils2 as db
import SNR_functions

# ============================================================================
# CONFIGURATION & CONSTANTS
# ============================================================================

DEFAULT_COLORS = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', 
                  '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']

TEST_TYPES = ['Data', 'Sensitivity', 'Last Tests']

SESSION_STATE_DEFAULTS = {
    'PlaceID': None,
    'Order': None,
    'test': None,
    'vib': None,
    'fd': None,
    'snr': None,
    'code': None
}

# ============================================================================
# CACHED FUNCTIONS
# ============================================================================

@st.cache_data
def convert_df(df):
    """Convierte DataFrame a CSV con encoding UTF-8"""
    return df.to_csv(index=False, sep=';').encode('utf-8')


@st.cache_data
def load_snr_excel():
    """Carga el Excel de SNR una sola vez"""
    return pd.read_excel('Devuelve_SNR_18_dígitos.xlsx', sheet_name='EAN')


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def initialize_session_state():
    """Inicializa todas las variables de sesión necesarias"""
    for key, default_value in SESSION_STATE_DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = default_value


def datetime_range_picker(start, end, key):
    """
    Crea un selector de rango de fecha y hora con valores iniciales relativos

    Args:
        start (int): El desplazamiento inicial para la fecha de inicio en minutos desde ahora.
        end (int): El desplazamiento inicial para la fecha de fin en minutos desde ahora.
        key (str): Una clave única para el componente.

    Returns:
        tuple: Una tupla con las fechas y horas de inicio y fin (start_datetime, end_datetime).
    """
    state_key_start = f"{key}_start"
    state_key_end = f"{key}_end"
    now = datetime.datetime.now()

    if state_key_start not in st.session_state:
        st.session_state[state_key_start] = now + timedelta(minutes=start)
        st.session_state[state_key_end] = now + timedelta(minutes=end)

    col1, col2 = st.columns(2)

    with col1:
        start_date = st.datetime_input(
            "Start Date",
            value=st.session_state[state_key_start],
            key=f"{key}_dt_start"
        )

    with col2:
        end_date = st.datetime_input(
            "End Date",
            value=st.session_state[state_key_end],
            key=f"{key}_dt_end"
        )
        
    st.session_state[state_key_start] = start_date
    st.session_state[state_key_end] = end_date

    return st.session_state[state_key_start], st.session_state[state_key_end]


def load_codes_and_calculate_snr(placeid=None, order=None, test=None):
    """
    Carga códigos de BD y calcula SNR - función reutilizable
    
    Returns:
        pd.DataFrame: DataFrame con SNR calculado
    """
    try:
        codes = db.load_data_from_sql(db.sql_codes(
            start=None,
            end=None, 
            placeid=placeid, 
            order=order, 
            test=test
        ))
    except Exception as e:
        st.error(f"Error al cargar datos desde la base de datos: {e}")
        return pd.DataFrame()
    
    if codes.empty:
        return codes
    
    df_snr = load_snr_excel()
    codes['SNR'] = codes.apply(
        lambda row: SNR_functions.get_SNR(row['VIB'], row['FD'], row['Short_SNR'], df_snr), 
        axis=1
    )
    
    return codes


def get_code_tuple(codes, selected_snr):
    """
    Extrae la tupla de código (VIB, FD, Short_SNR, SNR) del DataFrame

    Returns:
        list: [VIB, FD, Short_SNR, SNR] o [None, None, None, None]
    """
    if selected_snr is None or codes.empty:
        return [None, None, None, None]
    
    try:
        fila_seleccionada = codes.loc[codes['SNR'] == selected_snr].iloc[0]
        return [
            fila_seleccionada['VIB'],
            fila_seleccionada['FD'],
            fila_seleccionada['Short_SNR'],
            fila_seleccionada['SNR']
        ]
    except (IndexError, KeyError):
        return [None, None, None, None]


def get_range_slider_value(options, state_key, label, key):
    """
    Maneja la lógica de rangos (single value vs range)
    
    Returns:
        tuple: (start, end) del rango
    """
    if len(options) == 0:
        st.write(f'No {label.lower()} for these filters')
        return None
    elif options[0] == options[-1]:
        st.write(f"{label} = {options[0]}")
        st.session_state[state_key] = (options[0], options[0])
        return st.session_state[state_key]
    else: 
        st.slider(f'Select {label} Range: ', 
                 min_value=options[0], 
                 max_value=options[-1],
                 value=(options[0], options[-1]), 
                 step=1, 
                 key=key)
        return st.session_state[key]


# ============================================================================
# SENSITIVITY SECTION
# ============================================================================

def render_sensitivity_section():
    """Renderiza la sección de Sensitivity"""
    
    date_range_tuple = datetime_range_picker(start=-30, end=0, key='range_picker_sens')
    if date_range_tuple is None:
        st.error("Date range selection failed")
        return
    
    start_datetime, end_datetime = date_range_tuple
    rango_fechas = [start_datetime, end_datetime]

    col11, col12 = st.columns(2)
    col21, col22 = st.columns(2)
    
    initialize_session_state()

    # Cargar códigos
    codes = load_codes_and_calculate_snr(
        placeid=st.session_state.PlaceID,
        order=st.session_state.Order, 
        test=st.session_state.test
    )
    
    if codes.empty:
        return

    with col11:
        st.session_state['selected_snr'] = st.selectbox(
            "Select the SNR: ", 
            options=codes['SNR'], 
            index=0 if len(codes['SNR']) == 1 else None
        )
        selected_snr = st.session_state.selected_snr

    code = get_code_tuple(codes, selected_snr)

    # Test names
    sql_test_names = f'''SELECT DISTINCT TestName
        FROM TIP
            INNER JOIN IABO_ROUTINE_RESULT AS IRR ON IRR.ID_TIP=TIP.ID_TIP
            INNER JOIN IABO_ROUTINE_ANALYSIS AS IRA ON IRA.ID_IRR=IRR.ID_IRR
        WHERE IRA.Timestamp > '{rango_fechas[0]}' AND IRA.Timestamp < '{rango_fechas[1]}' '''

    test_names = db.load_data_from_sql(sql_test_names)
    with col22:
        st.selectbox('Select the Test: ', test_names, key='test')
        option = st.session_state.test

    # Orders
    orders = db.load_data_from_sql(db.sql_orders(
        start=rango_fechas[0], 
        end=rango_fechas[1], 
        vib=code[0], 
        fd=code[1], 
        snr=code[2], 
        test=st.session_state.test, 
        placeid=st.session_state.PlaceID
    ))
    with col21:
        st.selectbox("Select the Order: ", orders, index=None, key='Order')

    # PlaceIDs
    PlaceIDs = db.load_data_from_sql(db.query_PlaceIDs(
        start=rango_fechas[0], 
        end=rango_fechas[1], 
        order=st.session_state.Order, 
        test=st.session_state.test, 
        vib=code[0], 
        fd=code[1], 
        snr=code[2]
    ))
    with col12:
        st.selectbox('Select the Position: ', PlaceIDs, index=None, key='PlaceID')

    # Get sensitivity data
    sql = db.query_sensitivityID_IRR(StartDate=rango_fechas[0], EndDate=rango_fechas[1], TestName=option)
    IDs_IRR = db.load_data_from_sql(sql)
    df_sensitivity = {}

    for id in IDs_IRR['ID_IRR']:
        sql_sensitivity = db.query_sensitivity_sql(
            StartDate=rango_fechas[0], 
            EndDate=rango_fechas[1], 
            TestName=option, 
            ID_IRR=id, 
            vib=code[0], 
            fd=code[1], 
            snr=code[2]
        )
        df_sensitivity[id] = db.load_data_from_sql(sql_sensitivity)
        pattern = '^SQ0(?=.)'
        df_sensitivity[id]['Touch'] = df_sensitivity[id]['Touch'].str.replace(pattern, 'SQ', regex=True)

    # Graphics
    col_g1, col_g2 = st.columns(2)
    
    with col_g1:
        if st.button('Graphic 1'): 
            fig, ax = plt.subplots()
            df_sensitivity[IDs_IRR['ID_IRR'].iloc[0]].plot(
                x='Touch', 
                y=['DeltaAverage', 'UpperDeltaLimit', 'LowerDeltaLimit'], 
                kind='line', 
                marker='o', 
                ax=ax, 
                legend=True, 
                color=['black', 'blue', 'green']
            )
            ax.set_xticks(range(len(df_sensitivity[IDs_IRR['ID_IRR'].iloc[0]])))
            ax.tick_params(axis='x', labelsize=8) 
            ax.set_xticklabels(df_sensitivity[IDs_IRR['ID_IRR'].iloc[0]]['Touch'], rotation=45, ha='right') 
            ax.set_xlabel("Touch")
            plt.xticks(rotation=45) 
            st.pyplot(fig)

    with col_g2:
        if st.button('Graphic 2'):
            all_data_list = []
            for id, df in df_sensitivity.items():
                temp_df = df[['Touch', 'LowerDeltaLimit', 'UpperDeltaLimit', 'DeltaAverage']].copy()
                temp_df['id'] = id
                all_data_list.append(temp_df)

            all_data = pd.concat(all_data_list, ignore_index=True)

            most_common_limits = all_data.groupby('Touch', sort=False).agg({
                'LowerDeltaLimit': lambda x: x.mode().iloc[0],
                'UpperDeltaLimit': lambda x: x.mode().iloc[0],
            }).reset_index()
            most_common_limits.rename(columns={
                'LowerDeltaLimit': 'MostCommonLowerDeltaLimit',
                'UpperDeltaLimit': 'MostCommonUpperDeltaLimit'
            }, inplace=True)

            stats = all_data.groupby('Touch', sort=False).agg({
                'DeltaAverage': ['min', 'max', 'mean', 'std']
            }).reset_index()
            stats.columns = ['Touch', 'Minimum', 'Maximum', 'Mean', 'StandardDeviation']

            table_sensitivity = pd.merge(stats, most_common_limits, on='Touch', how='inner')

            fig, ax = plt.subplots(figsize=(10, 6)) 
            colors = sns.color_palette('rocket_r', n_colors=len(df_sensitivity))

            for i, (id, df) in enumerate(df_sensitivity.items()):
                df.plot(
                    x='Touch', 
                    y=['DeltaAverage'], 
                    kind='line', 
                    marker='o', 
                    ax=ax, 
                    color=[colors[i]], 
                    style=['-'], 
                    legend=False, 
                    grid=True
                )

            most_common_limits.plot(
                x='Touch', 
                y=['MostCommonLowerDeltaLimit'], 
                kind='line', 
                marker='o', 
                ax=ax, 
                color='green', 
                style=['--'], 
                grid=True,
                label=['LowerDeltaLimit'] 
            )
            most_common_limits.plot(
                x='Touch', 
                y=['MostCommonUpperDeltaLimit'], 
                kind='line', 
                marker='o', 
                ax=ax, 
                color='blue', 
                style=['--'], 
                grid=True,
                label=['UpperDeltaLimit'] 
            )

            first_df = list(df_sensitivity.values())[0]
            ax.set_xticks(range(len(first_df)))
            ax.set_xticklabels(first_df['Touch'], rotation=30, ha='right')
            ax.tick_params(axis='x', labelsize=10)
            ax.set_xlabel("")
            ax.set_title("Combined Sensitivity Plots")
            plt.tight_layout()

            st.pyplot(fig)
            st.table(table_sensitivity.set_index("Touch"))


# ============================================================================
# DATA SECTION
# ============================================================================

def render_data_section():
    """Renderiza la sección de Data"""
    
    filter_by_date = st.checkbox("Enable filter by date range", key='filtrar_fechas_activo')
    if st.session_state.filtrar_fechas_activo:
        date_range_tuple = datetime_range_picker(start=-30, end=0, key='range_picker_data')
        if date_range_tuple is not None:
            start_datetime, end_datetime = date_range_tuple
            rango_fechas = [start_datetime, end_datetime]
        else:
            return
    else:
        rango_fechas = [None, None]

    initialize_session_state()

    col11, col12 = st.columns(2)
    col41, col42 = st.columns(2)
    col21, col22 = st.columns(2)

    # Load codes
    codes = load_codes_and_calculate_snr(
        placeid=st.session_state.PlaceID,
        order=st.session_state.Order, 
        test=st.session_state.test
    )
    
    if codes.empty:
        return

    with col11:
        st.session_state['selected_snr'] = st.selectbox(
            "Select SNR: ", 
            options=codes['SNR'], 
            index=0 if len(codes['SNR']) == 1 else None
        )
        selected_snr = st.session_state.selected_snr

    code = get_code_tuple(codes, selected_snr)

    # VIB selection
    with col41:
        vibs = db.load_data_from_sql(db.query_vib(vib=code[0]))
        st.selectbox('Select SKU:', vibs, index=None, key='VIB')

    # Orders
    orders = db.load_data_from_sql(db.sql_orders(
        start=rango_fechas[0], 
        end=rango_fechas[1], 
        vib=code[0], 
        fd=code[1], 
        snr=code[2], 
        test=st.session_state.test, 
        placeid=st.session_state.PlaceID
    ))
    with col21:
        st.selectbox("Select Order: ", orders, index=None, key='Order')

    # Test names
    test_names = db.load_data_from_sql(db.sql_test_names(
        start=rango_fechas[0], 
        end=rango_fechas[1], 
        vib=code[0], 
        fd=code[1], 
        snr=code[2], 
        order=st.session_state.Order, 
        placeid=st.session_state.PlaceID
    ))
    with col22:
        st.selectbox('Select Test: ', test_names, index=None, key='test')

    # PlaceIDs
    PlaceIDs = db.load_data_from_sql(db.query_PlaceIDs(
        start=rango_fechas[0], 
        end=rango_fechas[1], 
        order=st.session_state.Order, 
        test=st.session_state.test, 
        vib=code[0], 
        fd=code[1], 
        snr=code[2]
    ))
    with col12:
        st.selectbox('Select Position: ', PlaceIDs, index=None, key='PlaceID')

    # Repetitions & Subcycles
    col31, col32 = st.columns(2)

    repetitions = db.load_data_from_sql(db.query_repetitions(
        start=rango_fechas[0], 
        end=rango_fechas[1], 
        order=st.session_state.Order, 
        test_name=st.session_state.test, 
        placeID=st.session_state.PlaceID, 
        subcycle=None, 
        vib=code[0], 
        fd=code[1], 
        snr=code[2]
    ))
    repetition_options = repetitions['Repetition'].tolist()

    with col31:
        repetition = get_range_slider_value(repetition_options, 'Repetition', 'Repetition', 'Repetition')

    subcycles = db.load_data_from_sql(db.query_subcycles(
        start=rango_fechas[0], 
        end=rango_fechas[1], 
        order=st.session_state.Order, 
        test_name=st.session_state.test, 
        placeID=st.session_state.PlaceID, 
        repetition=st.session_state.get('Repetition'), 
        vib=code[0], 
        fd=code[1], 
        snr=code[2]
    ))
    subcycle_options = subcycles['Subcycle'].tolist()

    with col32:
        subcycle = get_range_slider_value(subcycle_options, 'Subcycle', 'Subcycle', 'Subcycle')

    # Variable selection
    conn = st.connection('QIT_DATAMINING_20', type='sql')
    variable_options = conn.query("""SELECT DISTINCT Variable_Name
        FROM VA
        WHERE Variable_Name <> ''
        ORDER BY Variable_Name""", ttl=600)

    if len(variable_options) != 0:
        variables_list = st.multiselect('Select Variables: ', variable_options)
        if variables_list:
            st.text(f"Selected Variables: {', '.join(variables_list)}")
    else:
        variables_list = []
        st.info("No variables available")

    # Load data
    if 'df_cargado' not in st.session_state:
        st.session_state.df_cargado = pd.DataFrame()

    if st.button("Load data"):
        if len(variables_list) == 0:
            st.info('No variable selected.')
        else:
            sql_data = db.query_variables_sql(
                order=st.session_state.Order,
                start_date=rango_fechas[0],
                end_date=rango_fechas[1],
                test_name=st.session_state.test,
                subcycle=subcycle,
                repetition=repetition,
                variables=variables_list,
                placeID=st.session_state.PlaceID,
                VIB=code[0],
                FD=code[1],
                SNR=code[2]
            )
            df = db.load_data_from_sql(sql_data)
            if df.empty:
                st.info('No data available.')
            else: 
                st.success("Data loaded!")
            
            st.session_state.df_cargado = df

    # Display and export
    if 'df_cargado' in st.session_state and not st.session_state.df_cargado.empty:
        st.dataframe(st.session_state.df_cargado)
        st.write(f"{len(st.session_state.df_cargado)} Rows Loaded")
        csv = convert_df(st.session_state.df_cargado)
        st.download_button(
            label="Download data as CSV", 
            data=csv, 
            file_name=f"data_{datetime.date.today()}.csv",
            mime="text/csv", 
            key='download-csv'
        )

    # Visualization
    df = st.session_state.df_cargado
    if df is not None and not df.empty:
        render_data_visualization(df)


def render_data_visualization(df):
    """Renderiza la visualización de datos"""
    
    st.subheader('Data Visualization')
    
    with st.sidebar:
        st.header("⚙️ Graph Filters")

        time_options = sorted(df['TimeStamp'].unique())
        start_time, end_time = st.select_slider(
            'TimeStamp Range:', 
            options=time_options, 
            value=(time_options[0], time_options[-1]),
            format_func=lambda dt: pd.to_datetime(dt).strftime('%d/%m/%y %H:%M')
        )

        rep_options = sorted(df['Repetition'].unique())
        if rep_options[0] >= rep_options[-1]:
            start_rep = end_rep = rep_options[0]
        else:
            start_rep, end_rep = st.slider('Repetition Range:', rep_options[0], rep_options[-1], (rep_options[0], rep_options[-1]))

        sub_options = sorted(df['Subcycle'].unique())
        if sub_options[0] >= sub_options[-1]:
            start_sub = end_sub = sub_options[0]
        else: 
            start_sub, end_sub = st.slider('Subcycle Range:', sub_options[0], sub_options[-1], (sub_options[0], sub_options[-1]))

    df_filtrado = df[
        (df['TimeStamp'] >= start_time) & (df['TimeStamp'] <= end_time) &
        (df['Repetition'] >= start_rep) & (df['Repetition'] <= end_rep) &
        (df['Subcycle'] >= start_sub) & (df['Subcycle'] <= end_sub)
    ]

    if df_filtrado.empty:
        st.warning("No data found for the selected filter combination. Please broaden the ranges.")
        return

    if 'Timestamp' in df_filtrado.columns:
        df_filtrado['Timestamp'] = pd.to_datetime(df_filtrado['Timestamp'], errors='coerce')
        df_filtrado.dropna(subset=['Timestamp'], inplace=True)
    
    base_columns = [col for col in df_filtrado.columns if col not in ['Measurement', 'Variable_Name']]
    direct_columns_to_plot = ['Repetition', 'Subcycle']
    pivotable_variables = sorted(df_filtrado['Variable_Name'].unique().tolist())
    available_variables = pivotable_variables + direct_columns_to_plot

    Multiple_Axis = st.toggle("Multiple Axis", value=False)
    col1, col2 = st.columns([0.4, 1])
    
    with col1:
        x_column = st.selectbox("Select the variable for the X-axis", base_columns, index=min(4, len(base_columns)-1))
    with col2:
        y_columns_1 = st.multiselect("Select the variables for the Y-axis", available_variables)

    y_columns_2 = []
    if Multiple_Axis:
        remaining_vars = [v for v in available_variables if v not in y_columns_1]
        y_columns_2 = st.multiselect("Select additional variables for the second Y-axis", remaining_vars)
    
    # Color mapping
    color_mapping = {}
    with st.sidebar.expander("Edit Variable Colors"):
        for i, var_name in enumerate(available_variables):
            default_color = DEFAULT_COLORS[i % len(DEFAULT_COLORS)]
            color = st.color_picker(f"Color for {var_name}", value=default_color, key=f"color_{var_name}")
            color_mapping[var_name] = color

    all_selected_vars = y_columns_1 + y_columns_2
    
    if x_column and all_selected_vars:
        vars_to_pivot = [var for var in all_selected_vars if var in pivotable_variables]
        direct_vars_to_plot = [var for var in all_selected_vars if var in direct_columns_to_plot]

        if vars_to_pivot:
            df_pivoted = df_filtrado[df_filtrado['Variable_Name'].isin(vars_to_pivot)].pivot_table(
                index=x_column,
                columns='Variable_Name',
                values='Measurement',
                aggfunc='mean'
            ).reset_index()
        else:
            df_pivoted = pd.DataFrame(df_filtrado[[x_column]].drop_duplicates().sort_values(by=x_column))

        if direct_vars_to_plot:
            df_direct = df_filtrado.groupby(x_column)[direct_vars_to_plot].mean().reset_index()
            df_pivoted = pd.merge(df_pivoted, df_direct, on=x_column, how='left')
        
        fig = go.Figure()

        for col in y_columns_1:
            if col in df_pivoted.columns:
                fig.add_trace(go.Scatter(
                    x=df_pivoted[x_column], 
                    y=df_pivoted[col], 
                    mode='lines', 
                    name=col,
                    line=dict(color=color_mapping.get(col, None), width=1.75),
                    connectgaps=True
                ))

        for col in y_columns_2:
            if col in df_pivoted.columns:
                fig.add_trace(go.Scatter(
                    x=df_pivoted[x_column], 
                    y=df_pivoted[col], 
                    mode='lines', 
                    name=f"{col} (sec. axis)", 
                    yaxis="y2",
                    line=dict(color=color_mapping.get(col, None), width=1.75),
                    connectgaps=True
                ))

        fig.update_layout(
            showlegend=True,
            xaxis_title=x_column,
            yaxis_title="Primary Axis Values",
            yaxis2=dict(
                title="Secondary Axis Values",
                overlaying="y",
                side="right",
                visible=True if y_columns_2 else False
            ),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=40, r=40, t=80, b=40)
        )

        st.plotly_chart(fig, use_container_width=True)

    else:
        st.info("Please select an X-axis and at least one Y-axis variable to plot.")

    individual_analysis = st.toggle('Analysis by Individual Variable', value=False)
    if individual_analysis:
        grupos_filtrados = df_filtrado.groupby('Variable_Name')
        for valor, grupo_df in grupos_filtrados:
            with st.container(border=True):
                st.write(f"{valor}")
                
                chart = alt.Chart(grupo_df).mark_line(point=False, interpolate='monotone', strokeWidth=1.5).encode(
                    x=alt.X('TimeStamp:T', title='TimeStamp'),
                    y=alt.Y('Measurement:Q', title='Measurement', scale=alt.Scale(zero=False)),
                    tooltip=[
                        alt.Tooltip('TimeStamp:T', title='TimeStamp', format='%d-%m-%Y %H:%M'),
                        alt.Tooltip('Measurement:Q', title='Measurement', format='.2f'),
                        alt.Tooltip('Repetition:Q', title='Repetition'),
                        alt.Tooltip('Subcycle:Q', title='Subcycle'),
                    ],
                    color=alt.value(color_mapping[valor])
                ).interactive()
                
                st.altair_chart(chart, use_container_width=True)


# ============================================================================
# LAST TESTS SECTION
# ============================================================================

def render_last_tests_section():
    """Renderiza la sección de Last Tests"""
    st.write('Last tests: ')
    query = """
        SELECT TOP 20 [Order], TestName, PlaceID, Result,
        Start_TimeStamp, Final_TimeStamp, Current_Test_Hours, Total_Test_Hours
        FROM TPS
            INNER JOIN TIP ON TIP.ID_TPS = TPS.ID_TPS
        ORDER BY ID_TIP DESC; 
    """
    try:
        df_tests = db.load_data_from_sql(query)
        st.dataframe(df_tests, hide_index=True)
    except Exception as e:
        st.error(f"Error loading last tests: {e}")


# ============================================================================
# MAIN
# ============================================================================

def main():
    test_type = st.radio(label='Select Test Type:', options=TEST_TYPES, horizontal=True)

    if test_type == 'Last Tests':
        render_last_tests_section()
    elif test_type == 'Sensitivity':
        render_sensitivity_section()
    elif test_type == 'Data':
        render_data_section()


if __name__ == "__main__":
    main()
