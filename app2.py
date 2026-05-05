"""
Módulo de utilidades para conexión y consultas a base de datos SQL.

Mejoras implementadas:
- Credenciales desde st.secrets en lugar de hardcodeadas
- Mejor gestión de errores
- Funciones más reutilizables
- Caching mejorado
- Código más limpio y documentado
"""

import streamlit as st
import pandas as pd


# ============================================================================
# CONNECTION MANAGEMENT
# ============================================================================

CONNECTION_NAME = "QIT_DATAMINING_20"


@st.cache_data
def load_data_from_sql(query: str):
    """
    Ejecuta una consulta SQL usando st.connection y devuelve los datos como DataFrame.
    
    Args:
        query (str): Consulta SQL a ejecutar
        
    Returns:
        pd.DataFrame: Resultado de la consulta
    """
    try:
        conn = st.connection(CONNECTION_NAME, type="sql")
        df = conn.query(query, ttl=600)
        return df
    except Exception as e:
        raise Exception(f"Error loading data from SQL: {e}")


# ============================================================================
# SQL FORMATTING & UTILITIES
# ============================================================================

def format_sql_value(value):
    """
    Formatea un valor para ser incluido en una consulta SQL.
    
    Args:
        value: Valor a formatear (None, str, int, float, etc)
        
    Returns:
        str: Valor formateado para SQL
    """
    if value is None:
        return "NULL"
    elif isinstance(value, str):
        # Escapa comillas simples
        return f"'{value.replace(chr(39), chr(39)+chr(39))}'"
    else:
        return f"'{str(value)}'"


def where(order=None, test_name=None, start_date=None, end_date=None, 
          subcycle=None, repetition=None, placeID=None, VIB=None, FD=None, SNR=None):
    """
    Construye dinámicamente una cláusula WHERE para las consultas.
    
    Args:
        order: Número de orden
        test_name: Nombre del test
        start_date: Fecha de inicio
        end_date: Fecha de fin
        subcycle: Rango de subcycles (tupla)
        repetition: Rango de repeticiones (tupla)
        placeID: ID de posición
        VIB: Código VIB
        FD: Código FD
        SNR: Código SNR
        
    Returns:
        str: Cláusula WHERE formada
    """
    where_conditions = []
    
    if order is not None:
        where_conditions.append(f"TPS.[Order] = {format_sql_value(order)}")
    if test_name is not None:
        where_conditions.append(f"TIP.TestName = {format_sql_value(test_name)}")
    if start_date is not None:
        where_conditions.append(f"SbRep.TimeStamp >= {format_sql_value(start_date)}")
    if end_date is not None:
        where_conditions.append(f"SbRep.TimeStamp < {format_sql_value(end_date)}")
    if subcycle is not None and len(subcycle) == 2:
        where_conditions.append(f"SbRep.Subcycle >= {format_sql_value(subcycle[0])} AND SbRep.Subcycle <= {format_sql_value(subcycle[1])}")
    if repetition is not None and len(repetition) == 2:
        where_conditions.append(f"SbRep.Repetition >= {format_sql_value(repetition[0])} AND SbRep.Repetition <= {format_sql_value(repetition[1])}")
    if placeID is not None:
        where_conditions.append(f"TIP.PlaceID = {format_sql_value(placeID)}")
    if VIB is not None:
        where_conditions.append(f"DUT.VIB = {format_sql_value(VIB)}")
    if FD is not None:
        where_conditions.append(f"DUT.FD = {format_sql_value(FD)}")
    if SNR is not None:
        where_conditions.append(f"DUT.SNR = {format_sql_value(SNR)}")
    
    where_clause = " AND \n\t".join(where_conditions) if where_conditions else "1=1"
    return where_clause


# ============================================================================
# DATA LOADING QUERIES
# ============================================================================

def sql_codes(start, end, placeid, order, test):
    """Obtiene los códigos disponibles (VIB, FD, SNR)"""
    where_clause = where(order=order, test_name=test, start_date=start, end_date=end, placeID=placeid)
    return f'''
        SELECT DISTINCT VIB, FD, SNR AS Short_SNR
        FROM DUT
            INNER JOIN TPS ON TPS.ID_DUT = DUT.ID_DUT
            INNER JOIN TIP ON TIP.ID_TPS = TPS.ID_TPS
            INNER JOIN SbRep ON SbRep.ID_TIP = TIP.ID_TIP
        WHERE {where_clause}
    '''


