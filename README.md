# Bovinst v0.3.0 – Nybörjarguiden

Den här versionen gör nybörjarperspektivet till en grundregel i hela appen.

## Nytt
- användaren behöver inte välja skattekategori själv
- vanliga frågor översätts internt till skatteregler
- varje svårt begrepp förklaras när det behövs
- skatteord döljs bakom "Visa skatteordet – bara om du vill"
- 5 000-kronorsregeln förklaras med vardagsexempel
- resultat använder "har bra stöd", "kan vara möjligt" och "behöver kontrolleras"
- saknade kvitton hanteras utan att kostnaden raderas
- ingen slutlig skatt visas innan hela K5/K6-logiken är byggd

## Starta
pip install -r requirements.txt
streamlit run app.py
