import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os

def laad_simulatie_data(bestandspad):
    try:
        data = pd.read_csv(bestandspad, delimiter=';')
        return data
    except FileNotFoundError:
        print(f"het bestand {bestandspad} is niet gevonden. run eerst simulatie.py.")
        return None

def genereer_staafgrafieken_per_vloot_apart(data, metriek_gemiddelde, metriek_ondergrens, metriek_bovengrens, y_as_label, bestands_prefix, y_as_vanaf_nul=True):
    vlootgroottes = sorted(data['totale_vloot_grootte'].unique(), reverse=True)
    scenario_namen = data['scenario_beschrijving'].unique()
    
    unieke_combinaties = data[['algoritme_naam', 'wachttijd_klant_in_minuten']].drop_duplicates().values
    breedte_staaf = 0.8 / len(unieke_combinaties)
    x_posities = np.arange(len(scenario_namen))
    
    for vlootgrootte in vlootgroottes:
        sub_data = data[data['totale_vloot_grootte'] == vlootgrootte]
        
        figuur = plt.figure(figsize=(16, 8))
        as_grafiek = plt.gca()
        
        minimale_y_waarde = float('inf')
        maximale_y_waarde = 0.0
        
        for index, (algoritme, wachttijd) in enumerate(unieke_combinaties):
            algoritme_data = sub_data[(sub_data['algoritme_naam'] == algoritme) & (sub_data['wachttijd_klant_in_minuten'] == wachttijd)]
            algoritme_data = algoritme_data.set_index('scenario_beschrijving').reindex(scenario_namen).reset_index()
            
            if algoritme_data.empty or algoritme_data[metriek_gemiddelde].isna().all():
                continue
                
            gemiddeldes = algoritme_data[metriek_gemiddelde].values
            
            
            if metriek_ondergrens is not None and metriek_bovengrens is not None:
                ondergrens = algoritme_data[metriek_ondergrens].values
                bovengrens = algoritme_data[metriek_bovengrens].values
                
                ondergrens_gecorrigeerd = np.maximum(0, ondergrens)
                
                huidig_minimum = np.nanmin(ondergrens_gecorrigeerd)
                huidig_maximum = np.nanmax(bovengrens)
                
                foutmarge_onder = gemiddeldes - ondergrens_gecorrigeerd
                foutmarge_boven = bovengrens - gemiddeldes
                foutmarge = [foutmarge_onder, foutmarge_boven]
            else:
                huidig_minimum = np.nanmin(gemiddeldes)
                huidig_maximum = np.nanmax(gemiddeldes)
                foutmarge = None
                
            if huidig_minimum < minimale_y_waarde:
                minimale_y_waarde = huidig_minimum
            if huidig_maximum > maximale_y_waarde:
                maximale_y_waarde = huidig_maximum
            
            offset = (index - len(unieke_combinaties)/2) * breedte_staaf + breedte_staaf/2
            label_naam = f"{algoritme} ({wachttijd}m)"
            
            as_grafiek.bar(
                x_posities + offset, 
                gemiddeldes, 
                breedte_staaf, 
                yerr=foutmarge, 
                label=label_naam,
                capsize=3,
                alpha=0.8
            )

        if not y_as_vanaf_nul and minimale_y_waarde != float('inf'):
            verschil_min_max = maximale_y_waarde - minimale_y_waarde
            marge = verschil_min_max * 0.15
            
            if marge == 0:
                marge = minimale_y_waarde * 0.05
                
            ondergrens_y_as = max(0, minimale_y_waarde - marge)
            bovengrens_y_as = maximale_y_waarde + marge
            as_grafiek.set_ylim(bottom=ondergrens_y_as, top=bovengrens_y_as)
        else:
            as_grafiek.set_ylim(bottom=0)

        as_grafiek.set_ylabel(y_as_label)
        as_grafiek.set_title(f'{y_as_label} per Scenario (Vlootgrootte apart: {vlootgrootte})')
        as_grafiek.set_xticks(x_posities)
        as_grafiek.set_xticklabels([naam.split(':')[0] for naam in scenario_namen], rotation=45, ha="right")
        as_grafiek.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        
        plt.tight_layout()
        bestandsnaam = f'resultaten/{bestands_prefix}_apart_vloot_{vlootgrootte}.png'
        plt.savefig(bestandsnaam)
        plt.close(figuur)
        print(f"opgeslagen aparte analyse: {bestandsnaam}")

