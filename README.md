# Bovinst v0.22.0 – Explicita svar

Förberedd medan användaren är bortrest. Ingen push eller deploy nu.

Nytt:
- orörda frågor räknas inte längre som besvarade
- "Vet ej" räknas bara när användaren själv har valt det
- Avdragsminnet börjar med "Välj ett svar" i stället för automatiskt Vet ej
- tidslinjen börjar med "Välj ett svar" i stället för automatiskt Vet ej
- Bostadskontrollen kan inte längre välja villa eller svara på kontrollfrågor åt användaren
- saknade bostadskontrollsvar ger "behöver kontrolleras", aldrig falskt OK
- adaptiva följdfrågor får också ett neutralt startläge
- projekt auto-skapa först när minst en verklig följduppgift har lämnats
- explicit Vet ej bevaras som legitimt, genomgånget men osäkert svar
- 81 automatiska tester

Princip:
Bovinst får aldrig förväxla ett standardvärde i gränssnittet med ett faktiskt användarsvar.
