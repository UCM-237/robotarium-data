import re
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import LineCollection
from datetime import datetime

# --- CONFIGURACIÓN ---
LOG_FILE_PATH = "../Frodo/robot_6_log_20260602_144924.csv.log"  # Cambia por la ruta de tu archivo
TATAMI_WIDTH = 450.0
TATAMI_HEIGHT = 140.0
# --- CONFIGURACIÓN DE ORIENTACIÓN REAL ---
INVERTIR_EJE_X = True   # <--- CAMBIA A True O False PARA ALINEARLO CON TU TATAMI REAL
INVERTIR_EJE_Y = False  # <--- Por si el eje vertical también estuviera invertido
ANGULO_CORRECCION_VISUAL = 0.0  # Por si quieres rotar todas las flechas (ej: 180 o 90)
# Definición de colores para cada estado de la FSM (puedes añadir los que use tu algoritmo)
COLORES_ESTADO = {
    'AVANZA': '#1f77b4',                   # Azul - Marcha normal
    'PARANDO_PARA_RETROCEDER': '#d62728',  # Rojo - Frenada de emergencia al ver pared
    'RETROCEDIENDO': '#ff7f0e',            # Naranja - Marcha atrás
    'GIRANDO': '#2ca02c',                  # Verde - Rotación para cambiar rumbo
    'STOP': '#7f7f7f',                     # Gris
    'DESCONOCIDO': '#bcbd22'               # Amarillo/Oliva por si sale otro
}

