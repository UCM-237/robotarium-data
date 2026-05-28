import re
from datetime import datetime
import matplotlib.pyplot as plt

# ==========================================
# 1. FUNCIÓN DE CARGA Y PARSEO AMPLIADA
# ==========================================
def cargar_datos_log_estimador(log_path):
    ts_pattern = r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})"
    
    # Captura la línea cíclica de tu estimador: "Usando posición ST: x=X, y=Y, θ=T"
    # Nota: Ajustamos la expresión regular para que coincida exactamente con tu formato de log
    estimador_pattern = r"Usando posición\s+([\w_]+):\s*x=([\d\.-]+),\s*y=([\d\.-]+),\s*(?:θ|theta)=([\d\.-]+)"
    
    critico_pattern = r"CRITICAL - Pared muy cercana"

    registros_estimador = []
    eventos_criticos = []

    print(f"[Carga] Analizando hilos de control en: {log_path}...")

    with open(log_path, 'r', encoding='utf-8') as file:
        for num_linea, linea in enumerate(file, 1):
            ts_match = re.search(ts_pattern, linea)
            if not ts_match:
                continue
            
            current_ts = datetime.strptime(ts_match.group(1), "%Y-%m-%d %H:%M:%S")
            est_match = re.search(estimador_pattern, linea)

            if est_match:
                registros_estimador.append({
                    'linea': num_linea,
                    'timestamp': current_ts,
                    'estado_estimador': est_match.group(1), # Ej: VISION, ODOM, ESTIMADO...
                    'x': float(est_match.group(2)),
                    'y': float(est_match.group(3)),
                    'theta': float(est_match.group(4)),
                    'detalle': linea.strip()
                })
            elif re.search(critico_pattern, linea):
                eventos_criticos.append({
                    'linea': num_linea,
                    'timestamp': current_ts,
                    'detalle': linea.strip()
                })

    print(f"[Carga] Éxito: {len(registros_estimador)} ciclos de estimación y {len(eventos_criticos)} alarmas críticas.")
    return registros_estimador, eventos_criticos


# ==========================================
# 2. FUNCIÓN DE ANÁLISIS DE TRANSICIONES Y FALLOS
# ==========================================
def analizar_comportamiento_estimador(registros, alarmas):
    """
    Analiza si las alarmas de peligro o salidas ocurren cuando el robot
    pierde la visión y el estimador commuta a otro estado (ej. Odometría).
    """
    print(f"\n--- DIAGNÓSTICO DEL ESTIMADOR DE POSICIÓN ---")
    
    if not registros:
        print("[!] No se encontraron líneas del estimador. Verifica el texto exacto del log.")
        return

    # Contar cuántas veces se usa cada estado del estimador en el log
    estados_conteo = {}
    cambios_de_estado = []
    
    estado_anterior = registros[0]['estado_estimador']
    estados_conteo[estado_anterior] = 1

    for i in range(1, len(registros)):
        est_actual = registros[i]['estado_estimador']
        estados_conteo[est_actual] = estados_conteo.get(est_actual, 0) + 1
        
        # Detectar conmutación (ej: de VISION a ODOMETRIA)
        if est_actual != estado_anterior:
            cambios_de_estado.append({
                'linea': registros[i]['linea'],
                'timestamp': registros[i]['timestamp'],
                'de': estado_anterior,
                'a': est_actual,
                'x': registros[i]['x'],
                'y': registros[i]['y']
            })
            estado_anterior = est_actual

    # Imprimir resumen de uso de los modos de estimación
    print(" Distribución de modos utilizados por el robot:")
    for modo, conteo in estados_conteo.items():
        porcentaje = (conteo / len(registros)) * 100
        print(f"  • Modulo [{modo}]: {conteo} ciclos ({porcentaje:.1f}%)")
    
    print(f"  • Total de conmutaciones/cambios de modo detectados: {len(cambios_de_estado)}")

    # Correlacionar alarmas críticas con el estado del estimador
    print(f"\n [?] Análisis de Alarmas vs Estado del Estimador:")
    
    for alarma in alarmas:
        # Encontrar la estimación de posición más cercana en el tiempo (justo antes o en el mismo segundo)
        est_cercanas = [r for r in registros if r['timestamp'] <= alarma['timestamp']]
        if est_cercanas:
            ultima_est = est_cercanas[-1]
            print(f"   • Peligro en Línea {alarma['linea']} [{alarma['timestamp']}]:")
            print(f"     El robot ejecutó la FSM usando el modo: **{ultima_est['estado_estimador']}**")
            print(f"     Coordenadas calculadas en ese instante: ({ultima_est['x']:.2f}, {ultima_est['y']:.2f})")
            
            # Si estaba en modo odometría/estimado, alertar sobre posible deriva del encoder
            if ultima_est['estado_estimador'].upper() != 'VISION':
                print(f"     [ALERTA]: El robot calculaba su posición a ciegas (sin ArUco). Probable desfase por deriva.")
            print("-" * 65)

    return cambios_de_estado


# ==========================================
# 3. VISUALIZACIÓN POR COLORES SEGÚN EL MODO
# ==========================================
def visualizar_modos_estimador(registros, cambios, alarmas):
    if not registros:
        return

    plt.figure(figsize=(12, 9))
    
    # Separar trayectorias por modos para pintarlas de diferentes colores
    # Así verás tramos azules para Visión, tramos naranjas para Odometría, etc.
    modos_disponibles = list(set([r['estado_estimador'] for r in registros]))
    colores_map = {'VISION': 'dodgerblue', 'ODOM': 'darkorange', 'ODOMETRIA': 'darkorange', 'ESTIMADO': 'magenta'}
    
    for modo in modos_disponibles:
        x_modo = [r['x'] for r in registros if r['estado_estimador'] == modo]
        y_modo = [r['y'] for r in registros if r['estado_estimador'] == modo]
        
        color = colores_map.get(modo.upper(), 'gray')
        plt.scatter(x_modo, y_modo, color=color, s=5, alpha=0.6, label=f'Modo: {modo}')

    # Marcar los puntos exactos de conmutación (donde se perdió o recuperó el ArUco)
    if cambios:
        cx = [c['x'] for c in cambios]
        cy = [c['y'] for c in cambios]
        plt.scatter(cx, cy, color='black', marker='o', s=40, zorder=5, label='Cambio de Modo (Conmutación)')

    # Marcar alertas críticas
    if alarmas:
        # Buscamos la última posición registrada para pintar la X
        ax = []
        ay = []
        for al in alarmas:
            cercanos = [r for r in registros if r['timestamp'] <= al['timestamp']]
            if cercanos:
                ax.append(cercanos[-1]['x'])
                ay.append(cercanos[-1]['y'])
        plt.scatter(ax, ay, color='red', marker='X', s=150, zorder=6, label='CRITICAL - Pared muy cercana')

    plt.title('Mapa Espacial de Decisiones del Estimador de Posición', fontsize=13, fontweight='bold')
    plt.xlabel('X (mm)')
    plt.ylabel('Y (mm)')
    plt.grid(True, linestyle=':', alpha=0.5)
    plt.legend(loc='upper right')
    plt.axis('equal')
    plt.show()


# ==========================================
# EJECUCIÓN DEL MÓDULO
# ==========================================
if __name__ == "__main__":
    LOG_FILE = '../Frodo/Robot_06_20250525.log'
    
    registros, alarmas = cargar_datos_log_estimador(LOG_FILE)
    cambios = analizar_comportamiento_estimador(registros, alarmas)
    visualizar_modos_estimador(registros, cambios, alarmas)