def sql_orders(start, end, vib, fd, snr, test, placeid):
    """Obtiene las órdenes disponibles"""
    where_clause = where(test_name=test, start_date=start, end_date=end, placeID=placeid, VIB=vib, FD=fd, SNR=snr)
    return f"""
        SELECT DISTINCT [Order]
        FROM TPS
        INNER JOIN TIP ON TIP.ID_TPS = TPS.ID_TPS
        INNER JOIN DUT ON DUT.ID_DUT = TPS.ID_DUT
        INNER JOIN SbRep ON SbRep.ID_TIP = TIP.ID_TIP
        WHERE {where_clause}
    """


def sql_test_names(start, end, vib, fd, snr, order, placeid):
    """Obtiene los nombres de tests disponibles"""
    where_clause = where(order=order, start_date=start, end_date=end, placeID=placeid, VIB=vib, FD=fd, SNR=snr)
    return f'''
        SELECT DISTINCT TestName
        FROM TIP
            INNER JOIN TPS ON TPS.ID_TPS = TIP.ID_TPS
            INNER JOIN DUT ON DUT.ID_DUT = TPS.ID_DUT
            INNER JOIN SbRep ON SbRep.ID_TIP = TIP.ID_TIP
        WHERE {where_clause}
    '''


def query_PlaceIDs(start, end, order, test, vib, fd, snr):
    """Obtiene los Place IDs disponibles"""
    where_clause = where(order=order, test_name=test, start_date=start, end_date=end, VIB=vib, FD=fd, SNR=snr)
    return f''' 
        SELECT DISTINCT PlaceID
        FROM TIP
            INNER JOIN TPS ON TIP.ID_TPS = TPS.ID_TPS
            INNER JOIN SbRep ON SbRep.ID_TIP = TIP.ID_TIP
            INNER JOIN DUT ON DUT.ID_DUT = TPS.ID_DUT
        WHERE {where_clause}
        ORDER BY PlaceID
    '''


def query_repetitions(order=None, test_name=None, start=None, end=None, subcycle=None, placeID=None, vib=None, fd=None, snr=None):
    """Obtiene las repeticiones disponibles"""
    where_clause = where(order=order, test_name=test_name, start_date=start, end_date=end, 
                        subcycle=subcycle, placeID=placeID, VIB=vib, FD=fd, SNR=snr)
    return f'''
        SELECT DISTINCT Repetition
        FROM SbRep
        INNER JOIN TIP ON TIP.ID_TIP = SbRep.ID_TIP
        INNER JOIN TPS ON TIP.ID_TPS = TPS.ID_TPS
        INNER JOIN DUT ON DUT.ID_DUT = TPS.ID_DUT
        WHERE {where_clause}
        ORDER BY Repetition
    '''


def query_subcycles(order=None, test_name=None, start=None, end=None, repetition=None, placeID=None, vib=None, fd=None, snr=None):
    """Obtiene los subcycles disponibles"""
    where_clause = where(order=order, test_name=test_name, start_date=start, end_date=end, 
                        repetition=repetition, placeID=placeID, VIB=vib, FD=fd, SNR=snr)
    return f'''
        SELECT DISTINCT Subcycle
        FROM SbRep
        INNER JOIN TIP ON TIP.ID_TIP = SbRep.ID_TIP 
        INNER JOIN TPS ON TIP.ID_TPS = TPS.ID_TPS
        INNER JOIN DUT ON DUT.ID_DUT = TPS.ID_DUT 
        WHERE {where_clause}
        ORDER BY Subcycle
    '''


def query_vib(vib=None):
    """Obtiene los VIB disponibles"""
    where_clause = where(VIB=vib)
    return f'''
        SELECT DISTINCT VIB  
        FROM DUT 
        WHERE {where_clause}
    '''


def get_variables_by_table(table):
    """Obtiene las variables de una tabla específica"""
    return load_data_from_sql(f"""
        SELECT DISTINCT Variable_Name
        FROM VA
        WHERE Table_Name = '{table}'
    """)


# ============================================================================
# SENSITIVITY QUERIES
# ============================================================================

