import json
import numpy as np
import pandas as pd
from sklearn.mixture import GaussianMixture

with open('data/data_personenwagens.json', 'r', encoding='utf-8') as bestand:
    data = json.load(bestand)

rijen = []
for reservering in data.get('reserveringen'):
    datum_tijd = pd.to_datetime(reservering['startTijd'])
    start_minuten = datum_tijd.hour * 60 + datum_tijd.minute + datum_tijd.second / 60.0
    duur_minuten = reservering['duur']
    sleutels_opgehaald = 0
    if reservering.get('sleutelsOpgehaald'): 
        sleutels_opgehaald = 1
    
    rijen.append({
        'locatie': reservering['locatie'],
        'datum': datum_tijd.date(),
        'start_minuten': start_minuten,
        'duur_minuten': duur_minuten,
        'start_uur': datum_tijd.hour,
        'weekdag_index': datum_tijd.weekday(),
        'sleutels_opgehaald': sleutels_opgehaald
    })

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

        # to list voor de json
        if aic_score < beste_aic:
            beste_aic = aic_score
            beste_gmm_model = {
                'aantal_componenten': aantal_componenten,
                'gewichten': gmm.weights_.tolist(),
                'gemiddeldes': gmm.means_.flatten().tolist(),
                'varianties': gmm.covariances_.flatten().tolist()
            }
    return beste_gmm_model

def bepaal_dagdeel(uur):
    if 6 <= uur < 12: 
        return 'Ochtend'
    elif 12 <= uur < 18: 
        return 'Middag'
    else: 
        return 'Avond'

dataframe = pd.DataFrame(rijen)
locaties = dataframe['locatie'].unique()
dagen_namen = ['Maandag', 'Dinsdag', 'Woensdag', 'Donderdag', 'Vrijdag']

parameters = {
    # voorlooptijd: 
    # omdat de exacte boekingsdatum niet in de dataset zit. Moeten er zelf aannames worden gemaakt. daarom worden 
    # er 3 type mensen gemodelleerd: 
    # mensen die op voorhand plannen, dus meer dan 3 dagen op voorhand
    # mensen die gemiddeld plannen, dus 2 tot 72  uur op voorhand dus niet extreem vroeg op voorhand
    # mensen die noodgevallen moeten oplossen, dus minder dan 2 uur op voorhand. 
    # zo opsplitsen kan er later nog met kansen worden getest op andere kansgevallen.
    # dit hoeft opzich niet in de json te staan, maar in deze file wordt alle keuzes gemaakt, dus ook voor deze distributie
    'voorlooptijd': {
        'profielen': {
            'planner': {'kans': 0.15, 'minimum_minuten': 4320, 'maximum_minuten': 20160},  # 3 dagen tot 2 weken
            'gemiddeld': {'kans': 0.65, 'minimum_minuten': 120, 'maximum_minuten': 4320},   # 2 tot 72 uur (1-3 dagen op voorhand)
            'nood': {'kans': 0.20, 'minimum_minuten': 5, 'maximum_minuten': 120}           # 5 min tot 2 uur
        }
    },
    'locaties': {}
}

