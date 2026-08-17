import simpy
import json
import numpy as np
import csv
import os

import datagenerator
import first_come_first_serve
import first_come_first_serve_met_wachten
import verplaatsing_met_wachten
import minste_slijtage_eerst

with open('data/simulatie_parameters.json', 'r', encoding='utf-8') as bestand:
    parameters = json.load(bestand)

def bereken_proportionele_verdeelsleutel(totaal_aantal_wagens):
    # proporties zijn bepaald in eerste analyse data (per locatie de wagens nodig = aantal reserveringen op die locatie / totaal aantal reservaties) met afronding tot 4 cijfers na de komma
    proporties = {
        "Neermeerskaai_1A": 0.0820,
        "Henri_Farmanstraat_30": 0.1597,
        "Hofstraat_47_Seniotel": 0.4455,
        "Sint-Salvatorstraat_16": 0.3128
    }
    
    verdeelsleutel = {}
    resterende_wagens = totaal_aantal_wagens

    # verdelen van de wagens    
    for locatie, proportie in proporties.items():
        toegewezen_wagens = int(round(proportie * totaal_aantal_wagens))
        verdeelsleutel[locatie] = toegewezen_wagens
        resterende_wagens -= toegewezen_wagens

    # stel dat er een wagen over is dan wordt deze gewoon toegewezen aan drukste locatie
    if resterende_wagens != 0:
        drukste_locatie = "Hofstraat_47_Seniotel"
        verdeelsleutel[drukste_locatie] = verdeelsleutel[drukste_locatie] + resterende_wagens
        
    return verdeelsleutel

# dit is 1 simulatierun
def voer_enkele_simulatie_run_uit(gekozen_algoritme_module, totaal_aantal_wagens, aantal_simulatie_dagen, kansen_voorlooptijd, geduld_wachttijd_minuten):
    lijst_met_reserveringen = datagenerator.genereer_alle_reserveringen(aantal_simulatie_dagen, kansen_voorlooptijd)

    # unieke simpy omgeving maken    
    simulatie_omgeving = simpy.Environment()
    
    lijst_gefaalde_reserveringen = [] 
    statistieken = {
        'niet_doorgegaan_en_vrijgegeven': 0, 
        'succesvol_gewacht': 0
    }
    
    verdeelsleutel_wagens = bereken_proportionele_verdeelsleutel(totaal_aantal_wagens)

    # het aantal wagens moet binnen de omgeving worden gemaakt
    wagen_locatie_verzamelingen, alle_wagens_referentie = gekozen_algoritme_module.initialiseer_wagens(simulatie_omgeving, verdeelsleutel_wagens)

    # process binnen simpy zal de functie starten tot de eerste yield, daarna wordt de simulatie gestart met run() en zal de functie verder gaan tot de volgende yield
    simulatie_omgeving.process(gekozen_algoritme_module.start_simulatie(
        simulatie_omgeving, 
        wagen_locatie_verzamelingen, 
        lijst_met_reserveringen, 
        lijst_gefaalde_reserveringen, 
        statistieken, 
        geduld_wachttijd_minuten
    ))
    
    # run zal tijd tot eerste event laten uitvoeren, en zo verder tot eindtijd dat is aantal dagen *1440 minuten -- lengte van een dag
    simulatie_omgeving.run(until=aantal_simulatie_dagen * 1440)
    # nu is simulatie klaar
    
    totale_slijtage_vloot_in_minuten = 0
    totaal_aantal_reparaties_vloot = 0

    for wagen in alle_wagens_referentie:
        totale_slijtage_vloot_in_minuten += wagen.totale_levensduur_minuten
        totaal_aantal_reparaties_vloot += wagen.aantal_reparaties
    
    gemiddelde_slijtage_per_wagen_in_minuten = totale_slijtage_vloot_in_minuten / len(alle_wagens_referentie) 
    gemiddelde_reparaties_per_wagen = totaal_aantal_reparaties_vloot / len(alle_wagens_referentie)
    
    # simpele optelling uit de lijst van gefaalde reserveringen
    totaal_gefaalde_reserveringen = sum(lijst_gefaalde_reserveringen)
    
    return (
        totaal_gefaalde_reserveringen, 
        gemiddelde_slijtage_per_wagen_in_minuten, 
        gemiddelde_reparaties_per_wagen, 
        statistieken['niet_doorgegaan_en_vrijgegeven'], 
        statistieken['succesvol_gewacht']
    )

