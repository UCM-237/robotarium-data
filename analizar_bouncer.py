import json
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime

class BouncerAnalyzer:
    def __init__(self, log_file):
        self.log_file = log_file
        self.positions = []
        self.boundaries = None
        self.bounces = []

    def load_data(self):
        """Procesa el log buscando posiciones y límites de la arena."""
        with open(self.log_file, 'r') as f:
            for line in f:
                try:
                    # Ajusta esto según el formato de tu logger (JSON o texto plano)
                    data = json.loads(line)
                    
                    if "arena/boundaries" in data['topic']:
                        self.boundaries = data['message']['points']
                    
                    if "robot/position" in data['topic']:
                        pos = data['message']
                        self.positions.append((pos['x'], pos['y'], data['timestamp']))
                except:
                    continue

    def detect_bounces(self, threshold=5.0):
        """Detecta cambios bruscos de dirección cerca de los límites."""
        if len(self.positions) < 3: return
        
        for i in range(1, len(self.positions) - 1):
            # Calcular vectores de movimiento
            v1 = np.array([self.positions[i][0] - self.positions[i-1][0], 
                          self.positions[i][1] - self.positions[i-1][1]])
            v2 = np.array([self.positions[i+1][0] - self.positions[i][0], 
                          self.positions[i+1][1] - self.positions[i][1]])
            
            # Si el ángulo entre vectores cambia drásticamente (> 90 grados)
            dot_product = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-6)
            if dot_product < 0:  # Cambio de sentido
                self.bounces.append(self.positions[i])

    def plot_arena(self):
        """Genera un mapa visual del recorrido y los rebotes."""
        plt.figure(figsize=(10, 6))
        
        # Dibujar límites de la arena
        if self.boundaries:
            bx = [p['x'] for p in self.boundaries] + [self.boundaries[0]['x']]
            by = [p['y'] for p in self.boundaries] + [self.boundaries[0]['y']]
            plt.plot(bx, by, 'r--', label='Límites Arena')

        # Dibujar trayectoria
        px, py, _ = zip(*self.positions)
        plt.plot(px, py, 'b-', alpha=0.5, label='Trayectoria Robot')
        
        # Dibujar puntos de rebote
        if self.bounces:
            bx, by, _ = zip(*self.bounces)
            plt.scatter(bx, by, color='orange', s=100, label='Eventos de Rebote')

        plt.title("Análisis de Comportamiento Bouncer - Robotarium")
        plt.xlabel("X (cm)")
        plt.ylabel("Y (cm)")
        plt.legend()
        plt.grid(True)
        plt.show()

    def print_stats(self):
        total_dist = 0
        for i in range(1, len(self.positions)):
            total_dist += np.sqrt((self.positions[i][0]-self.positions[i-1][0])**2 + 
                                  (self.positions[i][1]-self.positions[i-1][1])**2)
        
        print(f"--- RESUMEN DEL BOUNCER ---")
        print(f"Puntos analizados: {len(self.positions)}")
        print(f"Distancia total recorrida: {total_dist:.2f} cm")
        print(f"Número de rebotes detectados: {len(self.bounces)}")

if __name__ == "__main__":
    analyzer = BouncerAnalyzer("bouncer_log.json")
    analyzer.load_data()
    analyzer.detect_bounces()
    analyzer.print_stats()
    analyzer.plot_arena()