def genereer_elbow_curves_per_scenario(data, metriek_gemiddelde, y_as_label, mapnaam):
    pad_naar_map = os.path.join('resultaten', mapnaam)
    os.makedirs(pad_naar_map, exist_ok=True)
    
    scenarios = data['scenario_beschrijving'].unique()
    unieke_combinaties = data[['algoritme_naam', 'wachttijd_klant_in_minuten']].drop_duplicates().values
    
    for scenario in scenarios:
        figuur = plt.figure(figsize=(14, 8))
        as_grafiek = plt.gca()
        
        sub_data = data[data['scenario_beschrijving'] == scenario]
        
        for algoritme, wachttijd in unieke_combinaties:
            lijn_data = sub_data[(sub_data['algoritme_naam'] == algoritme) & (sub_data['wachttijd_klant_in_minuten'] == wachttijd)]
            
            lijn_data = lijn_data.sort_values(by='totale_vloot_grootte', ascending=False)
            
            if not lijn_data.empty:
                label_naam = f"{algoritme} ({wachttijd}m)"

                as_grafiek.plot(
                    lijn_data['totale_vloot_grootte'].astype(str), 
                    lijn_data[metriek_gemiddelde],
                    marker='o',
                    linewidth=2.5,
                    label=label_naam
                )

        as_grafiek.set_xlabel('totale vlootgrootte (aantal auto\'s)')
        as_grafiek.set_ylabel(y_as_label)
        as_grafiek.set_title(f'Elbow Curve: {y_as_label}\nScenario: {scenario}')
        as_grafiek.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        as_grafiek.grid(True, linestyle='--', alpha=0.6)
        
        plt.tight_layout()
        
        veilig_scenario = "".join([c for c in scenario if c.isalnum() or c==' ']).rstrip().replace(" ", "_").lower()
        bestandsnaam = os.path.join(pad_naar_map, f"elbow_{veilig_scenario}.png")
        plt.savefig(bestandsnaam)
        plt.close(figuur)
        print(f"opgeslagen elbow curve: {bestandsnaam}")

bestand_resultaten = 'resultaten/simulatie_resultaten.csv'
simulatie_data = laad_simulatie_data(bestand_resultaten)

os.makedirs('resultaten', exist_ok=True)

