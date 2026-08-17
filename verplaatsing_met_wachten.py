import simpy
import numpy as np

# De L is gewoon voor leesbaarheid
L1 = "Hofstraat_47_Seniotel"
L2 = "Sint-Salvatorstraat_16"
L3 = "Henri_Farmanstraat_30"
L4 = "Neermeerskaai_1A"

# onderstaande reistijden zijn bepaald via google maps, door te kijken naar weekdagen, maximum en minimum en dan een waarde ertussen in, op werkelijke dag (gemeten op een vrijdag middag rond 13:40)
minimale_reistijden_in_minuten = {
    L1: {L1: 0,  L2: 12, L3: 12, L4: 7},
    L2: {L1: 12, L2: 0,  L3: 7,  L4: 10},
    L3: {L1: 14, L2: 6,  L3: 0,  L4: 14},
    L4: {L1: 8,  L2: 10, L3: 16, L4: 0},
}

gemiddelde_reistijden_in_minuten = {
    L1: {L1: 0,  L2: 16, L3: 20, L4: 9},
    L2: {L1: 16, L2: 0,  L3: 9,  L4: 16},
    L3: {L1: 19, L2: 8,  L3: 0,  L4: 21},
    L4: {L1: 11, L2: 16, L3: 25, L4: 0},
}

maximale_reistijden_in_minuten = {
    L1: {L1: 0,  L2: 22, L3: 28, L4: 12},
    L2: {L1: 22, L2: 0,  L3: 12, L4: 22},
    L3: {L1: 24, L2: 11, L3: 0,  L4: 28},
    L4: {L1: 14, L2: 22, L3: 35, L4: 0},
}

class Wagen:
    # elke wagen heeft een uniek identificatienummer en is toegewezen aan een specifieke locatie.
    def __init__(self, identificatienummer_wagen, naam_van_locatie):
        self.identificatienummer = identificatienummer_wagen
        self.locatie_naam = naam_van_locatie
        
        # minuten tellers specifiek apart voor de weibull verdelingen
        # totale levensduur minuten is voor de totale slijtage
        self.totale_levensduur_minuten = 0.0
        self.minuten_banden_lek = 0.0
        self.minuten_sinds_laatste_onderhoud = 0.0
        self.aantal_reparaties = 0
        self.minuten_banden_slijtage = 0.0
        self.minuten_remblokjes_slijtage = 0.0

def initialiseer_wagens(simulatie_omgeving, verdeelsleutel_wagens):
    verzameling_wagens_per_locatie = {}
    lijst_alle_wagens_referentie = []
    teller_wagen_identificatie = 1
    totaal_aantal_wagens=0

    for _,aantal_gekozen_wagens in verdeelsleutel_wagens.items():
        totaal_aantal_wagens += aantal_gekozen_wagens
    
    for naam_van_locatie, aantal_gekozen_wagens in verdeelsleutel_wagens.items():
        # hier is capaciteit totaal aantal wagens omdat deze zich kunnen verplaatsen
        parkeerplaats_wachtrij = simpy.FilterStore(simulatie_omgeving, capacity=totaal_aantal_wagens) 

        # elke locatie heeft een hoeveelheid wagens
        for _ in range(aantal_gekozen_wagens):
            nieuwe_wagen = Wagen(teller_wagen_identificatie, naam_van_locatie)
            parkeerplaats_wachtrij.put(nieuwe_wagen)
            lijst_alle_wagens_referentie.append(nieuwe_wagen)
            teller_wagen_identificatie += 1
            
        verzameling_wagens_per_locatie[naam_van_locatie] = parkeerplaats_wachtrij
        
    return verzameling_wagens_per_locatie, lijst_alle_wagens_referentie

