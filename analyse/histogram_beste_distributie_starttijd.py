import json
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import stats
from sklearn.mixture import GaussianMixture

# deze file plot de gmm op een histogrammen van starttijden, per locatie, per weekdag

with open('data/data_personenwagens.json', 'r', encoding='utf-8') as bestand:
    data = json.load(bestand)

rijen = []
for rit in data.get('reserveringen'):
    datum_tijd = pd.to_datetime(rit['startTijd'])
    start_minuten = datum_tijd.hour * 60 + datum_tijd.minute + datum_tijd.second / 60.0
    
    rijen.append({
        'locatie': rit['locatie'],
        'start_minuten': start_minuten,
        'weekdag_index': datum_tijd.weekday(),
        'weekdag_naam': datum_tijd.day_name()
    })
            
dataframe = pd.DataFrame(rijen)
dagen_namen = ['Maandag', 'Dinsdag', 'Woensdag', 'Donderdag', 'Vrijdag']
locaties = dataframe['locatie'].unique()

map_histogrammen = "histogrammen/beste_distributie/starttijden"
os.makedirs(map_histogrammen, exist_ok=True)

def pas_gmm_toe(data_reeks):
    if len(data_reeks) < 5: 
        return None

    data_2d = np.array(data_reeks).reshape(-1, 1)
    
    beste_aic = 10000000
    beste_gmm_model = None
    
    for aantal_componenten in range(2, 4):
        gmm = GaussianMixture(n_components=aantal_componenten, covariance_type='full', max_iter=1000, tol=1e-6, random_state=0)
        gmm.fit(data_2d)
        aic_score = gmm.aic(data_2d)
        
        if aic_score < beste_aic:
            beste_aic = aic_score
            beste_gmm_model = {
                'aantal_componenten': aantal_componenten,
                'gewichten': gmm.weights_.copy(),
                'gemiddeldes': gmm.means_.flatten().copy(),
                'varianties': gmm.covariances_.flatten().copy()
            }
    return beste_gmm_model

def maak_histogram_met_gmm(data_reeks, titel, bestandsnaam):
    if len(data_reeks) < 5: 
        return

    data_reeks = data_reeks / 60.0
    
    plt.figure(figsize=(10, 6))
    plt.hist(data_reeks, bins=50, density=True, edgecolor='black', alpha=0.6, color='steelblue')
    
    gmm_model = pas_gmm_toe(data_reeks)
    x_as = np.linspace(data_reeks.min(), data_reeks.max(), 1000)
    pdf_totaal = np.zeros_like(x_as)
    
    for component_index in range(gmm_model['aantal_componenten']):

        # per component de normaalverdeling plotten met juiste gewicht uit de GMM
        #pdf is probability density function, dit is de kans dat een waarde in een bepaald interval valt dus resultaat is een functie
        gewicht = gmm_model['gewichten'][component_index]
        gemiddelde = gmm_model['gemiddeldes'][component_index]
        standaardafwijking = np.sqrt(gmm_model['varianties'][component_index])
        
        pdf_component = gewicht * stats.norm.pdf(x_as, gemiddelde, standaardafwijking)
        pdf_totaal += pdf_component
        plt.plot(x_as, pdf_component)
        
    plt.plot(x_as, pdf_totaal)
    
    plt.title(f"Histogram met GMM: {titel}")
    plt.xlabel('Starttijd (uur)')
    plt.ylabel('Dichtheid')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(bestandsnaam)
    plt.close()

# Enkel 1 locatie, 1 weekdag apart
for locatie in locaties:
    for weekdag_index, dag_naam in enumerate(dagen_namen):
        locatie_klopt = dataframe['locatie'] == locatie
        weekdag_klopt = dataframe['weekdag_index'] == weekdag_index
                        
        subset = dataframe[locatie_klopt & weekdag_klopt]

        data_locatie_dag = subset['start_minuten'].values
        maak_histogram_met_gmm(data_locatie_dag, f"{locatie} - {dag_naam}", f"{map_histogrammen}/{locatie}_{dag_naam}.png")