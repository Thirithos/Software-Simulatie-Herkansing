import json
import numpy as np

def bereken_boekingsmoment(absolute_starttijd, actieve_voorlooptijd):
    # deze functie dient om nachturen te skippen, het is maar raar dat er plotw om 3:00 een reservering  boeking gebeurt...
    # daarom deze functie deze springt van 23:00 tot 5:00 over nachturen heen; (let wel op starttijd wordt gesampled van echte data)
    resterende_minuten = actieve_voorlooptijd
    # is in minuten
    huidige_tijd = absolute_starttijd
    
    while resterende_minuten > 0:
        minuut_van_de_dag = huidige_tijd % 1440
        
        if minuut_van_de_dag > 1380:
            # tussen 23:00 en middernacht: spring terug naar 23:00 waarbij minuut_van_de_dag -1380 tijd nodig is om terug te springen
            huidige_tijd = huidige_tijd - (minuut_van_de_dag - 1380)
            continue
            
        elif minuut_van_de_dag < 300:
            # tussen middernacht en 05:00: spring terug naar 23:00 van de vorige dag opnieuw zorgt +60 voor de tijd om tot 23:00 te geraken vorige dag
            huidige_tijd = huidige_tijd - (minuut_van_de_dag + 60)
            continue
            
        else:
            # Tussen 05:00 en 23:00
            beschikbare_minuten = minuut_van_de_dag - 300
            
            if resterende_minuten <= beschikbare_minuten:
                huidige_tijd = huidige_tijd - resterende_minuten
                resterende_minuten = 0
            else:
                resterende_minuten = resterende_minuten - beschikbare_minuten
                huidige_tijd = huidige_tijd - beschikbare_minuten
                huidige_tijd = huidige_tijd - 360  # van 5:00 naar 23:00

    # fallback als huidige_tijd in het negatieve gaat dus voor startpunt van de simulatie   
    return max(0, huidige_tijd)

def genereer_alle_reserveringen(simulatie_dagen, kansen_voorlooptijd):
    with open('data/simulatie_parameters.json', 'r', encoding='utf-8') as bestand:
        parameters = json.load(bestand)
        
    profielen = parameters['voorlooptijd']['profielen']
    kans_planner = kansen_voorlooptijd[0]
    kans_gemiddeld = kansen_voorlooptijd[1]
    kans_nood = kansen_voorlooptijd[2]
    
    dagen_namen = ['Maandag', 'Dinsdag', 'Woensdag', 'Donderdag', 'Vrijdag']
    alle_reserveringen = []
    
    for dag in range(simulatie_dagen):
        start_van_dag = dag * 1440
        
        # welke dag van de week is het
        index_weekdag = dag % 5
        naam_weekdag = dagen_namen[index_weekdag]

        # per locatie parameters ophalen
        for locatie_naam, data_locatie in parameters['locaties'].items():
            parameters_locatie_dag = data_locatie[naam_weekdag]
            
            verwacht_aantal_orders = parameters_locatie_dag['lambda_orders']
            aantal_orders_vandaag = np.random.poisson(lam=verwacht_aantal_orders)
            
            for _ in range(aantal_orders_vandaag):
                # starttijd bepalen via gmm
                gmm = parameters_locatie_dag['gmm_starttijd']
                gekozen_component = np.random.choice(gmm['aantal_componenten'], p=gmm['gewichten'])
                gemiddelde_starttijd = gmm['gemiddeldes'][gekozen_component]
                standaardafwijking_starttijd = np.sqrt(gmm['varianties'][gekozen_component])
                
                starttijd_op_dag = np.random.normal(gemiddelde_starttijd, standaardafwijking_starttijd)

                # er mag niet negatief of groter dan een dag worden gesampled
                # ideaal gebeurt dit nooit
                # maar als het wel gebeurt opnieuw samplen.
                # een andere optie is het laten doorlopen op vorige dag of volgende dag. maar de verdeling is gefit op de huidige dag en houdt geen rekening met vorige of volgende dag, daarom kies ik toch om te resamplen
                while starttijd_op_dag < 0 or starttijd_op_dag >= 1440.0:
                    starttijd_op_dag = np.random.normal(gemiddelde_starttijd, standaardafwijking_starttijd)
                absolute_starttijd = start_van_dag + starttijd_op_dag
                
                # lengte van een reservatie bepalen
                start_uur = str(int(starttijd_op_dag // 60))

                # genereer parameters heeft alle uren, dagdelen en dagen zelf al correct geplaatst per uur, dus is het enkel nog empirisch van dat uur een duur samplen
                duur_opties = parameters_locatie_dag['empirische_duur_per_uur'][start_uur]
                    
                duur_minuten = np.random.choice(duur_opties)

                # zelfde principe als duur
                kans_sleutel = parameters_locatie_dag['kans_sleutels_per_uur'][start_uur]
                
                sleutels_opgehaald = np.random.binomial(n=1, p=kans_sleutel)
                
                # voorloop tijd en dan dus ook de boekingsdatum bepalen
                # eerst bepalen uit welke groep de reserveerder zit
                # adhv de kansen
                groep = np.random.choice(['planner', 'gemiddeld', 'nood'], p=[kans_planner, kans_gemiddeld, kans_nood])

                # elk heeft zijn eigen uniforme verdeling waaruit gesampled kan worden.
                if groep == 'planner':
                    voorlooptijd = np.random.uniform(profielen['planner']['minimum_minuten'], profielen['planner']['maximum_minuten'])
                elif groep == 'gemiddeld':
                    voorlooptijd = np.random.uniform(profielen['gemiddeld']['minimum_minuten'], profielen['gemiddeld']['maximum_minuten'])
                else:
                    voorlooptijd = np.random.uniform(profielen['nood']['minimum_minuten'], profielen['nood']['maximum_minuten'])

                # opnieuw dit is om nachtboekingen te voorkomen
                boekingsmoment = bereken_boekingsmoment(absolute_starttijd, voorlooptijd)
                
                nieuwe_reservering = {
                    'boekingsmoment': boekingsmoment,
                    'absolute_starttijd': absolute_starttijd,
                    'duur_minuten': duur_minuten,
                    'locatie': locatie_naam,
                    'weekdag': naam_weekdag,
                    'sleutels_opgehaald': sleutels_opgehaald
                }
                alle_reserveringen.append(nieuwe_reservering)
                

    alle_reserveringen_gesorteerd = sorted(alle_reserveringen, key=lambda x: x['boekingsmoment'])
    return alle_reserveringen_gesorteerd