def stuur_naar_garage(simulatie_omgeving, parkeerplaats_queue, specifieke_wagen, reparatie_duur_in_minuten, type_reparatie):
    # wagen heeft een reparatie nodig of preventief onderhoud
    # de wagen mag dan ook niet meer beschikbaar zijn in de filterstore
    # de yield timeout, zorgt dat het niet meer beschikbaar is, pas na een timeout,
    # duur van het onderhoud zal het weer beschikbaar zijn
    yield simulatie_omgeving.timeout(reparatie_duur_in_minuten)
    specifieke_wagen.aantal_reparaties += 1
    
    # Als de reparatie is uitgevoerd ga ik ervanuit dat het perfect is gerepareerd zo goed als nieuw
    if type_reparatie == "banden_lek":
        specifieke_wagen.minuten_banden_lek = 0.0
    elif type_reparatie == "banden_slijtage":
        specifieke_wagen.minuten_banden_slijtage = 0.0
    elif type_reparatie == "remblokjes":
        specifieke_wagen.minuten_remblokjes_slijtage = 0.0
    elif type_reparatie == "preventief":
        specifieke_wagen.minuten_sinds_laatste_onderhoud = 0.0

    # dan kan de wagen weer in de queue worden geplaatst en zal het wachten op een nieuwe event
    yield parkeerplaats_queue.put(specifieke_wagen)

def schat_werkelijke_rijtijd(gereserveerde_duur_in_minuten):
    # de totale duur van een reservatie zou te groot zijn voor en slijtage aantal,
    # daarom schat ik het met een berekende aanname,
    # korte reserveringen zullen tussen de 15% en 75% liggen van rijtijd tov de duur (deze zakt na 8 uur)
    # lange reserveringen tussen de 15% en 40%
    # de grens
    
    # de ondergrens is  a * T met a = 0.15 (15 procent minimum rijtijd).
    ondergrens = 0.15 * gereserveerde_duur_in_minuten
    
    # formule bovengrens: T * (b - c * T)
    # b = 0.75 (bij een korte reservering ligt de bovengrens startend op 75% van de tijd)
    # c = 0.00073
    # ik neem aan dat een reguliere werkshift voor stadswerkers rond de 480 minuten (8uur) duurt
    # de c-waarde zal de maximale rijtijd-fractie vloeiend verlagen van 0.75 naar 0.40 gedurende 480 minuten
    # dan is dus 
    # 0.40 = 0.75 - (c * 480)  =>  c * 480 = 0.35  =>  c = 0.35 / 480 = 0.00073
    fractie_bovengrens = 0.75 - (0.00073 * gereserveerde_duur_in_minuten)
    
    # de maximale bovengrens blijft dan 40% 
    fractie_bovengrens = max(0.40, fractie_bovengrens)
    bovengrens = gereserveerde_duur_in_minuten * fractie_bovengrens    
    
    # uniforme verdeling omdat ik niet de  werkelijke rijminuten ken, dus ik ga ook geen aannames daarover maken
    return np.random.uniform(ondergrens, bovengrens)

def bereken_weibull_faalkans(huidige_levensduur_in_minuten, duur_nieuwe_reservering_in_minuten, vorm_parameter_beta, schaal_parameter_eta):
    exponent_voor_de_reservering = (huidige_levensduur_in_minuten / schaal_parameter_eta) ** vorm_parameter_beta
    exponent_na_de_reservering = ((huidige_levensduur_in_minuten + duur_nieuwe_reservering_in_minuten) / schaal_parameter_eta) ** vorm_parameter_beta
    kans_op_falen = 1.0 - np.exp(exponent_voor_de_reservering - exponent_na_de_reservering)
    return kans_op_falen

def zoek_beste_donor(locatie_in_nood, verzameling_wagens_per_locatie, actuele_reistijden_matrix):
    kandidaten = []
    for potentiele_donor_locatie, parkeerplaats_mogelijke_donor in verzameling_wagens_per_locatie.items():
        # een donor is in principe niet een locatie in nood maar voor alle zekerheid toch checken
        if potentiele_donor_locatie != locatie_in_nood and len(parkeerplaats_mogelijke_donor.items) > 1:
            reistijd = actuele_reistijden_matrix[potentiele_donor_locatie][locatie_in_nood]
            kandidaten.append((reistijd, potentiele_donor_locatie))
            
    if kandidaten:
        kandidaten.sort(key=lambda x: x[0]) # sorteer van kortste naar langste reistijd
        return kandidaten[0] # geeft (kortste_reistijd, donor_locatie) terug
    return None

