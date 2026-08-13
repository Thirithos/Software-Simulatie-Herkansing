import json
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import stats

# eerste analyse file voor het nabootsten van de historische data dan moet er geweten zijn hoeveel orders er per dag zijn,
# en ook welke distributies hier geschikt voor zijn
# het is discrete data dus discrete functies zijn nodig.
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

# elke unieke locatie
locaties = dataframe['locatie'].unique()

# alle kalenderdagen om tussen te loopen
min_datum = dataframe['datum'].min()
max_datum = dataframe['datum'].max()
alle_kalenderdagen = pd.date_range(start=min_datum, end=max_datum).date


map_historisch = "qq_plots/aantal_reserveringen_historisch"
map_modellen = "qq_plots/aantal_reserveringen_modellen"
map_histogrammen = "histogrammen/aantal_reserveringen"
os.makedirs(map_historisch, exist_ok=True)
os.makedirs(map_modellen, exist_ok=True)
os.makedirs(map_histogrammen, exist_ok=True)

# functie voor historische vergelijking
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

# qq plots om poisson en negbinomiale distributie te vergelijken met de historische data
def maak_qq_plot_discreet(data_reeks, titel, bestandsnaam):
    data_reeks = np.round(data_reeks).astype(int)
    kwantiel_niveaus = np.linspace(0.01, 0.99, 100)
    kwantielen_empirisch = np.quantile(data_reeks, kwantiel_niveaus)
    
    plt.figure(figsize=(8, 8))

    # poisson heeft 1 parameter, lambda, met als aanname dat de variantie gelijk is aan gemiddelde lambda. 
    lambda_waarde = np.mean(data_reeks)
    kwantielen_poisson = stats.poisson.ppf(kwantiel_niveaus, lambda_waarde)
    plt.scatter(kwantielen_poisson, kwantielen_empirisch, color='blue', marker='o', alpha=0.6, label='Poisson')

    # negatieve binomiale distributie heeft 2 parameters
    # omdat de bovengrens onbegrensd is, kan er theoretisch oneindig veel reserveringen zijn, (er is dus ook geen kans op succes)
    # wordt negatieve binomiaal gebruikt als extra alternatief voor de poisson. Dit is vooral handig als de variantie groter is dan het gemiddelde.
    
    # gemiddelde  = (n * (1 - p)) / p
    # variantie = (n * (1 - p)) / p**2
    
    # variantie = gemiddelde * (1 / p)
    # dit leidt tot p_parameter = gemiddelde / variantie
    # als variantie groot is is de p of kans heel laag.

    # de n parameter uit gemiddelde = (n * (1-p)) /p door p te vervangen door p_parameter = gemiddelde / variantie
    # gemiddelde = (n * (1 - (gemiddelde / variantie))) / (gemiddelde / variantie)
    # gemiddelde **2 / variantie = n * (1 - (gemiddelde / variantie))
    # gemiddelde **2 / (variantie * (1 - (gemiddelde / variantie))) = n
    # n = (gemiddelde ** 2) / (variantie - gemiddelde)

    # De keuze om negatief binomiaal te testen is omdat de variantie groter kan zijn dan het gemiddelde, (dankzij uitschieters)
    variantie = np.var(data_reeks, ddof=1)
    if variantie > lambda_waarde:
        p_parameter = lambda_waarde / variantie
        n_parameter = (lambda_waarde ** 2) / (variantie - lambda_waarde)
        kwantielen_negbin = stats.nbinom.ppf(kwantiel_niveaus, n_parameter, p_parameter)
        plt.scatter(kwantielen_negbin, kwantielen_empirisch, color='red', marker='x', alpha=0.6, label='Negatieve Binomiaal')
    
    min_val = min(kwantielen_empirisch.min(), kwantielen_poisson.min()) - 1
    max_val = max(kwantielen_empirisch.max(), kwantielen_poisson.max()) + 1
    plt.plot([min_val, max_val], [min_val, max_val])
    
    plt.xlabel('Theoretische kwantielen')
    plt.ylabel('Geobserveerde kwantielen')
    plt.title(f"Q-Q Plot: {titel}")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(bestandsnaam)
    plt.close()

# deze functie maakt een histogram van de discrete data reeks
def maak_histogram_discreet(data_reeks, titel, bestandsnaam):
    if len(data_reeks) < 5: return

    data_reeks = data_reeks.astype(int)
    minimum_waarde = int(data_reeks.min())
    maximum_waarde = int(data_reeks.max())
    # de bins zijn gemaakt vooral bij het plotten van discrete data, zodat de bins gecentreerd zijn rond de gehele getallen.
    discrete_bins = np.arange(minimum_waarde - 0.5, maximum_waarde + 1.5, 1)
    
    plt.figure(figsize=(8, 5))
    plt.hist(data_reeks, bins=discrete_bins, edgecolor='black', alpha=0.7, color='steelblue')
    plt.title(f"Histogram: {titel}")
    plt.xlabel('Aantal reserveringen per dag')
    plt.ylabel('Frequentie')
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