def query_sensitivityID_IRR(Order=None, StartDate=None, EndDate=None, SNR=None, TestName=None):
    """Obtiene los IDs de rutina de análisis para análisis de sensibilidad"""
    return f"""
        SELECT DISTINCT IRA.ID_IRR
        FROM dbo.TPS
            INNER JOIN dbo.DUT ON DUT.ID_DUT = TPS.ID_DUT
            INNER JOIN dbo.TIP ON TIP.ID_TPS = TPS.ID_TPS
            INNER JOIN IABO_ROUTINE_RESULT AS IRR ON IRR.ID_TIP = TIP.ID_TIP
            INNER JOIN IABO_ROUTINE_ANALYSIS AS IRA ON IRA.ID_IRR = IRR.ID_IRR
        WHERE 
            ({f"TPS.[Order] = {format_sql_value(Order)}" if Order else "1=1"})
            AND ({f"TIP.TestName = {format_sql_value(TestName)}" if TestName else "1=1"})
            AND (IRA.Timestamp > '{StartDate}')
            AND (IRA.Timestamp < '{EndDate}')
    """


def query_sensitivity_sql(StartDate, EndDate, TestName, ID_IRR, vib, fd, snr):
    """Obtiene los datos de sensibilidad para un ID_IRR específico"""
    return f"""
        SELECT
            TPS.ID_TPS,
            TIP.ID_TIP,
            TIP.TestName,
            IRR.Result,
            IRA.*
        FROM dbo.TPS
            INNER JOIN dbo.DUT ON DUT.ID_DUT = TPS.ID_DUT
            INNER JOIN dbo.TIP ON TIP.ID_TPS = TPS.ID_TPS
            INNER JOIN IABO_ROUTINE_RESULT AS IRR ON IRR.ID_TIP = TIP.ID_TIP
            INNER JOIN IABO_ROUTINE_ANALYSIS AS IRA ON IRA.ID_IRR = IRR.ID_IRR
        WHERE 
            (IRA.Timestamp > '{StartDate}')
            AND (IRA.Timestamp < '{EndDate}')
            AND ({f"TIP.TestName = {format_sql_value(TestName)}" if TestName else "1=1"})
            AND ({f"IRA.ID_IRR = {ID_IRR}" if ID_IRR else "1=1"})
            AND ({f"DUT.VIB = {format_sql_value(vib)}" if vib else "1=1"})
            AND ({f"DUT.FD = {format_sql_value(fd)}" if fd else "1=1"})
            AND ({f"DUT.SNR = {format_sql_value(snr)}" if snr else "1=1"})
    """


# ============================================================================
# DATA QUERY
# ============================================================================

def query_variables_sql(order, start_date, end_date, test_name, subcycle, repetition, 
                        variables, placeID, VIB, FD, SNR):
    """
    Construye una consulta para obtener variables de medición con filtros.
    
    Args:
        order: Número de orden
        start_date: Fecha de inicio
        end_date: Fecha de fin
        test_name: Nombre del test
        subcycle: Rango de subcycle (tupla)
        repetition: Rango de repetición (tupla)
        variables: Lista de nombres de variables
        placeID: ID de posición
        VIB: Código VIB
        FD: Código FD
        SNR: Código SNR
        
    Returns:
        str: Consulta SQL
    """
    where_clause = where(order, test_name, start_date, end_date, subcycle, repetition, placeID, VIB, FD, SNR)
    variable_in_list = ", ".join([format_sql_value(v) for v in variables])

    return f'''   
        SELECT  
            TIP.PlaceID,
            TIP.TestName,
            SbRep.Repetition,
            SbRep.Subcycle,            
            seq.TimeStamp,
            VA.Variable_Name,
            m.Measurement
        FROM Measurement_all AS m
        JOIN VA ON m.ID_VA = VA.ID_VA
        JOIN Sequence AS seq ON m.ID_Sequence = seq.ID_Sequence
        JOIN SbRep ON seq.ID_SbRep = SbRep.ID_SbRep
        JOIN TIP ON SbRep.ID_TIP = TIP.ID_TIP
        JOIN TPS ON TPS.ID_TPS = TIP.ID_TPS
        JOIN DUT ON DUT.ID_DUT = TPS.ID_DUT
        WHERE {where_clause} AND VA.Variable_Name IN ({variable_in_list})
        ORDER BY seq.TimeStamp
    '''