# dit verplaatst de wagen van de donorlocatie naar locatie in nood
def bereid_locatie_voor(simulatie_omgeving, huidige_reservering, verzameling_wagens_per_locatie, wagens_onderweg_teller):
    locatie_in_nood = huidige_reservering['locatie']
    
    huidig_uur = (huidige_reservering['absolute_starttijd'] % 1440) / 60.0
    if (7 <= huidig_uur < 10) or (16 <= huidig_uur < 19):
        actuele_reistijden_matrix = maximale_reistijden_in_minuten
    elif (huidig_uur >= 22) or (huidig_uur < 6):
        actuele_reistijden_matrix = minimale_reistijden_in_minuten
    else:
        actuele_reistijden_matrix = gemiddelde_reistijden_in_minuten

    beste_donor_info = zoek_beste_donor(locatie_in_nood, verzameling_wagens_per_locatie, actuele_reistijden_matrix)
    if not beste_donor_info:
        return
        
    kortste_reistijd, _ = beste_donor_info
    
    # Checken of we de tijd hebben om auto te brengen met 5 minuten speling
    controle_moment = huidige_reservering['absolute_starttijd'] - kortste_reistijd - 5.0
    wacht_tot_controle = controle_moment - simulatie_omgeving.now
    
    if wacht_tot_controle > 0:
        yield simulatie_omgeving.timeout(wacht_tot_controle)

    parkeerplaats_in_nood = verzameling_wagens_per_locatie[locatie_in_nood]
    wagens_beschikbaar_en_onderweg = len(parkeerplaats_in_nood.items) + wagens_onderweg_teller[locatie_in_nood]

    if wagens_beschikbaar_en_onderweg == 0:
        huidig_uur_nu = (simulatie_omgeving.now % 1440) / 60.0
        if (7 <= huidig_uur_nu < 10) or (16 <= huidig_uur_nu < 19):
            matrix_nu = maximale_reistijden_in_minuten
        elif (huidig_uur_nu >= 22) or (huidig_uur_nu < 6):
            matrix_nu = minimale_reistijden_in_minuten
        else:
            matrix_nu = gemiddelde_reistijden_in_minuten
            
        beste_donor_nu = zoek_beste_donor(locatie_in_nood, verzameling_wagens_per_locatie, matrix_nu)
        
        if beste_donor_nu:
            reistijd_nu, donor_nu = beste_donor_nu
            parkeerplaats_donor = verzameling_wagens_per_locatie[donor_nu]
            
            wagen_om_te_verplaatsen = yield parkeerplaats_donor.get()
            
            wagens_onderweg_teller[locatie_in_nood] += 1
            
            simulatie_omgeving.process(verplaats_wagen(
                simulatie_omgeving, 
                wagen_om_te_verplaatsen, 
                parkeerplaats_in_nood, 
                reistijd_nu,
                locatie_in_nood,         
                wagens_onderweg_teller    
            ))

def verplaats_wagen(simulatie_omgeving, wagen_om_te_verplaatsen, bestemmings_parkeerplaats, reistijd_in_minuten, nieuwe_locatie_naam, wagens_onderweg_teller):
    # tijd van verplaatsing nu is de wagen onbeschikbaar
    yield simulatie_omgeving.timeout(reistijd_in_minuten)
    
    # de locatie aanpassen aan de nieuwe naam
    wagen_om_te_verplaatsen.locatie_naam = nieuwe_locatie_naam

    wagen_om_te_verplaatsen.totale_levensduur_minuten += reistijd_in_minuten
    wagen_om_te_verplaatsen.minuten_sinds_laatste_onderhoud += reistijd_in_minuten
    wagen_om_te_verplaatsen.minuten_banden_lek += reistijd_in_minuten
    wagen_om_te_verplaatsen.minuten_banden_slijtage += reistijd_in_minuten
    wagen_om_te_verplaatsen.minuten_remblokjes_slijtage += reistijd_in_minuten

    # wagen aan de bestemmingslocatie toevoegen
    yield bestemmings_parkeerplaats.put(wagen_om_te_verplaatsen)
    
    wagens_onderweg_teller[nieuwe_locatie_naam] -= 1