# belangrijk want anders zullen dagen waar 0 reserveringen zijn geweest niet meegenomen worden in de analyse.
alles_samen = dataframe.groupby('datum').size().reindex(alle_kalenderdagen, fill_value=0).values

# alles samen vergelijken met locatie en dag van de week apart,
# kan er alles worden samengenomen
for locatie in locaties:
    for weekdag_index, weekdag_naam in enumerate(dagen_namen):

        # eerst alle datums ophalen die overeenkomen met de weekdag
        datums_voor_deze_weekdag = datums_per_weekdag[weekdag_index]
        
        locatie_klopt = dataframe['locatie'] == locatie
        weekdag_klopt = dataframe['weekdag_index'] == weekdag_index

        subset = dataframe[locatie_klopt & weekdag_klopt]

        reserveringen_per_dag = subset.groupby('datum').size()
        # aanvullen met 0 want anders is het gemiddelde niet correct
        volledige_reeks = reserveringen_per_dag.reindex(datums_voor_deze_weekdag, fill_value=0)
        data_locatie_dag = volledige_reeks.values

        titel = f"Alles samen vs {locatie} - {weekdag_naam}"
        maak_qq_historisch(alles_samen, data_locatie_dag, titel, f"{map_historisch}/1_alles_vs_{locatie}_{weekdag_naam}.png", "Alles samen", f"{locatie} - {weekdag_naam}")

# locaties apart maar dagen samen vs per locatie en per dag
for locatie in locaties:
    reserveringen_locatie_totaal = dataframe[dataframe['locatie'] == locatie].groupby('datum').size()
    data_locatie_alle_dagen = reserveringen_locatie_totaal.reindex(alle_kalenderdagen, fill_value=0).values
    
    for weekdag_index, weekdag_naam in enumerate(dagen_namen):
        datums_voor_deze_weekdag = datums_per_weekdag[weekdag_index]
        
        locatie_klopt = dataframe['locatie'] == locatie
        weekdag_klopt = dataframe['weekdag_index'] == weekdag_index

        subset = dataframe[locatie_klopt & weekdag_klopt]
        reserveringen_per_dag = subset.groupby('datum').size()
        volledige_reeks = reserveringen_per_dag.reindex(datums_voor_deze_weekdag, fill_value=0)
        data_locatie_dag = volledige_reeks.values

        titel = f"{locatie} (Alle dagen) vs {locatie} - {weekdag_naam}"
        maak_qq_historisch(data_locatie_alle_dagen, data_locatie_dag, titel, f"{map_historisch}/2_{locatie}_vs_{locatie}_{weekdag_naam}.png", f"{locatie} (Alle dagen)", f"{locatie} - {weekdag_naam}")

# dagen apart maar locaties samen vs per locatie en per dag
for weekdag_index, weekdag_naam in enumerate(dagen_namen):
    datums_voor_deze_weekdag = datums_per_weekdag[weekdag_index]
    
    reserveringen_dag_totaal = dataframe[dataframe['weekdag_index'] == weekdag_index].groupby('datum').size()
    data_dag_alle_locaties = reserveringen_dag_totaal.reindex(datums_voor_deze_weekdag, fill_value=0).values
    
    for locatie in locaties:
        locatie_klopt = dataframe['locatie'] == locatie
        weekdag_klopt = dataframe['weekdag_index'] == weekdag_index
        
        subset = dataframe[locatie_klopt & weekdag_klopt]
        reserveringen_per_dag = subset.groupby('datum').size()
        volledige_reeks = reserveringen_per_dag.reindex(datums_voor_deze_weekdag, fill_value=0)
        data_locatie_dag = volledige_reeks.values

        titel = f"{weekdag_naam} (Alle locaties) vs {locatie} - {weekdag_naam}"
        maak_qq_historisch(data_dag_alle_locaties, data_locatie_dag, titel, f"{map_historisch}/3_{weekdag_naam}_vs_{locatie}_{weekdag_naam}.png", f"{weekdag_naam} (Alle locaties)", f"{locatie} - {weekdag_naam}")

# histogrammen en qq plots per locatie en per dag van de week.
for locatie in locaties:
    for weekdag_index, weekdag_naam in enumerate(dagen_namen):
        
        datums_voor_deze_weekdag = datums_per_weekdag[weekdag_index]
        
        locatie_klopt = dataframe['locatie'] == locatie
        weekdag_klopt = dataframe['weekdag_index'] == weekdag_index
        
        subset = dataframe[locatie_klopt & weekdag_klopt]

        reserveringen_per_dag = subset.groupby('datum').size()
        volledige_reeks = reserveringen_per_dag.reindex(datums_voor_deze_weekdag, fill_value=0)
        data_locatie_dag = volledige_reeks.values

        bestandsnaam_locatie_dag = f"4_{locatie}_{weekdag_naam}"
        maak_qq_plot_discreet(data_locatie_dag, f"{locatie} - {weekdag_naam}", f"{map_modellen}/{bestandsnaam_locatie_dag}.png")
        maak_histogram_discreet(data_locatie_dag, f"{locatie} - {weekdag_naam}", f"{map_histogrammen}/{bestandsnaam_locatie_dag}.png")