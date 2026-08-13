# Software-Simulatie-Herkansing

## Hoe te gebruiken:

In analyse wordt analyse gemaakt van de data in de data folder

Start met de data enkel voor personenwagens te selecteren door data_splitser.py met functie met argument 4 (personenwagens).

Nu er een specifieke opgeruimde data file bestaat met bruikbare data, kan genereer_parameters_distributies.py worden uitgevoerd.
Dit zal de nodige informatie leveren over de verdelingen zonder de hele data te moeten gebruiken.
(de andere files geven meer info over waarom ik de keuzes heb gemaakt van de nodige informatie over de verdelingen en data sampling zelf)

Nu kan de simulatie worden gestart door middel van simulatie.py
In de variabele algoritme_om_te_testen worden de algoritmes getest, op 6 scenario's voor voorlooptijd. ( dit is belangrijk vooral voor de verplaatsingsalgoritme
In de variabele mogelijke_klant_wachttijden kan worden gekozen welke wachttijden er allemaal getest worden 
In de variabele vlootgroottes, worden het aantal vlootgroottes getest

simulatie_analyse.py maakt grafieken om de resulaten te proberen begrijpen

