import simpy
import numpy as np

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
    
    for locatie_naam, aantal_gekozen_wagens in verdeelsleutel_wagens.items():
        # de filterstore is als een queue maar met een specifieke algoritme,
        # maar altijd op basis van first come first serve
        parkeerplaats_queue = simpy.FilterStore(simulatie_omgeving, capacity=aantal_gekozen_wagens)

        # elke locatie heeft een hoeveelheid wagens
        for _ in range(aantal_gekozen_wagens):
            nieuwe_wagen = Wagen(teller_wagen_identificatie, locatie_naam)
            
            parkeerplaats_queue.put(nieuwe_wagen)
            
            lijst_alle_wagens_referentie.append(nieuwe_wagen)
            teller_wagen_identificatie += 1

        # de verzameling wagens per locatie en een lijst met referenties van alle wagens teruggeven. 
        # lijst per locatie is er een eigen filterstore queue
        verzameling_wagens_per_locatie[locatie_naam] = parkeerplaats_queue
        
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
    # Weibull-verdeling is een verdeling om te bepalen hoe groot de kans is dat een mechanisch onderdeel faalt als het ouder wordt (of hier meer mee wordt gereden), er zijn twee parameters: 
    # de beta(vorm_parameter_beta) en eta (schaal_parameter_eta),
    # ik heb dat zo genoemd, want beta bepaalt hoe de faalkans toeneemt over tijd > 1 wordt gebruikt voor slijtage
    # en eta geeft de levensduur aan
   
    # de formule voor conditionele faalkans (kans op falen tijdens interval dt, gegeven overleving tot tijdstip t):
    # P(falen) = 1 - exp( (t / eta)^beta - ((t + dt) / eta)^beta )
    exponent_voor_de_reservering = (huidige_levensduur_in_minuten / schaal_parameter_eta) ** vorm_parameter_beta
    exponent_na_de_reservering = ((huidige_levensduur_in_minuten + duur_nieuwe_reservering_in_minuten) / schaal_parameter_eta) ** vorm_parameter_beta

    kans_op_falen = 1.0 - np.exp(exponent_voor_de_reservering - exponent_na_de_reservering)
    # als veiligheid omdat er 
    return kans_op_falen

