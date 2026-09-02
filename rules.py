from dataclasses import dataclass
from collections import defaultdict

RULESET_VERSION = "2026.09.02-v3"
VERIFIED_DATE = "2026-09-02"

@dataclass
class Assessment:
    status: str
    deductible_amount: float
    confidence: str
    reasons: list
    missing: list
    plain_summary: str

def net_cost(c):
    return max(float(c.get("amount",0) or 0) - float(c.get("rot",0) or 0), 0)

def classify_from_answers(c):
    """Translate ordinary-language answers into a tax category."""
    work = c.get("work_type","")
    existed = c.get("existed_before")
    changed_layout = c.get("changed_layout",False)
    added_new = c.get("added_new",False)

    if work == "Försäljningskostnad":
        return "sale"
    if changed_layout or added_new or existed is False:
        return "basic"
    return "repair"

def assess(c, sale_year, costs):
    kind = classify_from_answers(c)
    amount = net_cost(c)
    year = int(c.get("year") or sale_year)
    evidence = bool(c.get("evidence"))
    improved = c.get("improved")

    yearly = defaultdict(float)
    for x in costs:
        if classify_from_answers(x) in ("repair","basic"):
            yearly[int(x.get("year") or sale_year)] += net_cost(x)

    reasons, missing = [], []

    if kind == "sale":
        reasons.append("Du har beskrivit detta som en kostnad som uppstod för att kunna sälja bostaden.")
        if not evidence:
            missing.append("Försök hitta faktura, kvitto, avtal eller betalning som visar kostnaden.")
        return Assessment(
            "Ser möjlig ut", amount, "strong" if evidence else "medium",
            reasons, missing,
            "Det här ser ut som en kostnad som kan få minska vinsten från bostadsförsäljningen."
        )

    if yearly[year] < 5000:
        reasons.append(
            f"De förbättringskostnader du hittills lagt in för {year} blir tillsammans mindre än 5 000 kr."
        )
        missing.append(
            "Lägg in alla renoveringar och förbättringar från samma år. Det är totalsumman för året som är viktig."
        )
        return Assessment(
            "Behöver mer information", 0, "low", reasons, missing,
            "Det går inte att räkna med den här posten ännu. Flera mindre kostnader samma år kan tillsammans passera gränsen."
        )

    if kind == "basic":
        reasons.append(
            "Dina svar tyder på att du byggde nytt, byggde om eller lade till något som inte fanns tidigare."
        )
        if not evidence:
            missing.append("Försök hitta något som visar vad som gjordes och vad det kostade.")
        return Assessment(
            "Ser möjlig ut", amount, "strong" if evidence else "medium",
            reasons, missing,
            "Det här liknar det Skatteverket kallar en grundförbättring. Du behöver inte kunna ordet – Bovinst håller reda på kategorin."
        )

    if kind == "repair":
        if year < sale_year - 5 or year > sale_year:
            reasons.append(
                f"Du sålde bostaden {sale_year}. Den här typen av renovering får normalt bara räknas från {sale_year-5} till {sale_year}."
            )
            return Assessment(
                "Ser inte ut att kunna räknas med", 0, "low", reasons, [],
                "Åtgärden verkar vara för gammal för just reglerna om reparation och underhåll."
            )

        if improved is not True:
            missing.append(
                "Vi behöver veta om bostaden fortfarande var i bättre skick när du sålde den än när du köpte den."
            )
            return Assessment(
                "Behöver mer information", 0, "medium", reasons, missing,
                "Årtalet fungerar, men vi behöver förstå om förbättringen fortfarande fanns kvar när bostaden såldes."
            )

        reasons.append(
            "Åtgärden ligger inom rätt tidsperiod och du har angett att bostaden var i bättre skick vid försäljningen."
        )
        if not evidence:
            missing.append("Försök hitta underlag som visar kostnaden.")
        return Assessment(
            "Ser möjlig ut", amount, "strong" if evidence else "medium",
            reasons, missing,
            "Det här ser ut som en renovering eller reparation som kan vara relevant i vinstberäkningen."
        )

    return Assessment("Behöver mer information",0,"low",[],["Vi behöver veta mer om kostnaden."],
                      "Bovinst kan inte bedöma posten ännu.")