def simuleer_test_combinatie(gekozen_algoritme_module, naam_van_algoritme, totaal_aantal_wagens, aantal_simulatie_dagen, kansen_voorlooptijd, wachttijd_minuten, maximaal_toegestane_foutmarge=1.0):
    # blijven simulaties lopen
    print(f"starten simulatie met algoritme: {naam_van_algoritme} (klant wachttijd: {wachttijd_minuten}m, maximale variatie in gefaalde reserveringen: {maximaal_toegestane_foutmarge})...")
    
    # voor alle runs
    resultaten_gefaalde_reserveringen = []
    resultaten_slijtage = []
    resultaten_reparaties = []
    resultaten_niet_doorgegaan = []
    resultaten_gewacht = []

    # starten met 100 runs
    for _ in range(100):
        gefaald, slijtage, reparaties, niet_doorgegaan_vrijgegeven, succesvol_gewacht = voer_enkele_simulatie_run_uit(
            gekozen_algoritme_module, 
            totaal_aantal_wagens, 
            aantal_simulatie_dagen, 
            kansen_voorlooptijd, 
            wachttijd_minuten
        )
        resultaten_gefaalde_reserveringen.append(gefaald)
        resultaten_slijtage.append(slijtage)
        resultaten_reparaties.append(reparaties)
        resultaten_niet_doorgegaan.append(niet_doorgegaan_vrijgegeven)
        resultaten_gewacht.append(succesvol_gewacht)

        if len(resultaten_gefaalde_reserveringen) % 20 == 0:
            print(f"run: {len(resultaten_gefaalde_reserveringen)}")
        
    aantal_uitgevoerde_runs = 100
    
    # ddof=1 is voor een steekproef
    standaardafwijking_gefaald = np.std(resultaten_gefaalde_reserveringen, ddof=1)
    
    # standaardfout (standaardafwijking / wortel n)
    huidige_standaardfout = standaardafwijking_gefaald / np.sqrt(aantal_uitgevoerde_runs)
    
    # zolang dit te groot is (boven de toegestane foutmarge) blijven runs uitvoeren
    while huidige_standaardfout > maximaal_toegestane_foutmarge:
        gefaald, slijtage, reparaties, niet_doorgegaan_vrijgegeven, succesvol_gewacht = voer_enkele_simulatie_run_uit(
            gekozen_algoritme_module, 
            totaal_aantal_wagens, 
            aantal_simulatie_dagen, 
            kansen_voorlooptijd, 
            wachttijd_minuten
        )
        resultaten_gefaalde_reserveringen.append(gefaald)
        resultaten_slijtage.append(slijtage)
        resultaten_reparaties.append(reparaties)
        resultaten_niet_doorgegaan.append(niet_doorgegaan_vrijgegeven)
        resultaten_gewacht.append(succesvol_gewacht)
        
        aantal_uitgevoerde_runs += 1
        
        standaardafwijking_gefaald = np.std(resultaten_gefaalde_reserveringen, ddof=1)
        huidige_standaardfout = standaardafwijking_gefaald / np.sqrt(aantal_uitgevoerde_runs)
        
        if aantal_uitgevoerde_runs % 20 == 0:
            print(f"extra run {aantal_uitgevoerde_runs}: onzekerheid = {huidige_standaardfout:.4f}")
            
    return (
        resultaten_gefaalde_reserveringen, 
        resultaten_slijtage, 
        resultaten_reparaties, 
        resultaten_niet_doorgegaan, 
        resultaten_gewacht, 
        aantal_uitgevoerde_runs
    )