def voer_reservering_uit(simulatie_omgeving, parkeerplaats_queue, huidige_reservering, lijst_gefaalde_reserveringen, statistieken, geduld_wachttijd_minuten):
    # via fcfs, als er geen wagen beschikbaar is dan faalt het maar

    # wachten tot starttijd begint
    wachttijd_tot_start_reservering = huidige_reservering['absolute_starttijd'] - simulatie_omgeving.now
    if wachttijd_tot_start_reservering > 0:
        yield simulatie_omgeving.timeout(wachttijd_tot_start_reservering)

    # geen persoonwagens beschikbaar, dan kan de reservatie niet worden uitgevoerd        
    if len(parkeerplaats_queue.items) == 0:
        lijst_gefaalde_reserveringen.append(1)
        return
        
    # er is een wagen, neem de eerste beschikbare wagen uit de parkeerplaats, adhv FilterStore
    gekozen_wagen = yield parkeerplaats_queue.get()
    
    # Bij fcfs zonder wachten blijft de auto onbeschikbaar als de reserveerder
    # niet opdaagt
    if huidige_reservering.get('sleutels_opgehaald') == 0:
        # wagen is niet beschikbaar maar rijd ook niet, dus return 
        yield simulatie_omgeving.timeout(huidige_reservering['duur_minuten'])
        statistieken['niet_doorgegaan'] += 1
        yield parkeerplaats_queue.put(gekozen_wagen)
        return
        
    yield simulatie_omgeving.timeout(huidige_reservering['duur_minuten'])
    
    # rijdtijd volgens schatten
    effectieve_rijtijd_in_minuten = schat_werkelijke_rijtijd(huidige_reservering['duur_minuten'])

    # huidige aantal banden lek plus de nieuwe duur, dus zoadnig de kans op falen wordt berekend 
    # de tijd is berekend met een gemiddelde snelheid van 30 km/uur
    # dus bv 90000 min is 1500 uur dus 45 000 km tot een versleten band 
    kans_op_lekke_band = bereken_weibull_faalkans(gekozen_wagen.minuten_banden_lek, effectieve_rijtijd_in_minuten, 1.0, 300000.0) # hier 1 is een incident, niet echt slijtage
    kans_op_versleten_banden = bereken_weibull_faalkans(gekozen_wagen.minuten_banden_slijtage, effectieve_rijtijd_in_minuten, 3.5, 90000.0)
    kans_op_versleten_remblokjes = bereken_weibull_faalkans(gekozen_wagen.minuten_remblokjes_slijtage, effectieve_rijtijd_in_minuten, 2.5, 99960.0) # komt overeen met ongeveer 1666 uur wat overeenkomt met 50000 km bij 30 km/uur (remblokjes nakijken na 40000 km ongeveer)

    gekozen_wagen.totale_levensduur_minuten += effectieve_rijtijd_in_minuten
    gekozen_wagen.minuten_banden_lek += effectieve_rijtijd_in_minuten
    gekozen_wagen.minuten_sinds_laatste_onderhoud += effectieve_rijtijd_in_minuten
    gekozen_wagen.minuten_banden_slijtage += effectieve_rijtijd_in_minuten
    gekozen_wagen.minuten_remblokjes_slijtage += effectieve_rijtijd_in_minuten
        
    # per mogelijke falen op de wagen een getal tussen 0 en 1
    willekeurige_kans_trekking_banden_lek = np.random.random()
    willekeurige_kans_trekking_banden_slijtage = np.random.random()
    willekeurige_kans_trekking_remblokjes = np.random.random()

    # hier zal een onderhoud worden gehouden, de rijminuten op dat onderdeel zal naar 0 gaan
    if willekeurige_kans_trekking_banden_lek < kans_op_lekke_band:
        simulatie_omgeving.process(stuur_naar_garage(simulatie_omgeving, parkeerplaats_queue, gekozen_wagen, np.random.uniform(120.0, 240.0), "banden_lek"))
        
    elif willekeurige_kans_trekking_banden_slijtage < kans_op_versleten_banden:
        simulatie_omgeving.process(stuur_naar_garage(simulatie_omgeving, parkeerplaats_queue, gekozen_wagen, np.random.uniform(120.0, 180.0), "banden_slijtage"))
        
    elif willekeurige_kans_trekking_remblokjes < kans_op_versleten_remblokjes:
        simulatie_omgeving.process(stuur_naar_garage(simulatie_omgeving, parkeerplaats_queue, gekozen_wagen, np.random.uniform(180.0, 300.0), "remblokjes"))
        
    # na 6000 rijminuten (100 uur)
    elif gekozen_wagen.minuten_sinds_laatste_onderhoud >= 6000.0:
        if np.random.random() < 0.75:
            # kleine preventieve onderhoud van 60-90 minuten
            simulatie_omgeving.process(stuur_naar_garage(simulatie_omgeving, parkeerplaats_queue, gekozen_wagen, np.random.uniform(60.0, 90.0), "preventief"))
        else:
            # grotere preventieve onderhoud van 180-240 minuten
            simulatie_omgeving.process(stuur_naar_garage(simulatie_omgeving, parkeerplaats_queue, gekozen_wagen, np.random.uniform(180.0, 240.0), "preventief"))
            
    else:
        # geen onderhoud nodig, terug in queue
        yield parkeerplaats_queue.put(gekozen_wagen)

def start_simulatie(simulatie_omgeving, verzameling_wagens_per_locatie, lijst_met_reserveringen, lijst_gefaalde_reserveringen, statistieken, geduld_wachttijd_minuten):
    # krijgen een lijst van reservaties
    for huidige_reservering in lijst_met_reserveringen:
        tijd_tot_boekingsmoment = huidige_reservering['boekingsmoment'] - simulatie_omgeving.now
        if tijd_tot_boekingsmoment > 0:
            # wachten tot de reservatie start
            yield simulatie_omgeving.timeout(tijd_tot_boekingsmoment)

        # de reservering uitvoeren
        simulatie_omgeving.process(voer_reservering_uit(
            simulatie_omgeving, 
            verzameling_wagens_per_locatie[huidige_reservering['locatie']], 
            huidige_reservering, 
            lijst_gefaalde_reserveringen, 
            statistieken, 
            geduld_wachttijd_minuten
        ))