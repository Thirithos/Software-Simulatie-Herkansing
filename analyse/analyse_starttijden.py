import json
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.mixture import GaussianMixture

with open('data/data_personenwagens.json', 'r', encoding='utf-8') as bestand:
    data = json.load(bestand)


# tijd in minuten plaatsen ipv ruwe starttijd als datetime object
rijen = []
for reservering in data.get('reserveringen', []):
    datum_tijd = pd.to_datetime(reservering['startTijd'])
    start_minuten = datum_tijd.hour * 60 + datum_tijd.minute + datum_tijd.second / 60.0
    
    rijen.append({
        'locatie': reservering['locatie'],
        'start_minuten': start_minuten,
        'weekdag_index': datum_tijd.weekday(),
        'weekdag_naam': datum_tijd.day_name()
    })
            
dataframe = pd.DataFrame(rijen)
dagen_namen = ['Maandag', 'Dinsdag', 'Woensdag', 'Donderdag', 'Vrijdag']
locaties = dataframe['locatie'].unique()

map_historisch = "qq_plots/starttijden_historisch"
map_modellen = "qq_plots/starttijden_modellen"
map_histogrammen = "histogrammen/starttijden"
os.makedirs(map_historisch, exist_ok=True)
os.makedirs(map_modellen, exist_ok=True)
os.makedirs(map_histogrammen, exist_ok=True)

def maak_qq_historisch(data_reeks_1, data_reeks_2, titel, bestandsnaam, xlabel, ylabel):
    if len(data_reeks_1) < 5 or len(data_reeks_2) < 5: 
        return
    
    kwantiel_niveaus = np.linspace(0.01, 0.99, 100)
    kwantielen_1 = np.quantile(data_reeks_1, kwantiel_niveaus)
    kwantielen_2 = np.quantile(data_reeks_2, kwantiel_niveaus)
    
    plt.figure(figsize=(8, 8))
    plt.scatter(kwantielen_1, kwantielen_2, color='green', marker='o', alpha=0.6)
    
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
    if len(data_reeks) < 5: 
        return None

    # rijen zijn observaties, kolommen zijn variabelen, we hebben er 
    # maar 1 dus 1 kolom nodig, -1 betekent het aantal rijen bepalen door de lengte van de data_reeks
    data_2d = np.array(data_reeks).reshape(-1, 1)
    
    beste_aic = 10000000
    beste_gmm_model = None

    # uit histogrammen zie ik dat er meestal 2 tot 4 pieken zijn maar zker niet normaal verdeeld over de hele figuur (dan is er maar 1 component)
    for aantal_componenten in range(2, 4):
        # componenten is aantal curves, waarvan elke curve full is dus elke heeft eigen variantie, bij 2 componenten zoekt GuassianMixture naar 2 pieken, over 1000 iteraties het stopt als het verschil kleiner is dan 1/1000000, random state moet seed krijgen, dit is 0 gewoon om reproduceerbaar te zijn aangezien de algoritmes die de juiste verdeling zoeken gevoelig zijn aan de startwaarden
        gmm = GaussianMixture(n_components=aantal_componenten, covariance_type='full', max_iter=1000, tol=1e-6, random_state=0)
        # enkel nog de data fitten en aic berekenen
        gmm.fit(data_2d)
        aic_score = gmm.aic(data_2d)

        # een aic score is best zo laag mogelijk
        # aic gebruikt likelihood van goodness of fit en altijd parameters, meer parameters = hogere aic score, meer likelihood = lagere aic score.
        
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
        # hier wordt gekozen welke normaalverdeling gebruikt wordt
        # op basis van de fit eerder
        component_index = np.random.choice(gmm_model['aantal_componenten'], p=gmm_model['gewichten'])

        # gemiddelde en standaardafwijking van die normaalverdeling is gekend
        gemiddelde = gmm_model['gemiddeldes'][component_index]
        standaardafwijking = np.sqrt(gmm_model['varianties'][component_index])
        # de waarde trekken via normaalverdeling met dat gemiddelde en standaardafwijking
        getrokken_waarde = np.random.normal(gemiddelde, standaardafwijking)
        
        samples.append(getrokken_waarde)
    return np.array(samples)

def maak_qq_plot_continu(data_reeks, titel, bestandsnaam, xlabel):
    if len(data_reeks) < 5: 
        return
    
    veilige_data = np.where(data_reeks <= 0, 0.1, data_reeks)
    kwantiel_niveaus = np.linspace(0.01, 0.99, 100)
    
    # Beide reeksen kwantielen omzetten naar uren (gewoon overzichtelijker voor de grafiek, ipv te zitten rekenen met minuten)
    kwantielen_empirisch = np.quantile(veilige_data, kwantiel_niveaus) / 60.0 
    
    plt.figure(figsize=(8, 8))
        
    gmm_model = pas_gmm_toe(veilige_data)
    gmm_samples = sample_uit_gmm(gmm_model, aantal_samples=10000)
    kwantielen_gmm = np.quantile(gmm_samples, kwantiel_niveaus) / 60.0 
    
    plt.scatter(kwantielen_gmm, kwantielen_empirisch, color='red', marker='x', alpha=0.6)
            
    # Nu de min en max waarden ook in uren berekenen (1 minuten = 1/60 uren)
    min_val =min(kwantielen_empirisch.min(), kwantielen_gmm.min()) - (1/60.0) 
    max_val = max(kwantielen_empirisch.max(), kwantielen_gmm.max()) + (1/60.0) 
    plt.plot([min_val, max_val], [min_val, max_val])
    
    plt.xlabel(xlabel)
    plt.ylabel("GMM kwantielen")
    plt.title(f"Q-Q Plot: {titel}")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(bestandsnaam)
    plt.close()