for locatie in locaties:
    parameters['locaties'][locatie] = {} 
    alle_data_locatie = dataframe[dataframe['locatie'] == locatie].copy()

    min_datum = dataframe['datum'].min()
    max_datum = dataframe['datum'].max()
    alle_kalenderdagen = pd.date_range(start=min_datum, end=max_datum).date

    for weekdag_index, dag_naam in enumerate(dagen_namen):
        locatie_klopt = dataframe['locatie'] == locatie
        weekdag_klopt = dataframe['weekdag_index'] == weekdag_index
        subset = dataframe[locatie_klopt & weekdag_klopt].copy()
        
        # aantal reserveringen per dag: Poisson verdeling
        # dit is discrete data, aantal reserveringen Uit de Q-Q plots bleek dat 
        # zowel Poisson als NegBin visueel bijna hetzelfde zijn tov de referentielijn. Er is gekozen voor Poisson, omdat er slechts 1 parameter nodig is 
        # in plaats van 2 (n en p) bij NegBin.
        # er wordt ook altijd opgesplitst per locatie en per weekdag,  de qq plots historisch tonen mooi aan dat het beter is om alles apart te modelleren per locatie en per weekdag.
        # (zelfde patroon bij duur en starttijd)
    
        datums_voor_deze_weekdag = []
        for d in alle_kalenderdagen:
            if d.weekday() == weekdag_index:
                datums_voor_deze_weekdag.append(d)
            
        orders_per_aanwezige_dag = subset.groupby('datum').size()
    
        orders_compleet = orders_per_aanwezige_dag.reindex(datums_voor_deze_weekdag, fill_value=0)
    
        lambda_orders = float(orders_compleet.mean())
        
        # starttijd: Gaussian Mixture Model (GMM)
        # GMM is een verdeling die meerdere normaalverdelingen combineert over niet normaal verdeelde data.
        # als er gekeken is naar de histogrammen dan is er duidelijk te zien dat het geen patroon volgt van bijvoorbeeld een lognormale, normale, weibull, gamma of andere verdeling getoond in de les. Wel veel pieken te zien in de histogrammen, daarom is er gekozen om een GMM te gebruiken.
        starttijden = subset['start_minuten'].values
        gmm_starttijd = pas_gmm_toe(starttijden)
        
        # legte van een reservering: Empirische verdeling
        # Het begin lijkt wel goed voor GMM maar er zitten uitschieters inde data die ver liggen van de andere datapunten. om die mee te nemen is het niet mogelijk om een verdeling te fitten.
        # omdat de andere verdelingen wel passen en dus nieuwe samples kunnen maken, is het geen ramp dat duur een empirische verdeling is, er wordt wel nog altijd opgesplitst per locatie en per weekdag en per uur... omdat in bins zoals 3uur en dagdelen als ochtend middag en avond het toch een andere trend geeft. Daarom is er gekozen om eerst per uur te samplen empirisch, als er geen data is binnen dat uur maar er toevallig wel een startuur is gesampeld. dan is er de 3 uur bin als daar ook geen data is voor die locatie dan is er het dagdeel, en tenslotte de hele dag.
        # dit koppelt de starttijden met de duur

        # Empirische Cumulatieve Distributiefunctie (ECDF) voor duur per uur
        subset['drie_uur_bin'] = (subset['start_uur'] // 3) * 3
        subset['dagdeel'] = subset['start_uur'].apply(bepaal_dagdeel)
            
        alle_duren_dag = subset['duur_minuten'].tolist()
        empirische_duur_per_uur = {}

        aantal_drie_uur_bins_gekozen = 0
        aantal_dagdelen_gekozen = 0
        aantal_hele_dag_gekozen = 0
            
        for uur in range(24):
            data_uur = subset[subset['start_uur'] == uur]['duur_minuten'].tolist()
                
            if len(data_uur) >= 5:
                # er is genoeg data voor het uur
                empirische_duur_per_uur[str(uur)] = data_uur
            else:
                # naar 3-uur bin
                bin_uur = (uur // 3) * 3
                data_3u = subset[subset['drie_uur_bin'] == bin_uur]['duur_minuten'].tolist()
                    
                if len(data_3u) >= 5:
                    empirische_duur_per_uur[str(uur)] = data_3u
                    aantal_drie_uur_bins_gekozen += 1
                else:
                    # naar dagdeel bin (Ochtend/Middag/Avond)
                    dagdeel = bepaal_dagdeel(uur)
                    data_dagdeel = subset[subset['dagdeel'] == dagdeel]['duur_minuten'].tolist()
                    
                    if len(data_dagdeel) >= 5:
                        empirische_duur_per_uur[str(uur)] = data_dagdeel
                        aantal_dagdelen_gekozen += 1
                    else:
                        # naar de hele dag
                        empirische_duur_per_uur[str(uur)] = alle_duren_dag
                        aantal_hele_dag_gekozen += 1

        print(f"Locatie: {locatie}, Weekdag: {dag_naam} - Aantal 3-uur bins gekozen: {aantal_drie_uur_bins_gekozen}, Aantal dagdelen gekozen: {aantal_dagdelen_gekozen}, Aantal hele dag gekozen: {aantal_hele_dag_gekozen}")

        
        # sleutels niet opgehaald: Empirische verdeling
        # Ik doe zelfde principe als de duur omdat er telkens per uur maar 1 enkele kans wordt berekend is het een emprische verdeling
        # later gebruiken we een kans verdeling met de kans als p waarde in een binomiale verdeling, aantal orders is de n waarde.
        # ik moet hier niet de aantallen printen want het is hetzelfde verloop als bij de duur
        alle_sleutels_dag = subset['sleutels_opgehaald'].tolist()
        kans_sleutels_per_uur = {}
        
        for uur in range(24):
            data_sleutel_uur = subset[subset['start_uur'] == uur]['sleutels_opgehaald'].tolist()
            
            if len(data_sleutel_uur) >= 5:
                kans_sleutels_per_uur[str(uur)] = float(np.mean(data_sleutel_uur))
            else:
                bin_uur = (uur // 3) * 3
                data_sleutel_3u = subset[subset['drie_uur_bin'] == bin_uur]['sleutels_opgehaald'].tolist()
                
                if len(data_sleutel_3u) >= 5:
                    kans_sleutels_per_uur[str(uur)] = float(np.mean(data_sleutel_3u))
                else:
                    dagdeel = bepaal_dagdeel(uur)
                    data_sleutel_dagdeel = subset[subset['dagdeel'] == dagdeel]['sleutels_opgehaald'].tolist()
                    
                    if len(data_sleutel_dagdeel) >= 5:
                        kans_sleutels_per_uur[str(uur)] = float(np.mean(data_sleutel_dagdeel))
                    else:
                        kans_sleutels_per_uur[str(uur)] = float(np.mean(alle_sleutels_dag))
                        
        parameters['locaties'][locatie][dag_naam] = {
            'lambda_orders': lambda_orders,
            'gmm_starttijd': gmm_starttijd,
            'empirische_duur_per_uur': empirische_duur_per_uur,
            'kans_sleutels_per_uur': kans_sleutels_per_uur
        }

with open('data/simulatie_parameters.json', 'w', encoding='utf-8') as bestand:
    json.dump(parameters, bestand, ensure_ascii=False, indent=4)

    
                    