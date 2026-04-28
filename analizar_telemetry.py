import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import numpy as np

# 1. Cargar y limpiar datos
df = pd.read_csv('Arwen/telemetry_data_Arwen.csv')

# Opcional: Eliminar filas duplicadas si el robot estuvo quieto mucho tiempo
df = df.loc[(df[['x', 'y', 'yaw']].shift() != df[['x', 'y', 'yaw']]).any(axis=1)]

fig, ax = plt.subplots(figsize=(8, 8))
ax.set_aspect('equal')
ax.grid(True, linestyle='--', alpha=0.6)

# Configuración de límites (con un pequeño margen)
ax.set_xlim(df['x'].min() - 0.2, df['x'].max() + 0.2)
ax.set_ylim(df['y'].min() - 0.2, df['y'].max() + 0.2)
ax.set_title("Animación de Trayectoria: Arwen")

# Elementos de la animación
line, = ax.plot([], [], 'b-', alpha=0.4, label='Rastro') # La línea del camino
robot_dot, = ax.plot([], [], 'ro', markersize=8, label='Robot') # El robot actual
direction_arrow = ax.quiver(0, 0, 0, 0, color='red', scale=20) # Flecha de orientación

def init():
    line.set_data([], [])
    robot_dot.set_data([], [])
    return line, robot_dot

def update(frame):
    # Obtener datos hasta el frame actual
    x_data = df['x'].iloc[:frame]
    y_data = df['y'].iloc[:frame]
    
    # Actualizar rastro
    line.set_data(x_data, y_data)
    
    # Actualizar posición actual del robot
    curr_x = df['x'].iloc[frame]
    curr_y = df['y'].iloc[frame]
    curr_yaw = df['yaw'].iloc[frame]
    robot_dot.set_data([curr_x], [curr_y])
    
    # Actualizar flecha de dirección
    direction_arrow.set_offsets([curr_x, curr_y])
    direction_arrow.set_UVC(np.cos(curr_yaw), np.sin(curr_yaw))
    
    return line, robot_dot, direction_arrow

# Crear la animación
# interval es el tiempo entre frames en ms. Redúcelo para ir más rápido.
ani = FuncAnimation(fig, update, frames=len(df), init_func=init, 
                    blit=True, interval=50, repeat=False)

plt.legend()
plt.show()