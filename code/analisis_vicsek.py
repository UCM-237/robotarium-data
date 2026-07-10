import re
import ast
import math
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# Ruta al archivo de log
log_file_path = "../vicsek_data/robot_6_log_20260709_155107.csv.log"

# Estructuras para almacenar datos extraídos
posiciones_propias = []
comandos_motores = []
estados_fsm = []
datos_orientacion = []

# Expresiones regulares
regex_pos_vision = re.compile(r"Posición actualizada por visión: x=([\d\.-]+), y=([\d\.-]+), θ=([\d\.-]+)")
regex_fsm = re.compile(r"Estado FSM: (\w+) \| Target Theta: ([\d\.-]+)° \| Theta Act: ([\d\.-]+)°")
regex_cmd = re.compile(r"v: ([\d\.-]+) \| w: ([\d\.-]+)")
regex_enjambre = re.compile(r"Enjambre (\{.*\})")
regex_vicsek = re.compile(r"Vicsek angle ([\d\.-]+)")

ultimo_enjambre = {}
ultima_posicion_propia = None

with open(log_file_path, 'r', encoding='utf-8') as file:
    for line in file:
        ts_match = re.search(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})", line)
        if not ts_match:
            continue
        ts = ts_match.group(1)

        # 1. Capturar posición y orientación propia del Robot 6
        pos_match = regex_pos_vision.search(line)
        if pos_match:
            ultima_posicion_propia = float(pos_match.group(3)) # Guardamos θ propio
            posiciones_propias.append({
                "timestamp": ts, "x": float(pos_match.group(1)), "y": float(pos_match.group(2)), "theta": ultima_posicion_propia
            })
            continue

        # 2. Capturar Máquina de Estados (FSM)
        fsm_match = regex_fsm.search(line)
        if fsm_match:
            estados_fsm.append({
                "timestamp": ts, "estado": fsm_match.group(1), "target_theta": float(fsm_match.group(2)), "theta_act": float(fsm_match.group(3))
            })
            continue

        # 3. Capturar comandos de velocidad
        cmd_match = regex_cmd.search(line)
        if cmd_match:
            comandos_motores.append({"timestamp": ts, "v": float(cmd_match.group(1)), "w": float(cmd_match.group(2))})
            continue

        # 4. Capturar estado del vecindario
        enjambre_match = regex_enjambre.search(line)
        if enjambre_match:
            try:
                ultimo_enjambre = ast.literal_eval(enjambre_match.group(1))
            except Exception:
                pass
            continue

        # 5. Capturar ángulo Vicsek registrado y calcular el teórico simultáneamente
        vicsek_match = regex_vicsek.search(line)
        if vicsek_match:
            angulo_log = float(vicsek_match.group(1))
            
            # --- CÁLCULO TEÓRICO DE LA MEDIA DE VICSEK ---
            if ultima_posicion_propia is not None:
                sin_sum = math.sin(ultima_posicion_propia)
                cos_sum = math.cos(ultima_posicion_propia)
                
                # Sumamos vectores de los vecinos que están en el enjambre
                for robot_id, data in ultimo_enjambre.items():
                    sin_sum += math.sin(data['theta'])
                    cos_sum += math.cos(data['theta'])
                
                vicsek_teorico = math.atan2(sin_sum, cos_sum)
            else:
                vicsek_teorico = np.nan

            registro_angulos = {
                "timestamp": ts,
                "Vicsek_Angle_Log": angulo_log,
                "Vicsek_Teorico": vicsek_teorico,
                "Robot_6_Propio": ultima_posicion_propia
            }
            
            for robot_id, data in ultimo_enjambre.items():
                registro_angulos[f"Robot_{robot_id}_Vecino"] = data.get("theta")
                
            datos_orientacion.append(registro_angulos)

# Convertir listas a DataFrames de Pandas
df_pos = pd.DataFrame(posiciones_propias)
df_angulos = pd.DataFrame(datos_orientacion)

if not df_angulos.empty:
    df_angulos.fillna(method='ffill', inplace=True)
    
    # --- CORRECCIÓN CRÍTICA: UNWRAP ANGULAR ---
    # np.unwrap corrige los saltos artificiales de 2*pi cuando el ángulo pasa de pi a -pi
    df_angulos['Vicsek_Angle_Log'] = np.unwrap(df_angulos['Vicsek_Angle_Log'])
    df_angulos['Vicsek_Teorico'] = np.unwrap(df_angulos['Vicsek_Teorico'])
    df_angulos['Robot_6_Propio'] = np.unwrap(df_angulos['Robot_6_Propio'])
    
    columnas_vecinos = [col for col in df_angulos.columns if col.endswith('_Vecino')]
    for col in columnas_vecinos:
        df_angulos[col] = np.unwrap(df_angulos[col])

# --- GRÁFICA 2: COMPARATIVA DE ORIENTACIONES CORREGIDA ---
if not df_angulos.empty:
    plt.figure(figsize=(12, 6))
    
    # Ángulo guardado en Log vs Ángulo recalculado teóricamente
    plt.plot(df_angulos['timestamp'], df_angulos['Vicsek_Angle_Log'], 
             label='Vicsek registrado en LOG', color='black', linewidth=3, linestyle='-')
    plt.plot(df_angulos['timestamp'], df_angulos['Vicsek_Teorico'], 
             label='Vicsek teórico (Cálculo Script)', color='red', linewidth=1.5, linestyle='--')
    
    # Orientaciones de origen sin cortes verticales artificiales
    plt.plot(df_angulos['timestamp'], df_angulos['Robot_6_Propio'], label='Robot 6 (Propio)', alpha=0.5, linestyle=':')
    for col in columnas_vecinos:
        plt.plot(df_angulos['timestamp'], df_angulos[col], label=f'{col.replace("_Vecino", "")}', alpha=0.6)
        
    plt.title('Validación de Modelo de Vicsek (Fase Desempaquetada sin Saltos de $2\pi$)')
    plt.xlabel('Tiempo')
    plt.ylabel('Ángulo Acumulado (Radianes)')
    plt.xticks(rotation=45)
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.legend(loc='upper left')
    plt.tight_layout()
    plt.show()