def analizar_log_completo(file_path):
    x_coords = []
    y_coords = []
    angles = []
    delays_ms = []
    tiempos_acumulados_seg = []
    estados_por_muestra = []  # <--- NUEVA LISTA para registrar el estado de la FSM en cada posición
    distancias_minimas = []
    # Expresiones regulares para capturar posición y la marca de tiempo completa
    time_regex = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})")
    
    # 2. Regex específica para tu JSON real de la línea: {"x": -6.72, "y": 100.55, "yaw": -1.629...
    # Captura los tres valores numéricos (incluyendo negativos y decimales)
    json_regex = re.compile(r'"x":\s*([-\d.]+),\s*"y":\s*([-\d.]+),\s*"yaw":\s*([-\d.]+)')
    fsm_regex = re.compile(r"Estado FSM:\s*([A-Za-zA-Z0-9_]+)") # Captura la palabra del estado
    walls_regex = re.compile(r"Distancias a paredes:\s*Left:\s*([-\d.]+),\s*Right:\s*([-\d.]+),\s*Top:\s*([-\d.]+),\s*Bottom:\s*([-\d.]+)")

    ultimo_timestamp = None
    primer_timestamp = None
    lineas_con_posicion =0
    estado_actual = 'DESCONOCIDO'
    # Variables temporales para arrastrar los últimos valores de distancias leídos
    last_min_dist = 0.0

    with open(file_path, 'r', encoding='utf-8') as file:
        for line in file:
            # 1. Capturar distancias a las paredes
            if "Distancias a paredes:" in line:
                match_walls = walls_regex.search(line)
                if match_walls:
                    l = float(match_walls.group(1))
                    r = float(match_walls.group(2))
                    t = float(match_walls.group(3))
                    b = float(match_walls.group(4))
                    # Obtenemos la distancia real a la pared más cercana en este instante
                    last_min_dist = min(l, r, t, b)
            # 1. SI LA LÍNEA ES DE CAMBIO DE ESTADO, ACTUALIZAMOS LA VARIABLE
            if "Estado FSM:" in line:
                match_fsm = fsm_regex.search(line)
                if match_fsm:
                    estado_actual = match_fsm.group(1).strip()# Nos interesa analizar las líneas que registran los datos de posición de visión
            if "Topic 6/pos" in line:
              match_time = time_regex.search(line)
              match_json = json_regex.search(line)
              
              if match_time and match_json:
                    try:
                        # Extraer coordenadas reales del JSON
                        x = float(match_json.group(1))
                        y = float(match_json.group(2))
                        theta = float(match_json.group(3)) # El "yaw" o ángulo
                        
                        str_time = match_time.group(1)
                        current_timestamp = datetime.strptime(str_time, "%Y-%m-%d %H:%M:%S.%f")
                        
                        # Guardar en las listas globales
                        x_coords.append(x)
                        y_coords.append(y)
                        angles.append(theta)
                        estados_por_muestra.append(estado_actual) # <--- Vinculamos posición -> estado
                        distancias_minimas.append(last_min_dist) # Guardar la distancia asociada
                        # Guardar tiempo transcurrido (Reloj del experimento)
                        if primer_timestamp is None:
                            primer_timestamp = current_timestamp
                        
                        tiempo_desde_inicio = (current_timestamp - primer_timestamp).total_seconds()
                        tiempos_acumulados_seg.append(tiempo_desde_inicio)
                        
                        # Guardar delay relativo entre mensajes consecuivos
                        if ultimo_timestamp is not None:
                            delta = current_timestamp - ultimo_timestamp
                            delta_ms = delta.total_seconds() * 1000.0
                            delays_ms.append(delta_ms)
                        else:
                            delays_ms.append(0.0)
                            
                        ultimo_timestamp = current_timestamp
                    except ValueError:
                        continue

    print(f"Total de líneas analizadas con '6/pos': {lineas_con_posicion}")
    print(f"DEBUG: Primeros 5 tiempos calculados (seg): {tiempos_acumulados_seg[:5]}")
    print(f"DEBUG: Últimos 5 tiempos calculados (seg): {tiempos_acumulados_seg[-5:]}")
    print(f"DEBUG: Total elementos de tiempo: {len(tiempos_acumulados_seg)}")
    if not x_coords:
        print("No se encontraron datos de 'Posicion:' en el log.")
        return

    # --- DIBUJAR LOS GRÁFICOS (Subplots) ---
    fig, (ax1) = plt.subplots(1, 1, figsize=(12, 10))
    fig.suptitle(f"Análisis Global de Telemetría y Retardos - {file_path}", fontsize=14, fontweight='bold')

    # --- GRÁFICO 1: TRAYECTORIA MULTICOLOR SEGÚN FSM ---
    ax1.plot([0, TATAMI_WIDTH, TATAMI_WIDTH, 0, 0], [0, 0, TATAMI_HEIGHT, TATAMI_HEIGHT, 0], 
             'r--', linewidth=2, label="Límites del Tatami")
    ax1.axhspan(0, TATAMI_HEIGHT, color='gray', alpha=0.05)
    
    # TRUCO MÁGICO: Convertir puntos en segmentos individuales con colores específicos
    puntos = np.array([x_coords, y_coords]).T.reshape(-1, 1, 2)
    segmentos = np.concatenate([puntos[:-1], puntos[1:]], axis=1)
    
    # Asignar a cada segmento el color correspondiente al estado de la muestra
    colores_segmentos = [COLORES_ESTADO.get(est, COLORES_ESTADO['DESCONOCIDO']) for est in estados_por_muestra[:-1]]
    
    # Crear la colección de líneas y añadirla al tatami
    lc = LineCollection(segmentos, colors=colores_segmentos, linewidths=2.0)
    ax1.add_collection(lc)
    
    # Marcadores globales
    ax1.scatter(x_coords[0], y_coords[0], color='green', s=100, zorder=5, label="Inicio")
    ax1.scatter(x_coords[-1], y_coords[-1], color='black', s=100, zorder=5, label="Fin")
    
    # LÓGICA DE DETECCIÓN DE CAMBIOS DE ESTADO PARA ANOTACIONES
    for i in range(1, len(estados_por_muestra)):
        estado_previo = estados_por_muestra[i-1]
        estado_nuevo = estados_por_muestra[i]
        
        # Si el estado cambió en esta muestra, pintamos un marcador y su distancia
        if estado_previo != estado_nuevo:
            # Dibujar un punto negro sutil donde ocurre la conmutación
            ax1.scatter(x_coords[i], y_coords[i], color='black', s=30, zorder=4)
            
            # Texto con el valor de la distancia mínima a la pared más cercana
            texto_dist = f"{distancias_minimas[i]:.1f}"
            
            # Colocar la etiqueta flotante de forma limpia con una flecha apuntando al punto
            ax1.annotate(
                texto_dist, 
                xy=(x_coords[i], y_coords[i]), 
                xytext=(10, 10), 
                textcoords='offset points',
                fontsize=9, 
                fontweight='bold',
                color='darkred',
                bbox=dict(boxstyle='round,pad=0.2', fc='yellow', alpha=0.7),
                arrowprops=dict(arrowstyle='->', color='black', lw=0.8, alpha=0.5)
            ) 
    # Flechas de dirección (quiver)
    paso = max(1, len(x_coords) // 25)
    for i in range(0, len(x_coords), paso):
        ang_rad = np.radians(angles[i])
        
        # Aplicamos corrección manual por software si se define arriba
        if ANGULO_CORRECCION_VISUAL != 0:
            ang_rad += np.radians(ANGULO_CORRECCION_VISUAL)

        u = np.cos(ang_rad) * 15
        v = np.sin(ang_rad) * 15
        
        # SI REVERTIDMOS EL EJE HORIZONTAL, LA COMPONENTE X DE LA FLECHA CAMBIA DE SIGNO
        if INVERTIR_EJE_X:
            u = -u
        if INVERTIR_EJE_Y:
            v = -v
            
        ax1.quiver(x_coords[i], y_coords[i], u, v, color='black', 
                  angles='xy', scale_units='xy', scale=1, width=0.003, alpha=0.6)
    
    ax1.set_title("Trayectoria del Robot coloreada por Estado de la FSM")
    ax1.set_xlabel("Eje X")
    ax1.set_ylabel("Eje Y")
    ax1.set_xlim(min(min(x_coords),0) - 30, max(max(x_coords),TATAMI_WIDTH )+ 30)
    ax1.set_ylim(min(min(y_coords),0) - 30, max(max(y_coords),TATAMI_HEIGHT) + 30)
    # --- APLICACIÓN DE LA INVERSIÓN DE EJES ---
    if INVERTIR_EJE_X:
        ax1.invert_xaxis()  # <--- Voltea horizontalmente el gráfico de Matplotlib
    if INVERTIR_EJE_Y:
        ax1.invert_yaxis()  # <--- Voltea verticalmente el gráfico de Matplotlib
    ax1.grid(True, linestyle=':', alpha=0.6)
    ax1.set_aspect('equal', adjustable='box')
    
    # LEYENDA PERSONALIZADA PARA LOS ESTADOS
    from matplotlib.lines import Line2D
    elementos_leyenda = [Line2D([0], [0], color='r', linestyle='--', linewidth=2, label="Límites Tatami")]
    # Añadimos dinámicamente solo los estados que realmente aparecieron en el log
    estados_unicos_detectados = set(estados_por_muestra)
    for est in estados_unicos_detectados:
        color_est = COLORES_ESTADO.get(est, COLORES_ESTADO['DESCONOCIDO'])
        elementos_leyenda.append(Line2D([0], [0], color=color_est, lw=3, label=f"FSM: {est}"))
    ax1.legend(handles=elementos_leyenda, loc='upper right')
    plt.tight_layout()
    plt.show()
    
    # --- GRÁFICO 2: ANÁLISIS DE DELAY (Milisegundos) ---
        # Creamos una ventana con 2 gráficos: uno al lado del otro o arriba y abajo.
    fig, (ax2,ax3) = plt.subplots(2, 1, figsize=(12, 10))
    fig.suptitle(f"Análisis Global de Telemetría y Retardos - {file_path}", fontsize=14, fontweight='bold')

    mensajes_eje = np.arange(len(delays_ms))
    
    # Dibujar la línea de evolución del delay
    ax2.plot(mensajes_eje, delays_ms, color='purple', linewidth=1.2, label="Delay medido (ms)")
    
    # Calcular y dibujar la media del delay para tener una referencia clara
    delay_medio = np.mean(delays_ms[1:]) if len(delays_ms) > 1 else 0
    max_delay = np.max(delays_ms) if delays_ms else 0
    ax2.axhline(delay_medio, color='orange', linestyle='--', linewidth=1.5, 
                label=f"Delay Promedio: {delay_medio:.2f} ms")
    
    ax2.set_title("Evolución del Retardo (Delay) entre Mensajes de Visión (6/pos)")
    ax2.set_xlabel("Número de mensaje de posición recibido")
    ax2.set_ylabel("Tiempo transcurrido (ms)")
    ax2.grid(True, linestyle=':', alpha=0.6)
    ax2.legend(loc='upper right')

      # --- GRÁFICO 3: MENSAJES DE POSICION ---
    # Pintamos una línea vertical (vlines) para cada momento en el que llegó un mensaje
    ax3.vlines(tiempos_acumulados_seg, ymin=0, ymax=1, colors='g', alpha=0.6, linewidth=1.2, label="Mensaje '6/pos' recibido")
    # También añadimos una línea continua que acumula los mensajes para ver si la pendiente es constante
    ax3_twin = ax3.twinx()
    mensajes_acumulados_eje = np.arange(1, len(tiempos_acumulados_seg) + 1)
    print(mensajes_acumulados_eje)
    
    # Ahora ambos tienen exactamente la misma dimensión (por ejemplo, 550 y 550)
    ax3_twin.plot(tiempos_acumulados_seg, mensajes_acumulados_eje, color='darkblue', linestyle='--', alpha=0.7, label="Total acumulado")
    
    ax3.set_title("Línea Temporal de Recepción de Mensajes de Posición")
    ax3.set_xlabel("Tiempo transcurrido desde el inicio del log (segundos)")
    ax3.get_yaxis().set_visible(False) # Ocultamos el eje Y del vlines ya que solo es un indicador visual
    ax3_twin.set_ylabel("Cantidad de mensajes")
    ax3.grid(True, linestyle=':', alpha=0.6)
    
    # Juntar leyendas de los dos ejes en el gráfico 3
    lines, labels = ax3.get_legend_handles_labels()
    lines2, labels2 = ax3_twin.get_legend_handles_labels()
    ax3.legend(lines + lines2, labels + labels2, loc='upper left')
    
    # Si hay picos que superen por mucho la media, advertirlo
    if max_delay > 500:
        print(f"⚠️ Alerta: El sistema experimentó pérdidas de visión críticas de más de 0.5 segundos.")

    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    analizar_log_completo(LOG_FILE_PATH)