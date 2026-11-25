"""Utilidades de validación y saneamiento para entradas y salidas del sistema.

Las restricciones HTML/JS son solo comodidad: la seguridad real se aplica aquí,
en el servidor, antes de guardar o de entregar archivos al navegador.
"""

from decimal import Decimal, InvalidOperation

# Límites para archivos Excel importados (evita DoS por archivos enormes).
MAX_UPLOADED_BYTES = 5 * 1024 * 1024
MAX_EXCEL_ROWS = 5000

# Prefijos que Excel/CSV interpretan como fórmula al abrir el archivo.
_PREFIXOS_FORMULA = ('=', '+', '-', '@', '\t', '\r')


def sanitizar_valor_exportacion(valor):
    """Neutraliza la inyección de fórmulas en celdas de Excel/CSV.

    Un valor que empieza con =, +, - o @ se interpreta como fórmula al abrirlo
    en Excel. Anteponer un apóstrofo lo fuerza a texto sin cambiar su lectura.
    """
    if not isinstance(valor, str):
        return valor
    if valor.startswith(_PREFIXOS_FORMULA):
        return "'" + valor
    return valor


def fila_csv_segura(valores):
    """Aplica ``sanitizar_valor_exportacion`` a todos los valores de una fila."""
    return [sanitizar_valor_exportacion(v) for v in valores]


def proteger_exportacion_excel(wb):
    """Sanitiza todas las celdas de texto de un Workbook antes de guardarlo."""
    for ws in wb.worksheets:
        for fila in ws.iter_rows():
            for celda in fila:
                if isinstance(celda.value, str):
                    celda.value = sanitizar_valor_exportacion(celda.value)
    return wb


def validar_archivo_excel(archivo, extensiones=('.xlsx', '.xlsm')):
    """Devuelve un mensaje de error o ``None`` si el archivo es aceptable."""
    if not archivo:
        return 'Selecciona un archivo Excel.'
    nombre = (archivo.name or '').lower()
    if not nombre.endswith(tuple(extensiones)):
        return f'El archivo debe ser {" o ".join(extensiones)}.'
    if archivo.size > MAX_UPLOADED_BYTES:
        return f'El archivo supera el tamaño máximo de {MAX_UPLOADED_BYTES // (1024 * 1024)} MB.'
    return None


def iterar_filas_excel(ws, max_filas=MAX_EXCEL_ROWS):
    """Itera como máximo ``max_filas`` filas de la hoja activa."""
    for numero, fila in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if numero - 1 > max_filas:
            raise ValueError(f'El archivo supera el límite de {max_filas} filas.')
        yield numero, fila


def monto_no_negativo(valor, campo='El monto', defecto=Decimal('0.00')):
    """Convierte a Decimal y rechaza valores negativos o no numéricos."""
    if valor is None or valor == '':
        return defecto
    try:
        monto = Decimal(str(valor))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f'{campo} debe ser un número válido.')
    if monto < 0:
        raise ValueError(f'{campo} no puede ser negativo.')
    return monto