def monitor_wagens_tijdens_de_dag(simulatie_omgeving, verzameling_wagens_per_locatie, wagens_onderweg_teller):
    while True:
        # elke 60 minuten kijken of er locaties zijn die nood hebben
        yield simulatie_omgeving.timeout(60.0) 
        
        # huidige uur bepalen van de dag
        huidig_uur = (simulatie_omgeving.now % 1440) / 60.0
        
        # tijdens spits is er maximale reistijden
        if (7 <= huidig_uur < 10) or (16 <= huidig_uur < 19):
            actuele_reistijden_matrix = maximale_reistijden_in_minuten
        # tijdens de nacht is het minimale reistijden
        elif (huidig_uur >= 22) or (huidig_uur < 6):
            actuele_reistijden_matrix = minimale_reistijden_in_minuten
        # tijdens de rest van de dag is het gemiddelde reistijden
        else:
            actuele_reistijden_matrix = gemiddelde_reistijden_in_minuten
        
        # elke locatie wordt bekeken
        for locatie_in_nood, parkeerplaats_in_nood in verzameling_wagens_per_locatie.items():
            
            # als er al wagens onderweg zijn dan hoeft er geen nieuwe wagen te worden gestuurd
            if len(parkeerplaats_in_nood.items) == 0 and len(parkeerplaats_in_nood.get_queue) > wagens_onderweg_teller[locatie_in_nood]:
                
                # de beste donor wordt gezocht adhv de reistijden matrix en de beschikbare wagens
                beste_donor_info = zoek_beste_donor(locatie_in_nood, verzameling_wagens_per_locatie, actuele_reistijden_matrix)
                
                if beste_donor_info:
                    opgezochte_reistijd, donor_locatie_met_overschot = beste_donor_info
                    parkeerplaats_donor = verzameling_wagens_per_locatie[donor_locatie_met_overschot]
                    
                    # vanaf de get is de wagen niet beschikbaar op die locatie
                    wagen_om_te_verplaatsen = yield parkeerplaats_donor.get()
                    
                    wagens_onderweg_teller[locatie_in_nood] += 1
                    
                    # verplaatsen van de wagen naar de locatie in nood, kost tijd
                    simulatie_omgeving.process(verplaats_wagen(
                        simulatie_omgeving, 
                        wagen_om_te_verplaatsen, 
                        parkeerplaats_in_nood, 
                        opgezochte_reistijd,
                        locatie_in_nood,          
                        wagens_onderweg_teller   
                    ))

