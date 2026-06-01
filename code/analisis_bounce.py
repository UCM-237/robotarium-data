import re
import matplotlib.pyplot as plt
import numpy as np

from datetime import datetime

# --- CONFIGURACIÓN ---
LOG_FILE_PATH = "../Frodo/robot_6_log_20260601_125701.csv.log"  # Cambia por la ruta de tu archivo
TATAMI_WIDTH = 450.0
TATAMI_HEIGHT = 140.0

def analizar_log_completo(file_path):
    x_coords = []
    y_coords = []
    angles = []
    delays_ms = []
    tiempos_acumulados_seg = []
    # Expresiones regulares para capturar posición y la marca de tiempo completa
    time_regex = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})")
    
    # 2. Regex específica para tu JSON real de la línea: {"x": -6.72, "y": 100.55, "yaw": -1.629...
    # Captura los tres valores numéricos (incluyendo negativos y decimales)
    json_regex = re.compile(r'"x":\s*([-\d.]+),\s*"y":\s*([-\d.]+),\s*"yaw":\s*([-\d.]+)')

    ultimo_timestamp = None
    primer_timestamp = None
    lineas_con_posicion =0
    with open(file_path, 'r', encoding='utf-8') as file:
        for line in file:
            # Nos interesa analizar las líneas que registran los datos de posición de visión
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
    # Creamos una ventana con 2 gráficos: uno al lado del otro o arriba y abajo.
    fig, (ax1, ax2,ax3) = plt.subplots(3, 1, figsize=(12, 10))
    fig.suptitle(f"Análisis Global de Telemetría y Retardos - {file_path}", fontsize=14, fontweight='bold')

    # --- GRÁFICO 1: EL TATAMI Y LA TRAYECTORIA ---
    ax1.plot([0, TATAMI_WIDTH, TATAMI_WIDTH, 0, 0], 
             [0, 0, TATAMI_HEIGHT, TATAMI_HEIGHT, 0], 
             'r--', linewidth=2, label="Límites del Tatami")
    ax1.axhspan(0, TATAMI_HEIGHT, color='gray', alpha=0.1)
    ax1.plot(x_coords, y_coords, color='blue', linestyle='-', linewidth=1.5, label="Trayectoria")
    ax1.plot(x_coords, y_coords, 'o', color='blue', markersize=4, alpha=0.7)
    ax1.scatter(x_coords[0], y_coords[0], color='green', s=80, zorder=5, label="Inicio")
    ax1.scatter(x_coords[-1], y_coords[-1], color='red', s=80, zorder=5, label="Final")
    
    # Flechas de dirección
    paso = max(1, len(x_coords) // 20)
    for i in range(0, len(x_coords), paso):
        u = np.cos(angles[i]) * 15
        v = np.sin(angles[i]) * 15
        ax1.quiver(x_coords[i], y_coords[i], u, v, color='black', 
                   angles='xy', scale_units='xy', scale=1, width=0.003, alpha=0.5)
        
    ax1.set_title("Visualización del Robot en el Tatami")
    ax1.set_xlabel("Eje X")
    ax1.set_ylabel("Eje Y")
    ax1.set_xlim(-30, TATAMI_WIDTH + 30)
    ax1.set_ylim(-30, TATAMI_HEIGHT + 30)
    ax1.grid(True, linestyle=':', alpha=0.6)
    ax1.legend(loc='upper right')
    ax1.set_aspect('equal', adjustable='box')

    # --- GRÁFICO 2: ANÁLISIS DE DELAY (Milisegundos) ---
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