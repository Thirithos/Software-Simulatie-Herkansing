import json
from datetime import datetime

# data bevat "types", "reserveringen", "vehicles", "locations"

voertuig_types = {
    0: "bestelwagens",
    1: "bussen",
    2: "elektrische fietsen",
    3: "klassieke fietsen",
    4: "personenwagens",
    5: "speciale elektrische fietsen",
    6: "speciale fietsen",
    7: "vrachtwagens"
}

# aan de hand van vehicletypeid binnen jobs veld enkel de reserveringen van dat type voertuig in een nieuwe datafile zetten, dan is de data gecleand van fouten en weekends (zijn er te weinig bijvoorbeeld op zaterdag 435/(104*4) gemiddeld dus te weinig)
# deze python file kan dus een nieuwe json file maken, dan moet er niet telkens gefilterd worden in elke file 
def maak_datafile_specifiek_voertuig(vehicleTypeId):
    voertuig_naam = voertuig_types.get(vehicleTypeId, "onbekend").replace(" ", "_")
    output_filename = f"data/data_{voertuig_naam}.json"

    with open('data/data.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    locatie_mapping = {}
    for locatie in data.get("locations", []):
        coords = locatie.get("coords", {})
        if "latitude" in coords and "longitude" in coords:
            # een tuple (latitude, longitude) als unieke sleutel elke locatie heeft dan een mapping
            coord_sleutel = (coords["latitude"], coords["longitude"])
            locatie_mapping[coord_sleutel] = locatie.get("address")

    gefilterde_reserveringen = []
    fouten_genegeerd = 0
    weekend_genegeerd = 0
    fouten_op_zaterdag = 0
    fouten_op_zondag = 0 
    
    for job in data.get("jobs", []):
        if job.get("vehicleTypeId") == vehicleTypeId:
            
            # locatie mapping door de coördinaten te veranderen naar adres zoals in de data zit
            coords = job.get("coords", {})
            locatie_naam = "Geen coördinaten in job"
            
            if "latitude" in coords and "longitude" in coords:
                coord_sleutel = (coords["latitude"], coords["longitude"])
                
                locatie_naam = locatie_mapping[coord_sleutel]
            
            # starttijd en duur bepalen uit de "period" field
            if "period" in job:
                from_date_str = job["period"].get("fromDate")
                to_date_str = job["period"].get("toDate")

                               
                if from_date_str and to_date_str:
                    # fromisoformat ondersteunt de +02:00 tijdzone
                    start_dt = datetime.fromisoformat(from_date_str)
                    end_dt = datetime.fromisoformat(to_date_str)

                    # er is besloten in minuten te werken, seconden is te fijn, in simpy maakt het opzcih niet veel uit
                    # zolang het consistent is 
                    duur_minuten = (end_dt - start_dt).total_seconds()/60

                    # negeer zaterdag (5) en zondag (6)
                    if start_dt.weekday() == 5:
                        # er wordt geteld voor te zien of er hetzelfde uitkomt als eerste_analyse_data.py
                        weekend_genegeerd += 1
                        fouten_op_zaterdag += 1
                        continue

                    if start_dt.weekday() == 6:
                        weekend_genegeerd += 1
                        fouten_op_zondag += 1
                        continue
                    
                    # soms is er een fout in data waardoor duur negatief is, omdat endtime voor begintime is,
                    # die reserveringen kunnen niet erin blijven
                    if duur_minuten < 0:
                        fouten_genegeerd += 1
                        continue

                    locatie_naam = locatie_naam[5:]
                    # voor (Seniotel)
                    locatie_naam = str(locatie_naam).replace("(", "").replace(")", "").strip()
                    # toevoegen en vervangen
                    locatie_naam = "_".join(locatie_naam.split())

                    # dit weerspiegeld de gefilterde dataset id is ook niet meer nodig
                    nieuwe_reservering = {
                        "sleutelsOpgehaald": job.get("keysPickedUp"),
                        "locatie": locatie_naam,
                        "startTijd": from_date_str,
                        "duur": duur_minuten
                    }
                    
                    gefilterde_reserveringen.append(nieuwe_reservering)

    # gefilterde reserveringen is gewoon een lijst daarom ook dict voor de json.dump
    nieuwe_data = {
        "reserveringen": gefilterde_reserveringen
    }

    with open(output_filename, 'w', encoding='utf-8') as outfile:
        json.dump(nieuwe_data, outfile, ensure_ascii=False, indent=4)
        
    print(f"Aantal reserveringen overgeslagen wegens negatieve duur: {fouten_genegeerd}")
    print(f"Aantal reserveringen overgeslagen wegens weekend: {weekend_genegeerd}")
    print(f"Aantal reserveringen overgeslagen op zaterdag: {fouten_op_zaterdag}")
    print(f"Aantal reserveringen overgeslagen op zondag: {fouten_op_zondag}")

maak_datafile_specifiek_voertuig(4)