def voer_reservering_uit(simulatie_omgeving, parkeerplaats_wachtrij, huidige_reservering, lijst_gefaalde_reserveringen, statistieken, geduld_wachttijd_minuten):
    wachttijd_tot_start_reservering = huidige_reservering['absolute_starttijd'] - simulatie_omgeving.now
    if wachttijd_tot_start_reservering > 0:
        yield simulatie_omgeving.timeout(wachttijd_tot_start_reservering)
        
    start_wacht_tijd_moment = simulatie_omgeving.now
    maximaal_geduld_klant_in_minuten = geduld_wachttijd_minuten
    
    
    with parkeerplaats_wachtrij.get() as aanvraag_voor_wagen:
        
        resultaat = yield aanvraag_voor_wagen | simulatie_omgeving.timeout(maximaal_geduld_klant_in_minuten)
        
        if aanvraag_voor_wagen in resultaat:
            gekozen_wagen = aanvraag_voor_wagen.value
            
            if simulatie_omgeving.now > start_wacht_tijd_moment + 0.0001:
                statistieken['succesvol_gewacht'] += 1
            
            if huidige_reservering.get('sleutels_opgehaald') == 0:
                yield simulatie_omgeving.timeout(15.0)
                statistieken['niet_doorgegaan'] += 1
                yield parkeerplaats_wachtrij.put(gekozen_wagen)
                return
                
            yield simulatie_omgeving.timeout(huidige_reservering['duur_minuten'])
            
            effectieve_rijtijd_in_minuten = schat_werkelijke_rijtijd(huidige_reservering['duur_minuten'])
                                
            kans_op_lekke_band = bereken_weibull_faalkans(gekozen_wagen.minuten_banden_lek, effectieve_rijtijd_in_minuten, 1.0, 300000.0)
            kans_op_versleten_banden = bereken_weibull_faalkans(gekozen_wagen.minuten_banden_slijtage, effectieve_rijtijd_in_minuten, 3.5, 90000.0)                
            kans_op_versleten_remblokjes = bereken_weibull_faalkans(gekozen_wagen.minuten_remblokjes_slijtage, effectieve_rijtijd_in_minuten, 2.5, 99960)
                        
            gekozen_wagen.totale_levensduur_minuten += effectieve_rijtijd_in_minuten
            gekozen_wagen.minuten_banden_lek += effectieve_rijtijd_in_minuten
            gekozen_wagen.minuten_sinds_laatste_onderhoud += effectieve_rijtijd_in_minuten
            gekozen_wagen.minuten_banden_slijtage += effectieve_rijtijd_in_minuten
            gekozen_wagen.minuten_remblokjes_slijtage += effectieve_rijtijd_in_minuten
                                
            willekeurige_kans_trekking_banden_lek = np.random.random()
            willekeurige_kans_trekking_banden_slijtage = np.random.random()
            willekeurige_kans_trekking_remblokjes = np.random.random()
            
            if willekeurige_kans_trekking_banden_lek < kans_op_lekke_band:
                simulatie_omgeving.process(stuur_naar_garage(simulatie_omgeving, parkeerplaats_wachtrij, gekozen_wagen, np.random.uniform(120.0, 240.0), "banden_lek"))
            elif willekeurige_kans_trekking_banden_slijtage < kans_op_versleten_banden:
                simulatie_omgeving.process(stuur_naar_garage(simulatie_omgeving, parkeerplaats_wachtrij, gekozen_wagen, np.random.uniform(120.0, 180.0), "banden_slijtage"))
            elif willekeurige_kans_trekking_remblokjes < kans_op_versleten_remblokjes:
                simulatie_omgeving.process(stuur_naar_garage(simulatie_omgeving, parkeerplaats_wachtrij, gekozen_wagen, np.random.uniform(180.0, 300.0), "remblokjes"))
            elif gekozen_wagen.minuten_sinds_laatste_onderhoud >= 6000.0:
                if np.random.random() < 0.75:
                    simulatie_omgeving.process(stuur_naar_garage(simulatie_omgeving, parkeerplaats_wachtrij, gekozen_wagen, np.random.uniform(60.0, 90.0), "preventief"))
                else:
                    simulatie_omgeving.process(stuur_naar_garage(simulatie_omgeving, parkeerplaats_wachtrij, gekozen_wagen, np.random.uniform(180.0, 240.0), "preventief"))
            else:
                yield parkeerplaats_wachtrij.put(gekozen_wagen)
                
        else:
            lijst_gefaalde_reserveringen.append(1)

def start_simulatie(simulatie_omgeving, verzameling_wagens_per_locatie, lijst_met_reserveringen, lijst_gefaalde_reserveringen, statistieken, geduld_wachttijd_minuten):
    # per locatie een wagen die onderweg is
    wagens_onderweg_teller = {L1: 0, L2: 0, L3: 0, L4: 0}
    
    simulatie_omgeving.process(monitor_wagens_tijdens_de_dag(simulatie_omgeving, verzameling_wagens_per_locatie, wagens_onderweg_teller))
    
    for huidige_reservering in lijst_met_reserveringen:
        tijd_tot_boekingsmoment = huidige_reservering['boekingsmoment'] - simulatie_omgeving.now
        if tijd_tot_boekingsmoment > 0:
            yield simulatie_omgeving.timeout(tijd_tot_boekingsmoment)
            
        # paralel proces die kijkt of er een donor wagen kan worden gestuurd naar de locatie op voorhand
        simulatie_omgeving.process(bereid_locatie_voor(
            simulatie_omgeving, 
            huidige_reservering, 
            verzameling_wagens_per_locatie,
            wagens_onderweg_teller
        ))
            
        simulatie_omgeving.process(voer_reservering_uit(
            simulatie_omgeving, 
            verzameling_wagens_per_locatie[huidige_reservering['locatie']], 
            huidige_reservering, 
            lijst_gefaalde_reserveringen, 
            statistieken, 
            geduld_wachttijd_minuten
        ))