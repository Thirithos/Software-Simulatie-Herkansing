import json
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import stats
from sklearn.mixture import GaussianMixture

# om endtime te simuleren gebruik ik de duur, dit wordt vanaf de start geteld.
# deze file dient om: te zien welke data geschikt is, (er zijn evenveel datapunten als in starttijd)
# zoals de andere wordt er gecheckt of er verlies van info door samen te nemen
# en welke verdelingen geschikt zijn. de duur lijkt discreet
# maar de data is continue, er zijn kommagetallen, logisch want een endtime kan uren,minuten,seconden verwijderd zijn 

with open('data/data_personenwagens.json', 'r', encoding='utf-8') as bestand:
    data = json.load(bestand)

rijen = []
for reservering in data.get('reserveringen'):
    duur_minuten = reservering['duur']
    datum_tijd = pd.to_datetime(reservering['startTijd'])
    start_uur = datum_tijd.hour
    
    # dit zijn de delen voor opsplitsing om te zien of er verschil is tussen per uur of per dagdeel
    if 6 <= start_uur < 12:
        dagdeel = 'Ochtend'
    elif 12 <= start_uur < 18:
        dagdeel = 'Middag'
    else:
        dagdeel = 'Avond'

    # deze code gaat de buckets maken per 3 uur als fijnere opsplitsing dan dagdeel
    bucket_start = (start_uur // 3) * 3
    bucket_eind = (bucket_start + 3) % 24
    drie_uur_bucket = f"{bucket_start:02d}-{bucket_eind:02d}"

    rijen.append({
        'locatie': reservering['locatie'],
        'duur_minuten': duur_minuten,
        'weekdag_index': datum_tijd.weekday(),
        'weekdag_naam': datum_tijd.day_name(),
        'start_uur': start_uur,
        'dagdeel': dagdeel,
        'drie_uur_bucket': drie_uur_bucket
    })


            
dataframe = pd.DataFrame(rijen)
dagen_namen = ['Maandag', 'Dinsdag', 'Woensdag', 'Donderdag', 'Vrijdag']
locaties = dataframe['locatie'].unique()

print("3-uur buckets:")
for bucket in dataframe['drie_uur_bucket'].unique():
    print(f"  {bucket}")

map_historisch = "qq_plots/duur_historisch"
map_modellen = "qq_plots/duur_modellen"
map_histogrammen = "histogrammen/duur"
map_uren = "qq_plots/duur_uren_historisch"         

os.makedirs(map_historisch, exist_ok=True)
os.makedirs(map_modellen, exist_ok=True)
os.makedirs(map_histogrammen, exist_ok=True)
os.makedirs(map_uren, exist_ok=True)

def maak_histogram_continu(data_reeks, titel, bestandsnaam):
    if len(data_reeks) < 5: 
        return
    aantal_bins = int(np.sqrt(len(data_reeks)))
    plt.figure(figsize=(8, 5))
    plt.hist(data_reeks, bins=aantal_bins, edgecolor='black', alpha=0.7, color='steelblue')
    plt.title(f"Histogram: {titel}")
    plt.xlabel('Duur (minuten)')
    plt.ylabel('Frequentie')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(bestandsnaam)
    plt.close()

def maak_qq_historisch(data_reeks_1, data_reeks_2, titel, bestandsnaam, xlabel, ylabel):
    # als er te weinig data is, is het niet zinvol om data op te splitsen
    if len(data_reeks_1) < 5 or len(data_reeks_2) < 5: 
        return

    # lijstje van kwantiel niveaus 100 kwanitelen over het interval van 0.01 tot 0.99
    kwantiel_niveaus = np.linspace(0.01, 0.99, 100)
    # de kwantielen worden gekoppeld aan de data reeksen om dan te kunnen plotten met een scatter
    kwantielen_1 = np.quantile(data_reeks_1, kwantiel_niveaus)
    kwantielen_2 = np.quantile(data_reeks_2, kwantiel_niveaus)
    
    plt.figure(figsize=(8, 8))
    plt.scatter(kwantielen_1, kwantielen_2, color='green', marker='o', alpha=0.6)

    # de reden van de -1 en +1 is om de lijn wat beter zichtbaar te maken
    minimum_waarde = min(kwantielen_1.min(), kwantielen_2.min()) - 1
    maximum_waarde = max(kwantielen_1.max(), kwantielen_2.max()) + 1
    plt.plot([minimum_waarde, maximum_waarde], [minimum_waarde, maximum_waarde])
    
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.title(f"Vergelijking: {titel}")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(bestandsnaam)
    plt.close()

def pas_gmm_toe(data_reeks):
    # Ik gebruik GMM omdat ik merk dat er uitschieters zijn en ik probeer deze erin te vatten.
    # dit is puur als test, om te zien of het werkt
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

def sample_uit_gmm(gmm_model, aantal_samples=10000):
    samples = []
    for _ in range(aantal_samples):
        component_index = np.random.choice(gmm_model['aantal_componenten'], p=gmm_model['gewichten'])

        gemiddelde = gmm_model['gemiddeldes'][component_index]
        standaardafwijking = np.sqrt(gmm_model['varianties'][component_index])

        getrokken_waarde = np.random.normal(gemiddelde, standaardafwijking)
        
        samples.append(getrokken_waarde)
    return np.array(samples)

def maak_qq_plot_continu(data_reeks, titel, bestandsnaam, xlabel):
    if len(data_reeks) < 5: 
        return
    
    veilige_data = np.where(data_reeks <= 0, 0.1, data_reeks)
    kwantiel_niveaus = np.linspace(0.01, 0.99, 100)
    kwantielen_empirisch = np.quantile(veilige_data, kwantiel_niveaus)
    
    plt.figure(figsize=(8, 8))

    # ik probeer eerst een lognormale verdeling, ik zie wel enkele uitschieters... maar het lijkt ook wel een piek in het begin van de grafiek te hebben wat op een lognormale verdeling lijkt (dan zijn de uitschieters slecht in de qq plot)
    try:
        lognorm_parameters = stats.lognorm.fit(veilige_data)
        lognorm_samples = stats.lognorm.rvs(*lognorm_parameters, size=10000)
        kwantielen_lognorm = np.quantile(lognorm_samples, kwantiel_niveaus)
        plt.scatter(kwantielen_lognorm, kwantielen_empirisch, color='green', marker='o', alpha=0.5)
    except:
        pass

    # voor de uitschieters probeer ik ook een GMM als het zinvol is dan kunnen we het gebruiken als dat niet werkt, dan is empirisch het enigste waar ik aan denk    
    try:
        gmm_model = pas_gmm_toe(veilige_data)
        gmm_samples = sample_uit_gmm(gmm_model, aantal_samples=10000)
        kwantielen_gmm = np.quantile(gmm_samples, kwantiel_niveaus)
        plt.scatter(kwantielen_gmm, kwantielen_empirisch, color='brown', marker='^', alpha=0.7)
    except:
        pass
             
    minimum_waarde = kwantielen_empirisch.min() - 1
    maximum_waarde = kwantielen_empirisch.max() + 1
    plt.plot([minimum_waarde, maximum_waarde], [minimum_waarde, maximum_waarde])
    
    plt.xlabel(xlabel)
    plt.ylabel('data verdeling')
    plt.title(f"Q-Q Plot: {titel}")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(bestandsnaam)
    plt.close()

alles_samen = dataframe['duur_minuten'].values

# alles samen vergelijken met locatie en dag van de week apart,
# kan er alles worden samengenomen
for locatie in locaties:
    for weekdag_index, weekdag_naam in enumerate(dagen_namen):
        locatie_klopt = dataframe['locatie'] == locatie
        weekdag_klopt = dataframe['weekdag_index'] == weekdag_index

        subset = dataframe[locatie_klopt & weekdag_klopt]

        data_locatie_weekdag = subset['duur_minuten'].values

        titel = f"Alles samen vs {locatie} - {weekdag_naam}"
        maak_qq_historisch(alles_samen, data_locatie_weekdag, titel, f"{map_historisch}/1_alles_vs_{locatie}_{weekdag_naam}.png", "Alles samen", f"{locatie} - {weekdag_naam}")

for locatie in locaties:
    data_locatie = dataframe['locatie'] == locatie
    data_locatie_alle_dagen = dataframe[data_locatie]['duur_minuten'].values
    for weekdag_index, weekdag_naam in enumerate(dagen_namen):
        locatie_klopt = dataframe['locatie'] == locatie
        weekdag_klopt = dataframe['weekdag_index'] == weekdag_index
        subset = dataframe[locatie_klopt & weekdag_klopt]

        data_locatie_weekdag = subset['duur_minuten'].values
        titel = f"{locatie} (Alle dagen) vs {locatie} - {weekdag_naam}"
        maak_qq_historisch(data_locatie_alle_dagen, data_locatie_weekdag, titel, f"{map_historisch}/2_{locatie}_vs_{weekdag_naam}.png", f"{locatie} - {weekdag_naam}", f"{locatie} - {weekdag_naam}")

for weekdag_index, weekdag_naam in enumerate(dagen_namen):
    data_weekdag = dataframe['weekdag_index'] == weekdag_index
    data_weekdag_alle_locaties = dataframe[data_weekdag]['duur_minuten'].values
    for locatie in locaties:
        locatie_klopt = dataframe['locatie'] == locatie
        weekdag_klopt = dataframe['weekdag_index'] == weekdag_index
        subset = dataframe[locatie_klopt & weekdag_klopt]
        data_locatie_weekdag = subset['duur_minuten'].values
        titel = f"{weekdag_naam} (Alle locaties) vs {locatie} - {weekdag_naam}"
        maak_qq_historisch(data_weekdag_alle_locaties, data_locatie_weekdag, titel, f"{map_historisch}/3_{weekdag_naam}_vs_{locatie}.png", f"{weekdag_naam} (Alle locaties)", f"{locatie} - {weekdag_naam}")

for locatie in locaties:
    for weekdag_index, weekdag_naam in enumerate(dagen_namen):
        locatie_klopt = dataframe['locatie'] == locatie
        weekdag_klopt = dataframe['weekdag_index'] == weekdag_index
        subset = dataframe[locatie_klopt & weekdag_klopt]

        data_locatie_weekdag = subset['duur_minuten'].values
        bestandsnaam_locatie_weekdag = f"4_{locatie}_{weekdag_naam}"
        maak_qq_plot_continu(data_locatie_weekdag, f"{locatie} - {weekdag_naam}", f"{map_modellen}/{bestandsnaam_locatie_weekdag}.png", f"{locatie} - {weekdag_naam}")
        maak_histogram_continu(data_locatie_weekdag, f"{locatie} - {weekdag_naam}", f"{map_histogrammen}/{bestandsnaam_locatie_weekdag}.png")


# distributie fitten over duur is niet mogelijk omdat de duur enorme uitschieters heeft, die niet gefilterd mogen worden
# omdat er op verschillende locaties enkele uitschieters te zien zijn.
# en ook om starttijd te koppelen aan de duur, is het beter om per uur te modelleren want 

# de uren verschillen aanzienlijk in de duur per uur. dus dagdelen samennemen is nadelig
uren_per_dagdeel = {
    'Ochtend': [6, 7, 8, 9, 10, 11],
    'Middag': [12, 13, 14, 15, 16, 17],
    'Avond': [18, 19, 20, 21, 22, 23, 0, 1, 2, 3, 4, 5]
}

# hier worden alle data verzamelt per dag per locatie en dan per dagdeel en dan per uur

for locatie in locaties:
    for weekdag_index, weekdag_naam in enumerate(dagen_namen):
        locatie_klopt = dataframe['locatie'] == locatie
        weekdag_klopt = dataframe['weekdag_index'] == weekdag_index
        subset = dataframe[locatie_klopt & weekdag_klopt]

        for dagdeel, uren_lijst in uren_per_dagdeel.items():
            subset_dagdeel = subset[subset['dagdeel'] == dagdeel]
            data_dagdeel = subset_dagdeel['duur_minuten'].values
            
            if len(data_dagdeel) < 15: 
                continue 
            
            for uur in uren_lijst:
                subset_uur = subset_dagdeel[subset_dagdeel['start_uur'] == uur]
                data_uur = subset_uur['duur_minuten'].values
                
                titel = f"{locatie} - {weekdag_naam} ({dagdeel} bin) vs Uur {uur}"
                bestandsnaam = f"{map_uren}/vergelijk_{locatie}_{weekdag_naam}_{dagdeel}_uur_{uur}.png"
                
                maak_qq_historisch(data_dagdeel, data_uur, titel, bestandsnaam, f"{locatie} - {weekdag_naam} ({dagdeel} bin)", f"{locatie} - {weekdag_naam} Uur {uur}")


# Hier vergelijken we de historische data van de 3-uur bucket met de historische data van 1 specifiek uur binnen die bucket buckets zijn:
# 00-03, 03-06, 06-09, 09-12, 12-15, 15-18, 18-21, 21-24
# zelfde effect als bij dagdelen, er is verlies van informatie (geen zelfde trend als per uur afzonderlijk)

for locatie in locaties:
    for weekdag_index, weekdag_naam in enumerate(dagen_namen):
        locatie_klopt = dataframe['locatie'] == locatie
        weekdag_klopt = dataframe['weekdag_index'] == weekdag_index
        subset = dataframe[locatie_klopt & weekdag_klopt]

        for bucket_label in subset['drie_uur_bucket'].unique():
            subset_bucket = subset[subset['drie_uur_bucket'] == bucket_label]
            data_bucket = subset_bucket['duur_minuten'].values
            
            if len(data_bucket) < 15: 
                continue 
            
            for uur in subset_bucket['start_uur'].unique():
                subset_uur = subset_bucket[subset_bucket['start_uur'] == uur]
                data_uur = subset_uur['duur_minuten'].values
                
                if len(data_uur) < 5: 
                    continue
                
                titel = f"{locatie} - {weekdag_naam} (Bucket {bucket_label}) vs Uur {uur}"
                bestandsnaam = f"{map_uren}/vergelijk_{locatie}_{weekdag_naam}_bucket_{bucket_label}_uur_{uur}.png"
                maak_qq_historisch(data_bucket, data_uur, titel, bestandsnaam, f"{locatie} - {weekdag_naam} (Bucket {bucket_label})", f"{locatie} - {weekdag_naam} Uur {uur}")