def maak_histogram_continu(data_reeks, titel, bestandsnaam):
    if len(data_reeks) < 5: 
        return
    #data reeks omzetten naar uren
    data_reeks = np.array(data_reeks) / 60.0
    aantal_bins = int(np.sqrt(len(data_reeks)))
    plt.figure(figsize=(8, 5))
    plt.hist(data_reeks, bins=aantal_bins, edgecolor='black', alpha=0.7, color='steelblue')
    plt.title(f"Histogram: {titel}")
    plt.xlabel('Starttijd')
    plt.ylabel('Frequentie')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(bestandsnaam)
    plt.close()

alles_samen = dataframe['start_minuten'].values

# alles samen dus dag en locaties samengevoegd vs alles apart
for locatie in locaties:
    for weekdag_index, weekdag_naam in enumerate(dagen_namen):
        locatie_klopt = dataframe['locatie'] == locatie
        weekdag_klopt = dataframe['weekdag_index'] == weekdag_index
        
        subset = dataframe[locatie_klopt & weekdag_klopt]

        data_locatie_dag = subset['start_minuten'].values
        titel = f"Alles samen vs {locatie} - {weekdag_naam}"
        maak_qq_historisch(alles_samen, data_locatie_dag, titel, f"{map_historisch}/1_alles_vs_{locatie}_{weekdag_naam}.png", "Alles samen", f"{locatie} - {weekdag_naam}")

# alle locaties apart maar alle dagen samen vs alles apart
for locatie in locaties:
    data_locatie_alle_dagen = dataframe[dataframe['locatie'] == locatie]['start_minuten'].values

    for weekdag_index, weekdag_naam in enumerate(dagen_namen):
        locatie_klopt = dataframe['locatie'] == locatie
        weekdag_klopt = dataframe['weekdag_index'] == weekdag_index
        
        subset = dataframe[locatie_klopt & weekdag_klopt]
        data_locatie_dag = subset['start_minuten'].values

        titel = f"{locatie} (Alle dagen) vs {locatie} - {weekdag_naam}"
        maak_qq_historisch(data_locatie_alle_dagen, data_locatie_dag, titel, f"{map_historisch}/2_{locatie}_vs_{locatie}_{weekdag_naam}.png", f"{locatie} (Alle dagen)", f"{locatie} - {weekdag_naam}")

# alle dagen apart maar alle locaties samen vs alles apart
for weekdag_index, weekdag_naam in enumerate(dagen_namen):
    data_dag_alle_locaties = dataframe[dataframe['weekdag_index'] == weekdag_index]['start_minuten'].values
    for locatie in locaties:
        locatie_klopt = dataframe['locatie'] == locatie
        weekdag_klopt = dataframe['weekdag_index'] == weekdag_index
        
        subset = dataframe[locatie_klopt & weekdag_klopt]

        data_locatie_dag = subset['start_minuten'].values

        titel = f"{weekdag_naam} (Alle locaties) vs {locatie} - {weekdag_naam}"
        maak_qq_historisch(data_dag_alle_locaties, data_locatie_dag, titel, f"{map_historisch}/3_{weekdag_naam}_vs_{locatie}_{weekdag_naam}.png", f"{weekdag_naam} (Alle locaties)", f"{locatie} - {weekdag_naam}")

# ik heb gekozen voor alle dagen en alle locaties apart te modelleren, omdat bij de andere dit ook het geval is (alle locaties apart met dagen samen zou nog kunnen)    
for locatie in locaties:
    for weekdag_index, weekdag_naam in enumerate(dagen_namen):
        locatie_klopt = dataframe['locatie'] == locatie
        weekdag_klopt = dataframe['weekdag_index'] == weekdag_index
        
        subset = dataframe[locatie_klopt & weekdag_klopt]

        data_locatie_dag = subset['start_minuten'].values

        bestandsnaam_locatie_dag = f"4_{locatie}_{weekdag_naam}"
        maak_qq_plot_continu(data_locatie_dag, f"{locatie} - {weekdag_naam}", f"{map_modellen}/{bestandsnaam_locatie_dag}.png", f"{locatie} - {weekdag_naam}")
        maak_histogram_continu(data_locatie_dag, f"{locatie} - {weekdag_naam}", f"{map_histogrammen}/{bestandsnaam_locatie_dag}.png")
