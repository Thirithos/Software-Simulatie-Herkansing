import json
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import stats

# deze file plot de poissonverdeling op een histogram van het aantal reserveringen per dag, per locatie, per weekdag

with open('data/data_personenwagens.json', 'r', encoding='utf-8') as bestand:
    data = json.load(bestand)

rijen = []
for reservering in data.get('reserveringen'):
    datum_tijd = pd.to_datetime(reservering['startTijd'])
    rijen.append({
        'locatie': reservering['locatie'],
        'datum': datum_tijd.date(),
        'weekdag_index': datum_tijd.weekday(),
        'weekdag_naam': datum_tijd.day_name()
    })
            
dataframe = pd.DataFrame(rijen)
dagen_namen = ['Maandag', 'Dinsdag', 'Woensdag', 'Donderdag', 'Vrijdag']
locaties = dataframe['locatie'].unique()

min_datum = dataframe['datum'].min()
max_datum = dataframe['datum'].max()
alle_kalenderdagen = pd.date_range(start=min_datum, end=max_datum).date

map_histogrammen = "histogrammen/beste_distributie/aantal_orders"
os.makedirs(map_histogrammen, exist_ok=True)

def maak_histogram_met_poisson(data_reeks, titel, bestandsnaam):
    if len(data_reeks) < 5: return
    
    data_reeks = data_reeks.astype(int)
    minimum_waarde = int(data_reeks.min())
    maximum_waarde = int(data_reeks.max())

    discrete_bins = np.arange(minimum_waarde - 0.5, maximum_waarde + 1.5, 1)

    lambda_waarde = np.mean(data_reeks)

    plt.figure(figsize=(8, 5))
    plt.hist(data_reeks, bins=discrete_bins, edgecolor='black', alpha=0.7, color='steelblue')
    # verdeling
    x_as = np.arange(0, maximum_waarde)
    # de poisson verdeling
    y_as = stats.poisson.pmf(x_as, lambda_waarde)
    plt.plot(x_as, y_as)
    
    plt.title(f"Histogram met Poisson: {titel}")
    plt.xlabel('Aantal reserveringen per dag')
    plt.ylabel('Dichtheid')

    plt.xlim(minimum_waarde - 1, maximum_waarde + 1)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(bestandsnaam)
    plt.close()

datums_per_weekdag = {}
for weekdag_index in range(len(dagen_namen)):
    datums_per_weekdag[weekdag_index] = []
    for datum in alle_kalenderdagen:
        if datum.weekday() == weekdag_index:
            datums_per_weekdag[weekdag_index].append(datum)

# per dag en per locatie
for locatie in locaties:
    for weekdag_index, dag_naam in enumerate(dagen_namen):
        datums_voor_deze_weekdag = datums_per_weekdag[weekdag_index]
        
        locatie_klopt = dataframe['locatie'] == locatie
        weekdag_klopt = dataframe['weekdag_index'] == weekdag_index
                
        subset = dataframe[locatie_klopt & weekdag_klopt]
        
        reserveringen_per_dag = subset.groupby('datum').size()
        volledige_reeks = reserveringen_per_dag.reindex(datums_voor_deze_weekdag, fill_value=0)
        data_locatie_dag = volledige_reeks.values
        
        maak_histogram_met_poisson(data_locatie_dag, f"{locatie} - {dag_naam}", f"{map_histogrammen}/{locatie}_{dag_naam}.png")