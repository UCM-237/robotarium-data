import re
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import LineCollection
from datetime import datetime
from matplotlib.animation import FuncAnimation

# --- CONFIGURACIÓN ---
LOG_FILE_PATH = "../Frodo/robot_6_log_20260604_162118.csv.log"  # Cambia por la ruta de tu archivo
# --- CONFIGURACIÓN DE LOS LÍMITES REALES DE TU ARENA ---
X_MIN, X_MAX = -102.0, 298.0
Y_MIN, Y_MAX = 16.0, 160.0
# --- CONFIGURACIÓN DE ORIENTACIÓN REAL ---
INVERTIR_EJE_X = True   # <--- CAMBIA A True O False PARA ALINEARLO CON TU TATAMI REAL
INVERTIR_EJE_Y = False  # <--- Por si el eje vertical también estuviera invertido
ANGULO_CORRECCION_VISUAL = 0.0  # Por si quieres rotar todas las flechas (ej: 180 o 90)
# Dimensiones físicas extraídas de tu robot.h (en cm)
ROBOT_RADIUS = 14.5 / 2.0  # 7.25 cm de radio real

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

    # --- CONFIGURACIÓN DE LA FIGURA ---
    fig, ax1 = plt.subplots(1, 1, figsize=(12, 18))
    fig.suptitle(f"Simulación Animada FSM - Robot 6", fontsize=14, fontweight='bold')
    
    # Dibujar límites del Tatami estáticos
    ax1.plot([X_MIN, X_MAX, X_MAX, X_MIN, X_MIN], [Y_MIN, Y_MIN, Y_MAX, Y_MAX, Y_MIN], 'r--', linewidth=2, label="Límites Reales")
    ax1.axhspan(Y_MIN, Y_MAX, color='gray', alpha=0.05)
    
    # Añadir margen dinámico a los ejes para ver bien los rebotes exteriores
    ax1.set_xlim(X_MIN - 20, X_MAX + 20)
    ax1.set_ylim(Y_MIN - 20, Y_MAX + 20)
    if INVERTIR_EJE_X: ax1.invert_xaxis()
    if INVERTIR_EJE_Y: ax1.invert_yaxis()
    ax1.set_aspect('equal', adjustable='box')
    ax1.grid(True, linestyle=':', alpha=0.6)

    # Elementos de la animación que se actualizarán cuadro por cuadro
    lc = LineCollection([], linewidths=2.5)
    ax1.add_collection(lc)
    
    # --- NUEVOS ELEMENTOS GEOMÉTRICOS DEL ROBOT ---
    # 1. Cuerpo del robot: Un círculo con radio real (7.25 cm), fondo semi-transparente azul claro
    robot_body = plt.Circle((x_coords[0], y_coords[0]), ROBOT_RADIUS, 
                            facecolor='#a1c4fd', edgecolor='black', linewidth=1.5, zorder=6, alpha=0.8)
    ax1.add_patch(robot_body)
    
    # 2. Radio orientador: Una línea negra sólida que apunta hacia el frente del robot
    robot_radius_line, = ax1.plot([], [], color='black', linewidth=2.5, zorder=7)
    
    # Texto dinámico con el estado de la FSM superior izquierdo
    fsm_text = ax1.text(0.02, 0.95, '', transform=ax1.transAxes, fontsize=12, fontweight='bold',
                        bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

    # Guardar los puntos donde ya ha ocurrido un cambio de estado para pintarlos fijos
    puntos_cambio_x = []
    puntos_cambio_y = []
    puntos_cambio_scat = ax1.scatter([], [], color='black', s=30, zorder=4)

    # --- ELEMENTOS AUXILIARES ESTÁTICOS (Gráficas 2 y 3) ---
    fig2, (ax2, ax3) = plt.subplots(2, 1, figsize=(12, 8))  
    ax2.plot(delays_ms, color='purple', alpha=0.7)
    ax2.set_title("Retardo entre mensajes de visión (ms)")
    ax2.grid(True, linestyle=':')
    
    ax3.plot(tiempos_acumulados_seg, np.arange(len(tiempos_acumulados_seg)), color='green', alpha=0.7)
    ax3.set_title("Flujo Temporal Acumulado")
    ax3.grid(True, linestyle=':')

    # Leyenda estática para identificar los estados
    from matplotlib.lines import Line2D
    elementos_leyenda = [Line2D([0], [0], color='r', linestyle='--', linewidth=2, label="Límites Tatami")]
    for est in set(estados_por_muestra):
        elementos_leyenda.append(Line2D([0], [0], color=COLORES_ESTADO.get(est, '#7f7f7f'), lw=3, label=f"FSM: {est}"))
    ax1.legend(handles=elementos_leyenda, loc='upper right')

    # --- FUNCIONES DE LA ANIMACIÓN ---
    def init():
        """Inicializa los elementos limpios al comienzo de la animación"""
        lc.set_segments([])
        robot_radius_line.set_data([], [])
        fsm_text.set_text('')
        return lc, robot_body, robot_radius_line, fsm_text, puntos_cambio_scat

    def update(frame):
        """Se ejecuta secuencialmente en cada iteración/fotograma (frame)"""
        if frame == 0:
            puntos_cambio_x.clear()
            puntos_cambio_y.clear()
            puntos_cambio_scat.set_offsets(np.empty((0, 2)))

        # 1. Reconstruir la trayectoria histórica hasta el fotograma actual
        if frame > 0:
            x_hist = x_coords[:frame+1]
            y_hist = y_coords[:frame+1]
            puntos = np.array([x_hist, y_hist]).T.reshape(-1, 1, 2)
            segmentos = np.concatenate([puntos[:-1], puntos[1:]], axis=1)
            colores_segmentos = [COLORES_ESTADO.get(est, '#7f7f7f') for est in estados_por_muestra[:frame]]
            
            lc.set_segments(segmentos)
            lc.set_colors(colores_segmentos)

        # 2. Detectar si en este fotograma ocurrió un cambio de estado
        if frame > 0 and estados_por_muestra[frame-1] != estados_por_muestra[frame]:
            puntos_cambio_x.append(x_coords[frame])
            puntos_cambio_y.append(y_coords[frame])
            puntos_cambio_scat.set_offsets(np.c_[puntos_cambio_x, puntos_cambio_y])
            
            # Dibujar una anotación permanente de la distancia en el tatami
            ax1.annotate(f"{distancias_minimas[frame]:.1f}", 
                         xy=(x_coords[frame], y_coords[frame]), 
                         xytext=(10, 10), textcoords='offset points', fontsize=8, fontweight='bold',
                         color='darkred', bbox=dict(boxstyle='round,pad=0.1', fc='yellow', alpha=0.6))

       # 3. Mover el centro del círculo (Cuerpo del Robot)
        cx, cy = x_coords[frame], y_coords[frame]
        robot_body.set_center((cx, cy))

        # 4. Calcular el extremo del radio basándonos en la orientación (theta)
        ang_rad = angles[frame] + np.radians(ANGULO_CORRECCION_VISUAL)
        # Componentes de dirección del radio considerando inversiones de laboratorio
        dx = ROBOT_RADIUS * np.cos(ang_rad)
        dy = ROBOT_RADIUS * np.sin(ang_rad)
        if INVERTIR_EJE_X: dx = -dx
        if INVERTIR_EJE_Y: dy = -dy

        # La línea del radio se dibuja desde el centro (cx, cy) hasta la superficie (cx + dx, cy + dy)
        robot_radius_line.set_data([cx, cx + dx], [cy, cy + dy])

        # 5. Cambiar el color del círculo del robot para que refleje visualmente su estado
        estado_act = estados_por_muestra[frame]
        robot_body.set_facecolor(COLORES_ESTADO.get(estado_act, '#a1c4fd'))

        # 5. Actualizar cuadro de texto informativo
        estado_act = estados_por_muestra[frame]
        fsm_text.set_text(f"Estado FSM: {estado_act}\nDist. Mínima: {distancias_minimas[frame]:.1f} cm\nTiempo: {tiempos_acumulados_seg[frame]:.2f}s")
        fsm_text.set_color(COLORES_ESTADO.get(estado_act, 'black'))

        return lc, robot_body, robot_radius_line, fsm_text, puntos_cambio_scat

    # Calcular intervalo de reproducción basado en el retardo real medio (aprox 30-50ms)
    delay_medio = np.mean(delays_ms[1:]) if len(delays_ms) > 1 else 40
    
    # Crear animación
    ani = FuncAnimation(fig, update, frames=len(x_coords), init_func=init,
                        interval=int(delay_medio), blit=False, repeat=True)

    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    analizar_log_completo(LOG_FILE_PATH)