if __name__ == "__main__":
    # 1 jaar = 52 weken *5 dagen
    aantal_simulatie_dagen = 52 * 5  
    
    mapnaam_resultaten = 'resultaten'
    os.makedirs(mapnaam_resultaten, exist_ok=True)
    
    bestandspad_csv = os.path.join(mapnaam_resultaten, 'simulatie_resultaten.csv')

    # openen van de opgeslagen resultaten,
    # bekjken welke er al uitgevoerd zijn
    combinaties_al_uitgevoerd = set()
    if os.path.isfile(bestandspad_csv):
        with open(bestandspad_csv, 'r', encoding='utf-8') as csv_bestand:
            lezer = csv.reader(csv_bestand, delimiter=';')
            next(lezer,None)  # header overslaan, None voor het geval dat het bestand leeg is
            for rij in lezer:  
                # kolom 0: algoritme_naam
                # kolom 1: wachttijd_klant_in_minuten een algoritme (als het toepasselijk is wacht bijvoorbeeld 10 min op terugkomende wagens)
                # kolom 2: totale_vloot_grootte
                # kolom 3: scenario_beschrijving

                combo = (rij[0], float(rij[1]), int(rij[2]), rij[3])
                combinaties_al_uitgevoerd.add(combo)

    bestand_bestaat_al = os.path.isfile(bestandspad_csv)

    with open(bestandspad_csv, 'a', newline='', encoding='utf-8') as csv_bestand:
        schrijver = csv.writer(csv_bestand, delimiter=';')
        if not bestand_bestaat_al:
            schrijver.writerow([
                'algoritme_naam', 
                'wachttijd_klant_in_minuten', 
                'totale_vloot_grootte', 
                'scenario_beschrijving', 
                'totaal_aantal_runs', 
                'gemiddeld_gefaalde_reserveringen', 
                'standaardafwijking_gefaald', 
                'betrouwbaarheidsinterval_onder_gefaald', 
                'betrouwbaarheidsinterval_boven_gefaald',
                'gemiddelde_slijtage_per_wagen_in_minuten', 
                'standaardafwijking_slijtage', 
                'betrouwbaarheidsinterval_onder_slijtage', 
                'betrouwbaarheidsinterval_boven_slijtage',
                'gemiddeld_aantal_reparaties_per_wagen', 
                'standaardafwijking_reparaties', 
                'betrouwbaarheidsinterval_onder_reparaties', 
                'betrouwbaarheidsinterval_boven_reparaties',
                'gemiddeld_aantal_reserveringen_niet_doorgegaan', 
                'standaardafwijking_niet_doorgegaan', 
                'betrouwbaarheidsinterval_onder_niet_doorgegaan', 
                'betrouwbaarheidsinterval_boven_niet_doorgegaan',
                'gemiddeld_aantal_klanten_succesvol_gewacht', 
                'standaardafwijking_succesvol_gewacht', 
                'betrouwbaarheidsinterval_onder_succesvol_gewacht', 
                'betrouwbaarheidsinterval_boven_succesvol_gewacht'
            ])

    
    algoritmen_om_te_testen = [
        ("fcfs_strikt", first_come_first_serve),
        ("fcfs_wachten", first_come_first_serve_met_wachten),
        ("verplaatsing_met_wachten", verplaatsing_met_wachten),
        ("minste_slijtage_eerst", minste_slijtage_eerst)
    ]

    mogelijke_klant_wachttijden = [10.0, 15.0, 20.0, 30.0]

    vloot_groottes_om_te_testen = [129, 120, 110, 109, 108, 107, 106, 105, 104, 103, 102, 101, 100]

    for naam_van_algoritme, gekozen_algoritme_module in algoritmen_om_te_testen:
        
        if naam_van_algoritme in ["fcfs_wachten", "verplaatsing_met_wachten", "minste_slijtage_eerst"]: 
            wachttijden_om_te_testen = mogelijke_klant_wachttijden
        else:
            wachttijden_om_te_testen = [0.0] 
        
        for wachttijd_minuten in wachttijden_om_te_testen:
            
            for test_aantal_wagens in vloot_groottes_om_te_testen: 

                # een mix van verschillende voorlooptijden. Vooral om te zien of er een effect is van de voorlooptijd op het aantal gefaalde reserveringen
                verschillende_scenarios = [
                    {"naam": "scenario 1: zeer veel planners (90 procent)", "kansen": [0.90, 0.08, 0.02]},
                    {"naam": "scenario 2: veel planners (80 procent)", "kansen": [0.80, 0.15, 0.05]},
                    {"naam": "scenario 3: gebalanceerd (30 procent / 50 procent / 20 procent)", "kansen": [0.30, 0.50, 0.20]},
                    {"naam": "scenario 4: standaard mix", "kansen": [0.15, 0.65, 0.20]},
                    {"naam": "scenario 5: veel last-minute boekers (60 procent)", "kansen": [0.10, 0.30, 0.60]},
                    {"naam": "scenario 6: zeer veel noodgevallen (80 procent)", "kansen": [0.05, 0.15, 0.80]}
                ]
                
                for scenario in verschillende_scenarios:
                    huidige_combinatie = (naam_van_algoritme, float(wachttijd_minuten), int(test_aantal_wagens), scenario['naam'])
                    if huidige_combinatie in combinaties_al_uitgevoerd:
                        print(f"overgeslagen: {scenario['naam']}, vloot: {test_aantal_wagens}, algoritme: {naam_van_algoritme}, wachttijd: {wachttijd_minuten}m")
                        continue

                    print("\n")
                    print(f"test: {scenario['naam']}, vlootgrootte: {test_aantal_wagens}, algoritme: {naam_van_algoritme}, ingestelde wachttijd: {wachttijd_minuten}m")
                    
                    res_gefaald, res_slijtage, res_reparaties, res_niet_doorgegaan, res_gewacht, totaal_uitgevoerde_runs = simuleer_test_combinatie(
                        gekozen_algoritme_module,
                        naam_van_algoritme,
                        test_aantal_wagens, 
                        aantal_simulatie_dagen, 
                        scenario['kansen'],
                        wachttijd_minuten,
                        maximaal_toegestane_foutmarge=1.0
                    )
                    
                    gemiddelde_gefaald = float(np.mean(res_gefaald))
                    standaardafwijking_gefaald = float(np.std(res_gefaald, ddof=1))
                    # ik heb gekozen voor z=0,025 dus betrouwbaarheidsinterval van 95%
                    foutmarge_gefaald = 1.96 * (standaardafwijking_gefaald / np.sqrt(totaal_uitgevoerde_runs))
                    
                    gemiddelde_slijtage = float(np.mean(res_slijtage))
                    standaardafwijking_slijtage = float(np.std(res_slijtage, ddof=1))
                    foutmarge_slijtage = 1.96 * (standaardafwijking_slijtage / np.sqrt(totaal_uitgevoerde_runs))
                    
                    gemiddelde_reparaties = float(np.mean(res_reparaties))
                    standaardafwijking_reparaties = float(np.std(res_reparaties, ddof=1))
                    foutmarge_reparaties = 1.96 * (standaardafwijking_reparaties / np.sqrt(totaal_uitgevoerde_runs))
                    
                    gemiddelde_niet_doorgegaan = float(np.mean(res_niet_doorgegaan))
                    standaardafwijking_niet_doorgegaan = float(np.std(res_niet_doorgegaan, ddof=1))
                    foutmarge_niet_doorgegaan = 1.96 * (standaardafwijking_niet_doorgegaan / np.sqrt(totaal_uitgevoerde_runs))
                    
                    gemiddelde_gewacht = float(np.mean(res_gewacht))
                    standaardafwijking_gewacht = float(np.std(res_gewacht, ddof=1))
                    foutmarge_gewacht = 1.96 * (standaardafwijking_gewacht / np.sqrt(totaal_uitgevoerde_runs))
                    
                    print(f"gemiddeld aantal gefaalde reserveringen: {gemiddelde_gefaald:.2f}")
                    print(f"gemiddeld reserveringen niet doorgegaan (door sleutels niet opgepikt): {gemiddelde_niet_doorgegaan:.2f}")
                    print(f"gemiddeld aantal klanten gewacht: {gemiddelde_gewacht:.2f}")
                    
                    with open(bestandspad_csv, 'a', newline='', encoding='utf-8') as csv_bestand:
                        schrijver = csv.writer(csv_bestand, delimiter=';')
                        schrijver.writerow([
                            naam_van_algoritme,
                            wachttijd_minuten,
                            test_aantal_wagens, 
                            scenario['naam'], 
                            totaal_uitgevoerde_runs, 
                            
                            round(gemiddelde_gefaald, 4), 
                            round(standaardafwijking_gefaald, 4), 
                            round(max(0.0, gemiddelde_gefaald - foutmarge_gefaald), 4), 
                            round(gemiddelde_gefaald + foutmarge_gefaald, 4),
                            
                            round(gemiddelde_slijtage, 4),
                            round(standaardafwijking_slijtage, 4),
                            round(max(0.0, gemiddelde_slijtage - foutmarge_slijtage), 4),
                            round(gemiddelde_slijtage + foutmarge_slijtage, 4),
                            
                            round(gemiddelde_reparaties, 4),
                            round(standaardafwijking_reparaties, 4),
                            round(max(0.0, gemiddelde_reparaties - foutmarge_reparaties), 4),
                            round(gemiddelde_reparaties + foutmarge_reparaties, 4),
                            
                            round(gemiddelde_niet_doorgegaan, 4),
                            round(standaardafwijking_niet_doorgegaan, 4),
                            round(max(0.0, gemiddelde_niet_doorgegaan - foutmarge_niet_doorgegaan), 4),
                            round(gemiddelde_niet_doorgegaan + foutmarge_niet_doorgegaan, 4),
                            
                            round(gemiddelde_gewacht, 4),
                            round(standaardafwijking_gewacht, 4),
                            round(max(0.0, gemiddelde_gewacht - foutmarge_gewacht), 4),
                            round(gemiddelde_gewacht + foutmarge_gewacht, 4)
                        ])