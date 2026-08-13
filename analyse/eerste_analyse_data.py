import json
import os
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime

# data bevat "types", "jobs", "vehicles", "locations"

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

def haal_coordinaten_op(coord_data):
    if isinstance(coord_data, dict):
        latitude = coord_data.get('latitude')
        longitude = coord_data.get('longitude')
        return (latitude, longitude)
    else:
        return None

with open('data/data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

df_reserveringen = pd.DataFrame(data["jobs"])
df_voertuigen = pd.DataFrame(data["vehicles"])
df_locaties = pd.DataFrame(data["locations"])

aantal_types = len(data["types"])
print(f"Aantal type voertuigen: {aantal_types}")
# 8 types

aantal_reserveringen = len(df_reserveringen)
print(f"Aantal reserveringen: {aantal_reserveringen}")
# 61980 reserveringen

print("\n")

# counter telt voor elke voertuigtype het aantal reserveringen
reserveringen_aantal_per_type = df_reserveringen['vehicleTypeId'].value_counts()

for voertuigtype, aantal in reserveringen_aantal_per_type.items():
    print(f"Aantal reserveringen voor {voertuig_types.get(voertuigtype)}: {aantal}")

print("\n")

aantal_voertuigen = len(df_voertuigen)
print(f"Aantal voertuigen: {aantal_voertuigen}")
# 1360 voertuigen

print("\n")

# hier telt counter voor elke voertuigtype het aantal voertuigen dat er bestaan
voertuigen_aantal_per_type = df_voertuigen['vehicleType'].value_counts()

for voertuigtype, aantal in voertuigen_aantal_per_type.items():
    print(f"Aantal {voertuig_types.get(voertuigtype)}: {aantal}")

print("\n")

status_type_counts = df_voertuigen.groupby(['status', 'vehicleType']).size().unstack(fill_value=0)

# tellen van afevoerde voertuigen per type voertuig 
if 'Afgevoerd' in status_type_counts.index:
    for voertuigtype, aantal in status_type_counts.loc['Afgevoerd'].items():
        if aantal > 0:
            print(f"Aantal afgevoerde {voertuig_types.get(voertuigtype)}: {aantal}")

print("\n")

# tellen van voertuigen uit dienst per type voertuig
if 'Uitdienst' in status_type_counts.index:
    for voertuigtype, aantal in status_type_counts.loc['Uitdienst'].items():
        if aantal > 0:
            print(f"Aantal uitdienst {voertuig_types.get(voertuigtype)}: {aantal}")

print("\n")

#tellen van voertuigen in voortraject per type voertuig
if 'Voortraject' in status_type_counts.index:
    for voertuigtype, aantal in status_type_counts.loc['Voortraject'].items():
        if aantal > 0:
            print(f"Aantal in voortraject {voertuig_types.get(voertuigtype)}: {aantal}")

print("\n")

# tellen van voertuigen indienst per type voertuig
if 'Indienst' in status_type_counts.index:
    for voertuigtype, aantal in status_type_counts.loc['Indienst'].items():
        if aantal > 0:
            print(f"Aantal indienst {voertuig_types.get(voertuigtype)}: {aantal}")

print("\n")

# geen enkele fiets is als voertuig ingegeven, dus kunnen geen simulaties uitvoeren om dit aantal te verminderen, het enigste dat er kan worden geteld is de hoeveelheid piek fietsen op een gegeven moment.  

aantal_locaties = len(df_locaties)
print(f"Aantal locaties: {aantal_locaties}")
# 78 locaties

# locaties koppelen aan de reserveringen, hoeveel locaties zijn er per voertuigtype

# Eerst een mapping van coordinaten naar adressen
df_locaties['coord_tuple'] = df_locaties['coords'].apply(haal_coordinaten_op)
locatie_mapping = dict(zip(df_locaties['coord_tuple'], df_locaties['address']))

df_reserveringen['coord_tuple'] = df_reserveringen['coords'].apply(haal_coordinaten_op)
df_reserveringen['adres'] = df_reserveringen['coord_tuple'].map(locatie_mapping)

df_reserveringen['ruwe_starttijd'] = df_reserveringen['period'].str.get('fromDate')
df_reserveringen['starttijd'] = pd.to_datetime(df_reserveringen['ruwe_starttijd'])
df_reserveringen['weekdag'] = df_reserveringen['starttijd'].dt.weekday

reserveringen_met_coordinaten = df_reserveringen.dropna(subset=['coord_tuple'])
unieke_locaties_per_type = reserveringen_met_coordinaten.drop_duplicates(subset=['vehicleTypeId', 'coord_tuple'])

# dit is de personenwagens
# hier tel ik ook het aantal per locatie
personenwagens_reserveringen = df_reserveringen[df_reserveringen['vehicleTypeId'] == 4]
locatie_reserveringen_persoonwagen = personenwagens_reserveringen['adres'].value_counts()

# aantal locaties per voertuigtype printen
aantal_locaties_persoonwagen = len(unieke_locaties_per_type[unieke_locaties_per_type['vehicleTypeId'] == 4])
print(f"Aantal locaties voor personenwagens: {aantal_locaties_persoonwagen}")

aantal_locaties_bestelwagen = len(unieke_locaties_per_type[unieke_locaties_per_type['vehicleTypeId'] == 0])
print(f"Aantal locaties voor bestelwagens: {aantal_locaties_bestelwagen}")

aantal_locaties_vrachtwagen = len(unieke_locaties_per_type[unieke_locaties_per_type['vehicleTypeId'] == 7])
print(f"Aantal locaties voor vrachtwagens: {aantal_locaties_vrachtwagen}")

totaal_persoonwagen_reserveringen = locatie_reserveringen_persoonwagen.sum()
verdeelsleutel_proporties = {}

print("\n")

# de proportie is voor algoritmen die geen wagens verplaatsen, om de verdeling tussen de wagens te bepalen
for locatie, aantal in locatie_reserveringen_persoonwagen.items():
    proportie = aantal / totaal_persoonwagen_reserveringen
    verdeelsleutel_proporties[locatie] = proportie
    print(f"{locatie}: aantal {aantal}, proportie: {proportie:.2%}")
    
# Tel hoeveel reserveringen er per dag zijn
reserveringen_per_dag = df_reserveringen['weekdag'].value_counts().sort_index()
dagen_namen = ['maandag', 'dinsdag', 'woensdag', 'donderdag', 'vrijdag', 'zaterdag', 'zondag']

print("\n")
# totale aantallen
dagen_aantallen = []
for dag_idx in range(7):
    aantal = reserveringen_per_dag.get(dag_idx)
    dagen_aantallen.append(aantal)
    print(f"Aantal reserveringen op {dagen_namen[dag_idx]}: {aantal}")

print("\n")
#Aantal reserveringen op maandag: 12211
#Aantal reserveringen op dinsdag: 13570
#Aantal reserveringen op woensdag: 12241
#Aantal reserveringen op donderdag: 13592
#Aantal reserveringen op vrijdag: 9726
#Aantal reserveringen op zaterdag: 435
#Aantal reserveringen op zondag: 205
    
# tel totale lengte van de historische data, tel aantal maandagen, dinsdagen, woensdagen, donderdagen, vrijdagen, zaterdagen en zondagen. tussen de start van de eerste en laatste datum.
start_datum = df_reserveringen['starttijd'].min().normalize()
eind_datum = df_reserveringen['starttijd'].max().normalize()
historische_dagen = pd.date_range(start=start_datum, end=eind_datum, freq='D')

historische_dagen_counter = historische_dagen.weekday.value_counts()

print(f"Eerste datum in de historische data: {start_datum.date()}")
print(f"Laatste datum in de historische data: {eind_datum.date()}")
print(f"Totale lengte van de historische data: {len(historische_dagen)} dagen")

for dag_idx in range(7):
    print(f"Aantal {dagen_namen[dag_idx]} in de historische periode: {historische_dagen_counter.get(dag_idx)}")

print("\n")

os.makedirs('histogrammen', exist_ok=True)

plt.figure(figsize=(8, 5))
plt.bar(dagen_namen, dagen_aantallen, color='skyblue', edgecolor='black')
plt.title('Totaal aantal reserveringen per dag')
plt.ylabel('Aantal reserveringen')
plt.xticks(rotation=45)
plt.tight_layout()

plt.savefig('histogrammen/reserveringen_per_dag.png')
plt.close()

#  bekijken hoeveel keer de reservering is uitgevoerd voor personenwagens, door keysPickedUp field
# ook tellen voor aantal reserveringen van type 4 in het weekend ongeacht de keysPickedUp field

aantal_reserveringen_persoonwagen = int(personenwagens_reserveringen['keysPickedUp'].sum())
aantal_reserveringen_niet_opgehaald = len(personenwagens_reserveringen) - aantal_reserveringen_persoonwagen

reservering_zaterdag = len(personenwagens_reserveringen[personenwagens_reserveringen['weekdag'] == 5])
reservering_zondag = len(personenwagens_reserveringen[personenwagens_reserveringen['weekdag'] == 6])

print(f"Aantal reserveringen op zaterdag voor personenwagens: {reservering_zaterdag}")
print(f"Aantal reserveringen op zondag voor personenwagens: {reservering_zondag}")

print("\n")

totaal_personenwagens_reserveringen = aantal_reserveringen_persoonwagen + aantal_reserveringen_niet_opgehaald
if totaal_personenwagens_reserveringen > 0:
    percentage_reserveringen_doorgegaan = (aantal_reserveringen_persoonwagen / totaal_personenwagens_reserveringen) * 100
else:
    percentage_reserveringen_doorgegaan = 0.0

print(f"Aantal uitgevoerde reserveringen voor personenwagens: {aantal_reserveringen_persoonwagen}")
print(f"Aantal reserveringen voor personenwagens die niet zijn opgehaald: {aantal_reserveringen_niet_opgehaald}")
print(f"Percentage reserveringen voor personenwagens die zijn doorgegaan: {percentage_reserveringen_doorgegaan:.2f}%")

# piek-aantal gelijktijdige reservaties per voertuigtype
for type, type_naam in voertuig_types.items():
    # Deze lijst bevat alle gebeurtenissen wanneer een auto vertrekt of terugkomt
    gebeurtenissen = []
    
    for reservering in data.get("jobs"):
        if reservering.get("vehicleTypeId") == type:
            period = reservering.get("period")
            start_str = period.get("fromDate")
            eind_str = period.get("toDate")
            
        
            # Zet de tekst-tijden om naar leesbare Python datetime objecten
            start_dt = datetime.fromisoformat(start_str)
            eind_dt = datetime.fromisoformat(eind_str)

            # er zijn zo gevallen inde data                    
            if eind_dt > start_dt:
                # vertrek voertuig
                # +1 betekent dat het aantal gelijktijdig uitgeleende voertuigen stijgt met 1
                gebeurtenissen.append((start_dt, 1))
                    
                # aankomst voertuig
                # -1 betekent dat het aantal gelijktijdig uitgeleende voertuigen daalt met 1
                gebeurtenissen.append((eind_dt, -1))

    # sorteren op daatum als eerste, en dan als tweede op actie (-1 voor terugbrengen, +1 voor uitlenen)
    # -1 komt voor +1, zodat terugbrengen altijd vóór uitlenen wordt verwerkt
    # om geen niewe piek te veroorzaken als er een auto vertrekt
    gebeurtenissen.sort(key=lambda x: (x[0], x[1]))
    
    huidige_aantal = 0
    max_aantal = 0
    piek_moment = 0
    
    for tijd, verandering in gebeurtenissen:
        huidige_aantal += verandering
        
        if huidige_aantal > max_aantal:
            max_aantal = huidige_aantal
            piek_moment = tijd
            
    print(f"{type_naam}, maximum tegelijk: {max_aantal}")