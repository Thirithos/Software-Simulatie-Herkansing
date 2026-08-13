import numpy as np
import matplotlib.pyplot as plt

# deze file dient om de voorlooptijd te als grafiek voor te stellen, ik heb drie soorten voorlooptijden gemaakt:
# een noodgeval (5-120 minuten), een gemiddelde (120-4320 minuten) en een planner (4320-20160 minuten), de verdeling is 15% planner, 65% gemiddeld en 20% nood, maar deze wordt aangepast in simulatie door enkele scenario's (6 verschillende) omdat dit toch belangrijk is het effect ervan (als het er is) te bekijken.
def trek_voorlooptijd_steekproef(aantal_samples=1):
    samples = []

    
    for _ in range(aantal_samples):
        groep = np.random.choice(['planner', 'gemiddeld', 'nood'], p=[0.15, 0.65, 0.20])
        
        if groep == 'planner':
            # 3 dagen tot 2 weken
            voorlooptijd = np.random.uniform(4320, 20160)
            
        elif groep == 'gemiddeld':
            # 2 uur tot 3 dagen
            voorlooptijd = np.random.uniform(120, 4320)

        elif groep == 'nood':
            # 5 minuten tot 2 uur
            voorlooptijd = np.random.uniform(5, 120)
            
        samples.append(voorlooptijd)
        
    return np.array(samples)

steekproef = trek_voorlooptijd_steekproef(100000)

plt.figure(figsize=(20, 6))
plt.hist(steekproef, bins=100, density=True, color='skyblue')
plt.title('Voorlooptijd Verdeling')
plt.xlabel('Voorlooptijd (minuten)')
plt.ylabel('Dichtheid')
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig('histogrammen/voorlooptijd_verdeling.png')