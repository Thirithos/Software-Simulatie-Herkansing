import simpy
import numpy as np

class Wagen:
    def __init__(self, identificatienummer_wagen, naam_van_locatie):
        self.identificatienummer = identificatienummer_wagen
        self.locatie_naam = naam_van_locatie

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
    
    for locatie_naam, aantal_toegewezen_wagens in verdeelsleutel_wagens.items():
        parkeerplaats_wachtrij = simpy.FilterStore(simulatie_omgeving, capacity=aantal_toegewezen_wagens)
        
        for _ in range(aantal_toegewezen_wagens):
            nieuwe_wagen = Wagen(teller_wagen_identificatie, locatie_naam)
            parkeerplaats_wachtrij.put(nieuwe_wagen)
            lijst_alle_wagens_referentie.append(nieuwe_wagen)
            teller_wagen_identificatie += 1
            
        verzameling_wagens_per_locatie[locatie_naam] = parkeerplaats_wachtrij
        
    return verzameling_wagens_per_locatie, lijst_alle_wagens_referentie

def stuur_naar_garage(simulatie_omgeving, parkeerplaats_wachtrij, specifieke_wagen, reparatie_duur_in_minuten, type_reparatie):
    yield simulatie_omgeving.timeout(reparatie_duur_in_minuten)
    specifieke_wagen.aantal_reparaties += 1
    
    if type_reparatie == "banden_lek":
        specifieke_wagen.minuten_banden_lek = 0.0
    elif type_reparatie == "banden_slijtage":
        specifieke_wagen.minuten_banden_slijtage = 0.0
    elif type_reparatie == "remblokjes":
        specifieke_wagen.minuten_remblokjes_slijtage = 0.0
    elif type_reparatie == "preventief":
        specifieke_wagen.minuten_sinds_laatste_onderhoud = 0.0
        
    yield parkeerplaats_wachtrij.put(specifieke_wagen)

def schat_werkelijke_rijtijd(gereserveerde_duur_in_minuten):
    ondergrens = 0.15 * gereserveerde_duur_in_minuten
 
    fractie_bovengrens = 0.75 - (0.00073 * gereserveerde_duur_in_minuten)
    fractie_bovengrens = max(0.40, fractie_bovengrens)
    bovengrens = gereserveerde_duur_in_minuten * fractie_bovengrens
    
    ondergrens = min(ondergrens, gereserveerde_duur_in_minuten)
    bovengrens = max(ondergrens, bovengrens)
    
    return np.random.uniform(ondergrens, bovengrens)

def bereken_weibull_faalkans(huidige_levensduur_in_minuten, duur_nieuwe_reservering_in_minuten, vorm_parameter_beta, schaal_parameter_eta):
    exponent_voor_de_reservering = (huidige_levensduur_in_minuten / schaal_parameter_eta) ** vorm_parameter_beta
    exponent_na_de_reservering = ((huidige_levensduur_in_minuten + duur_nieuwe_reservering_in_minuten) / schaal_parameter_eta) ** vorm_parameter_beta

    kans_op_falen = 1.0 - np.exp(exponent_voor_de_reservering - exponent_na_de_reservering)

    return kans_op_falen

def voer_reservering_uit(simulatie_omgeving, parkeerplaats_wachtrij, huidige_reservering, lijst_gefaalde_reserveringen, statistieken, geduld_wachttijd_minuten):
    wachttijd_tot_start_reservering = huidige_reservering['absolute_starttijd'] - simulatie_omgeving.now
    if wachttijd_tot_start_reservering > 0:
        yield simulatie_omgeving.timeout(wachttijd_tot_start_reservering)
        
    start_wacht_tijd_moment = simulatie_omgeving.now
    maximaal_geduld_klant_in_minuten = geduld_wachttijd_minuten
    annuleringsmarge_in_minuten = 15.0
    
    if len(parkeerplaats_wachtrij.items) > 0:
        beschikbare_wagens = list(parkeerplaats_wachtrij.items)
        beschikbare_wagens.sort(key=lambda w: w.totale_levensduur_minuten)
        beste_wagen = beschikbare_wagens[0]

        aanvraag_voor_wagen = parkeerplaats_wachtrij.get(lambda w: w.identificatienummer == beste_wagen.identificatienummer)
    else:
        aanvraag_voor_wagen = parkeerplaats_wachtrij.get()
        
    race_resultaat = yield aanvraag_voor_wagen | simulatie_omgeving.timeout(maximaal_geduld_klant_in_minuten)
    
    if aanvraag_voor_wagen in race_resultaat:
        gekozen_wagen = aanvraag_voor_wagen.value
        
        if simulatie_omgeving.now > start_wacht_tijd_moment + 0.0001:
            statistieken['succesvol_gewacht'] += 1
            
        if huidige_reservering.get('sleutels_opgehaald', 1) == 0:
            yield simulatie_omgeving.timeout(annuleringsmarge_in_minuten)
            statistieken['niet_doorgegaan_en_vrijgegeven'] += 1
            yield parkeerplaats_wachtrij.put(gekozen_wagen)
            return
            
        yield simulatie_omgeving.timeout(huidige_reservering['duur_minuten'])
        
        effectieve_rijtijd_in_minuten = schat_werkelijke_rijtijd(huidige_reservering['duur_minuten'])

        kans_op_lekke_band = bereken_weibull_faalkans(gekozen_wagen.minuten_banden_lek, effectieve_rijtijd_in_minuten, 1.0, 300000.0)
        kans_op_versleten_banden = bereken_weibull_faalkans(gekozen_wagen.minuten_banden_slijtage, effectieve_rijtijd_in_minuten, 3.5, 90000.0)
        kans_op_versleten_remblokjes = bereken_weibull_faalkans(gekozen_wagen.minuten_remblokjes_slijtage, effectieve_rijtijd_in_minuten, 2.5, 240000.0)
        
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
        aanvraag_voor_wagen.cancel()
        lijst_gefaalde_reserveringen.append(1)

def start_simulatie(simulatie_omgeving, verzameling_wagens_per_locatie, lijst_met_reserveringen, lijst_gefaalde_reserveringen, statistieken, geduld_wachttijd_minuten):
    for huidige_reservering in lijst_met_reserveringen:
        tijd_tot_boekingsmoment = huidige_reservering['boekingsmoment'] - simulatie_omgeving.now
        if tijd_tot_boekingsmoment > 0:
            yield simulatie_omgeving.timeout(tijd_tot_boekingsmoment)
            
        simulatie_omgeving.process(voer_reservering_uit(
            simulatie_omgeving, 
            verzameling_wagens_per_locatie[huidige_reservering['locatie']], 
            huidige_reservering, 
            lijst_gefaalde_reserveringen, 
            statistieken, 
            geduld_wachttijd_minuten
        ))