if simulatie_data is not None:
    
    print("\nmaken van grafieken voor gemiste ritten")
    genereer_staafgrafieken_per_vloot_apart(
        data=simulatie_data, 
        metriek_gemiddelde='gemiddeld_gefaalde_reserveringen', 
        metriek_ondergrens='betrouwbaarheidsinterval_onder_gefaald', 
        metriek_bovengrens='betrouwbaarheidsinterval_boven_gefaald', 
        y_as_label='gemiddeld aantal gefaalde reserveringen', 
        bestands_prefix='gemist',
        y_as_vanaf_nul=True
    )
    genereer_elbow_curves_per_scenario(
        data=simulatie_data, 
        metriek_gemiddelde='gemiddeld_gefaalde_reserveringen', 
        y_as_label='gemiddeld aantal gefaalde reserveringen', 
        mapnaam='elbow_gefaalde_reserveringen'
    )
    
    print("\nmaken van grafieken voor reparaties (defecten)")
    genereer_staafgrafieken_per_vloot_apart(
        data=simulatie_data, 
        metriek_gemiddelde='gemiddeld_aantal_reparaties_per_wagen', 
        metriek_ondergrens='betrouwbaarheidsinterval_onder_reparaties', 
        metriek_bovengrens='betrouwbaarheidsinterval_boven_reparaties', 
        y_as_label='gemiddeld aantal defecten per wagen', 
        bestands_prefix='reparaties',
        y_as_vanaf_nul=False
    )
    genereer_elbow_curves_per_scenario(
        data=simulatie_data, 
        metriek_gemiddelde='gemiddeld_aantal_reparaties_per_wagen', 
        y_as_label='gemiddeld aantal defecten per wagen', 
        mapnaam='elbow_reparaties'
    )

    print("\nmaken van grafieken voor mediaan reparaties")
    genereer_staafgrafieken_per_vloot_apart(
        data=simulatie_data, 
        metriek_gemiddelde='mediaan_aantal_reparaties_per_wagen', 
        metriek_ondergrens=None, 
        metriek_bovengrens=None, 
        y_as_label='mediaan aantal defecten per wagen', 
        bestands_prefix='mediaan_reparaties',
        y_as_vanaf_nul=True
    )
    genereer_elbow_curves_per_scenario(
        data=simulatie_data, 
        metriek_gemiddelde='mediaan_aantal_reparaties_per_wagen', 
        y_as_label='mediaan aantal defecten per wagen', 
        mapnaam='elbow_mediaan_reparaties'
    )

    print("\nmaken van grafieken voor spreiding in het wagenvloot (spreiding slijtage)")
    # hoge spreiding betekent dat sommige wagens veel gereden worden terwijl andere stilstaan
    # lage spreiding betekent dat de meeste wagens in de vloot ongeveer evenveel minuten hebben gereden
    genereer_staafgrafieken_per_vloot_apart(
        data=simulatie_data, 
        metriek_gemiddelde='standaardafwijking_slijtage', 
        metriek_ondergrens=None, 
        metriek_bovengrens=None, 
        y_as_label='spreiding in wagenslijtage', 
        bestands_prefix='onbalans_slijtage',
        y_as_vanaf_nul=True
    )
    genereer_elbow_curves_per_scenario(
        data=simulatie_data, 
        metriek_gemiddelde='standaardafwijking_slijtage', 
        y_as_label='spreiding in wagenslijtage', 
        mapnaam='elbow_onbalans_slijtage'
    )
    
    print("\nmaken van grafieken voor slijtage (gemiddelde rijuren)")
    genereer_staafgrafieken_per_vloot_apart(
        data=simulatie_data, 
        metriek_gemiddelde='gemiddelde_slijtage_per_wagen_in_minuten', 
        metriek_ondergrens='betrouwbaarheidsinterval_onder_slijtage', 
        metriek_bovengrens='betrouwbaarheidsinterval_boven_slijtage', 
        y_as_label='gemiddelde slijtage per wagen (minuten)', 
        bestands_prefix='slijtage',
        y_as_vanaf_nul=False
    )
    genereer_elbow_curves_per_scenario(
        data=simulatie_data, 
        metriek_gemiddelde='gemiddelde_slijtage_per_wagen_in_minuten', 
        y_as_label='gemiddelde slijtage per wagen (minuten)', 
        mapnaam='elbow_slijtage'
    )
    
    print("\nmaken van grafieken voor reserveringen niet doorgegaan")

    # moet normaal constant zijn dit zijn de sleutels niet opgepikt
    genereer_staafgrafieken_per_vloot_apart(
        data=simulatie_data, 
        metriek_gemiddelde='gemiddeld_aantal_reserveringen_niet_doorgegaan', 
        metriek_ondergrens='betrouwbaarheidsinterval_onder_niet_doorgegaan', 
        metriek_bovengrens='betrouwbaarheidsinterval_boven_niet_doorgegaan', 
        y_as_label='gemiddeld reserveringen niet doorgegaan', 
        bestands_prefix='niet_doorgegaan',
        y_as_vanaf_nul=True
    )
    genereer_elbow_curves_per_scenario(
        data=simulatie_data, 
        metriek_gemiddelde='gemiddeld_aantal_reserveringen_niet_doorgegaan', 
        y_as_label='gemiddeld reserveringen niet doorgegaan', 
        mapnaam='elbow_niet_doorgegaan'
    )

    print("\nmaken van grafieken voor succesvol gewacht")
    genereer_staafgrafieken_per_vloot_apart(
        data=simulatie_data, 
        metriek_gemiddelde='gemiddeld_aantal_klanten_succesvol_gewacht', 
        metriek_ondergrens='betrouwbaarheidsinterval_onder_succesvol_gewacht', 
        metriek_bovengrens='betrouwbaarheidsinterval_boven_succesvol_gewacht', 
        y_as_label='gemiddeld aantal keer succesvol gewacht', 
        bestands_prefix='succesvol_gewacht',
        y_as_vanaf_nul=True
    )
    genereer_elbow_curves_per_scenario(
        data=simulatie_data, 
        metriek_gemiddelde='gemiddeld_aantal_klanten_succesvol_gewacht', 
        y_as_label='gemiddeld aantal keer succesvol gewacht', 
        mapnaam='elbow_succesvol_gewacht'
    )
    