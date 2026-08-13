import json
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# puur deze file om te zien hoe lang de duur is van reserveringen die starten tussen 16:00 en 20:00, om te zien of er een verschil is met de rest van de dag want rond 17-18 u is er een piek in startende reserveringen (zijn het avondshifts of korte reserveringen), dus specifiek hoelang de reserveringen duren die starten tijdens de avondspits

with open('data/data_personenwagens.json', 'r', encoding='utf-8') as bestand:
    data = json.load(bestand)

rijen = []
for reservering in data.get('reserveringen', []):
    datum_tijd = pd.to_datetime(reservering['startTijd'])
    start_uur = datum_tijd.hour
    
    if 16 <= start_uur < 20:
        rijen.append({
            'duur_minuten': reservering['duur'],
            'start_uur': start_uur
        })

dataframe = pd.DataFrame(rijen)

duur_data = dataframe['duur_minuten'].values
    
os.makedirs('histogrammen/specifiek_avond', exist_ok=True)
    
plt.figure(figsize=(10, 6))

aantal_bins = max(10, int(np.sqrt(len(duur_data))))
plt.hist(duur_data, bins=aantal_bins, edgecolor='black', alpha=0.7, color='darkorange')
    
plt.title(f"Histogram van Duur (Starttijd 16:00 - 20:00)")
plt.xlabel('Duur (minuten)')
plt.ylabel('Frequentie')
plt.grid(True, alpha=0.3)
plt.tight_layout()
    
bestandsnaam = 'histogrammen/specifiek_avond/duur_16u_tot_20u.png'
plt.savefig(bestandsnaam)
plt.close()