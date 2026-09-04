from dataclasses import dataclass
from collections import defaultdict

RULESET_VERSION="2026.09.04-v22"
VERIFIED_DATE="2026-09-03"

@dataclass
class Assessment:
    status:str
    deductible_amount:float
    confidence:str
    reasons:list
    missing:list
    plain_summary:str

def net_cost(c):
    """
    Belopp efter den ROT-reduktion användaren uttryckligen matat in.
    Historisk ROT ska inte antas automatiskt; appen frågar bara om modern ROT.
    """
    return max(float(c.get("amount",0) or 0)-float(c.get("rot",0) or 0),0)


def evidence_quality(c):
    """Normalisera både gamla och nya underlagsvärden."""
    raw=c.get("evidence_level")
    mapping={
        "Kvitto/faktura och betalning":"strong",
        "Kvitto eller faktura":"document",
        "Bankutdrag/betalning":"document",
        "Annat underlag":"alternative",
        "Foton/ritningar/bygglov eller annat":"alternative",
        "Inget underlag just nu":"none",
        "Vet ej":"none",
        "strong":"strong","document":"document","alternative":"alternative","none":"none",
    }
    if raw in mapping:
        return mapping[raw]
    return "document" if c.get("evidence") else "none"

def evidence_label(c):
    return {
        "strong":"Starkt underlag",
        "document":"Bra underlag",
        "alternative":"Alternativt underlag",
        "none":"Inget underlag just nu",
    }[evidence_quality(c)]

def amount_quality(c):
    q=c.get("amount_quality")
    if q in ("exact","approx","unknown"):
        return q
    return "exact" if float(c.get("amount",0) or 0)>0 else "unknown"

def classify_from_answers(c):
    if c.get("work_type")=="Försäljningskostnad":
        return "sale"
    if c.get("changed_layout") or c.get("added_new") or c.get("existed_before") is False:
        return "basic"
    return "repair"

def annual_improvement_total(costs, year, sale_year, home=None):
    """
    Summerar bara förbättringsutgifter som först klarar grundläggande individuell behörighet.
    Uppenbart obehöriga eller materiellt osäkra poster får inte hjälpa kalenderåret över 5 000 kr.
    """
    total=0.0
    for x in costs:
        if x.get("inactive"):
            continue
        if x.get("year_quality")=="unknown":
            continue
        if int(x.get("year") or sale_year)!=int(year):
            continue
        if amount_quality(x)!="exact":
            continue
        if x.get("self_labor"):
            continue

        kind=classify_from_answers(x)
        if kind not in ("repair","basic"):
            continue

        y=int(x.get("year") or sale_year)
        if y>int(sale_year):
            continue

        amount=net_cost(x)
        amount=max(amount-float(x.get("insurance_compensation",0) or 0),0)
        if amount<=0:
            continue

        if kind=="basic":
            if _old_basic_cutoff(x,home):
                continue
            if x.get("existed_before") is None and not (x.get("changed_layout") or x.get("added_new")):
                continue
        else:
            if y<int(sale_year)-5:
                continue
            if x.get("new_build_at_purchase"):
                continue
            if x.get("improved") is not True:
                continue

        total += amount
    return total

def _old_basic_cutoff(c, home):
    year=int(c.get("year") or 0)
    if home=="Bostadsrätt":
        return year and year < 1974
    return year and year < 1952

def assess(c, sale_year, costs, home=None):
    """
    Konservativ bedömning för vanliga privatbostadsfall.
    När information saknas returneras 0 eller varning hellre än att anta rätt till avdrag.
    """
    kind=classify_from_answers(c)
    amount=net_cost(c)
    year=int(c.get("year") or sale_year)
    evq=evidence_quality(c)
    evidence=evq in ("strong","document")
    alternative_evidence=evq=="alternative"
    aq=amount_quality(c)
    improved=c.get("improved")
    reasons=[]
    missing=[]

    if amount<=0:
        return Assessment(
            "Sparad – kostnaden behöver återskapas",0,"low",[],
            [
                "Kostnaden är ännu inte känd.",
                "Leta efter bankutdrag, lånehandling, offert, faktura eller andra spår som kan hjälpa dig återskapa beloppet."
            ],
            "Projektet sparas även utan känt belopp så att det inte glöms bort."
        )

    if year>int(sale_year):
        return Assessment(
            "Ser inte ut att kunna räknas med",0,"low",
            ["Åtgärden är daterad efter försäljningsåret."],[],
            "Kontrollera årtalet. En kostnad efter försäljningen ska inte automatiskt räknas in."
        )


    # Minnesbelopp ska inte förvandlas till falsk exakthet.
    if aq=="approx" and evq=="none":
        return Assessment(
            "Möjlig kostnad – behöver styrkas",0,"low",[],
            [
                "Beloppet är ungefärligt och bygger just nu bara på minnet.",
                "Försök hitta andra spår som visar att arbetet gjordes, omfattningen och ungefär när det utfördes."
            ],
            "Bovinst sparar posten men räknar inte in minnesbeloppet som deklarationsklart belopp ännu."
        )

    if aq=="approx" and alternative_evidence:
        return Assessment(
            "Kan vara möjlig med skäligt belopp",0,"medium",
            ["Du har markerat alternativa underlag som kan stödja att arbetet har utförts."],
            [
                "Det exakta beloppet är fortfarande osäkert.",
                "Bovinst ska hjälpa dig bygga ett underlag för ett skäligt belopp men ska inte hitta på summan."
            ],
            "Det kan finnas möjlighet till avdrag med ett skäligt belopp, men beloppet måste bedömas utifrån underlaget."
        )

    # User can set these flags in future document flows/tests.
    if c.get("self_labor"):
        return Assessment(
            "Ser inte ut att kunna räknas med",0,"low",
            ["Egen arbetsinsats är inte en avdragsgill förbättringsutgift."],[],
            "Bovinst räknar inte värdet av ditt eget arbete."
        )

    if c.get("rot_known") is False and int(c.get("year") or sale_year)>=2009:
        missing.append("Det är okänt om ROT användes. Kontrollera faktura eller Skatteverkets uppgifter innan beloppet blir deklarationsklart.")

    insurance=float(c.get("insurance_compensation",0) or 0)
    if insurance>0:
        amount=max(amount-insurance,0)
        reasons.append("Försäkringsersättning har räknats bort från kostnaden.")
        if amount<=0:
            return Assessment(
                "Ser inte ut att kunna räknas med",0,"low",reasons,[],
                "Hela den registrerade kostnaden verkar vara täckt av försäkringsersättning."
            )

    if kind=="sale":
        reasons.append("Du har beskrivit detta som en kostnad med direkt samband till försäljningen.")
        if c.get("sale_private_cost"):
            return Assessment(
                "Behöver mer information",0,"low",reasons,
                ["Privata kostnader som flytt eller vanlig städning ska inte behandlas som försäljningsutgift."],
                "Posten behöver delas upp eller klassificeras om innan den kan räknas med."
            )
        if not evidence:
            missing.append("Kvitto är inte det enda möjliga underlaget. Leta även efter bankbetalning, avtal, mejl eller andra spår av kostnaden.")
        return Assessment(
            "Ser möjlig ut",amount,"strong" if evidence else "medium",
            reasons,missing,
            "Det här ser ut som en kostnad som kan vara relevant i vinstberäkningen."
        )

    if kind=="basic":
        if home and _old_basic_cutoff(c,home):
            cutoff="1974" if home=="Bostadsrätt" else "1952"
            return Assessment(
                "Ser inte ut att kunna räknas med",0,"low",
                [f"Grundförbättringen är från före {cutoff} för den valda bostadstypen."],[],
                "Den här grundförbättringen ligger före den tidsgräns Bovinst använder för bostadstypen."
            )

        reasons.append("Dina svar tyder på ny-, till- eller ombyggnad eller något som inte fanns tidigare.")

        if c.get("better_material_split_needed"):
            missing.append(
                "Åtgärden verkar innehålla både ett vanligt utbyte och en tydlig standardhöjning. "
                "Kostnaden behöver delas mellan grundförbättring och reparation/underhåll."
            )
            return Assessment(
                "Behöver delas upp",0,"medium",reasons,missing,
                "Bovinst vill inte räkna hela kostnaden som grundförbättring när bara merkostnaden för bättre standard kan höra dit."
            )

        annual=annual_improvement_total(costs,year,sale_year,home)
        if annual<5000:
            reasons.append(f"De individuellt godtagbara förbättringsutgifterna för {year} blir hittills {annual:,.0f} kr.".replace(","," "))
            missing.append("Årets sammanlagda förbättringsutgifter behöver normalt nå minst 5 000 kr.")
            return Assessment(
                "Väntar på 5 000-kronorsgränsen",0,"low",reasons,missing,
                "Projektet ser i övrigt möjligt ut men årets godtagbara förbättringsutgifter ligger ännu under 5 000 kr."
            )

        if not evidence:
            missing.append("Försök hitta stöd för vad som gjordes, när det gjordes och kostnaden – till exempel foto, ritning, bankutdrag, lånehandling, offert eller mejl.")
        return Assessment(
            "Ser möjlig ut",amount,"strong" if evidence else "medium",
            reasons,missing,
            "Det här liknar en grundförbättring och kan vara relevant i vinstberäkningen."
        )

    # Repair/maintenance
    if year<int(sale_year)-5:
        return Assessment(
            "Ser inte ut att kunna räknas med",0,"low",
            [f"Försäljningen är {sale_year}. Reparation och underhåll får normalt bara avse {int(sale_year)-5}–{sale_year}."],[],
            "Åtgärden verkar vara för gammal för reglerna om förbättrande reparation och underhåll."
        )

    if c.get("new_build_at_purchase"):
        return Assessment(
            "Ser inte ut att kunna räknas med",0,"low",
            ["Du har angett att bostaden var nybyggd när du köpte den."],[],
            "Vanlig reparation och underhåll kan då inte automatiskt behandlas som en förbättring jämfört med skicket vid köpet."
        )

    if improved is not True:
        missing.append("Vi behöver veta om bostaden fortfarande var i bättre skick vid försäljningen än när du köpte den.")
        return Assessment(
            "Behöver mer information",0,"medium",reasons,missing,
            "Tidsperioden kan fungera, men Bovinst saknar stöd för att hela eller delar av kostnaden förbättrade skicket jämfört med köpet."
        )

    reasons.append("Åtgärden ligger inom sexårsperioden och du har angett att bostaden var i bättre skick vid försäljningen.")
    annual=annual_improvement_total(costs,year,sale_year,home)
    if annual<5000:
        reasons.append(f"De individuellt godtagbara förbättringsutgifterna för {year} blir hittills {annual:,.0f} kr.".replace(","," "))
        missing.append("Årets sammanlagda förbättringsutgifter behöver normalt nå minst 5 000 kr.")
        return Assessment(
            "Väntar på 5 000-kronorsgränsen",0,"low",reasons,missing,
            "Projektet ser i övrigt möjligt ut men årets godtagbara förbättringsutgifter ligger ännu under 5 000 kr."
        )

    if not evidence:
        missing.append("Försök hitta stöd för arbetet och kostnaden. Kvitto är bäst, men andra underlag kan också vara viktiga.")
    return Assessment(
        "Ser möjlig ut",amount,"strong" if evidence else "medium",
        reasons,missing,
        "Det här ser ut som förbättrande reparation eller underhåll som kan vara relevant."
    )









def project_readiness(case, cost, costs=None):
    """Försiktig deklarationsberedskap för ett enskilt projekt."""
    costs = costs or [cost]
    if cost.get("inactive"):
        return {
            "status":"Ignorerad","level":"inactive","ready":False,
            "reasons":["Projektet är markerat som inaktivt."],
            "next":"Ingen åtgärd om projektet verkligen inte ska räknas med."
        }

    reasons=[]
    steps=[]
    amount=float(cost.get("amount") or 0)
    aq=amount_quality(cost)
    yq=cost.get("year_quality","exact")
    ev=evidence_quality(cost)
    year=int(cost.get("year") or 0)
    sale_year=int(case.get("sellyear") or 0)
    kind=classify_from_answers(cost)

    if yq=="unknown":
        reasons.append("Året är inte fastställt.")
        steps.append("Tidsbestäm projektet med foton, mejl, bygglov, garantier, kalender eller bankhändelser.")
    elif yq=="approx":
        reasons.append("Året är ungefärligt.")
        steps.append("Försök snäva in perioden om tidsregler kan påverka avdraget.")

    if amount<=0 or aq=="unknown":
        reasons.append("Kostnaden är inte fastställd.")
        steps.append("Återskapa beloppet med faktura, bankkonto, lån, offert, kvitto eller annat stöd.")
    elif aq=="approx":
        reasons.append("Beloppet är ungefärligt.")
        steps.append("Stärk beloppet med så mycket daterat underlag som möjligt.")

    if ev=="none":
        reasons.append("Det finns ännu inget känt underlag.")
        steps.append("Leta efter alternativa spår: foton, ritningar, bygglov, bankutdrag, lån, offert, mejl, garanti eller företag.")
    elif ev=="alternative":
        reasons.append("Det finns alternativt underlag men ingen tydlig faktura/kvitto.")
        steps.append("Kontrollera att underlagen tillsammans stödjer tidpunkt, omfattning och belopp.")

    if cost.get("rot_known") is False and year>=2009:
        reasons.append("ROT är inte klarlagt.")
        steps.append("Kontrollera faktura eller uppgift från Skatteverket innan nettobeloppet används.")

    if kind in ("basic","repair") and cost.get("existed_before") is None:
        reasons.append("Det är oklart om lösningen fanns när bostaden köptes.")
        steps.append("Jämför med gamla prospekt, foton eller besiktningsunderlag från köpet.")

    if kind=="repair" and cost.get("improved") is None:
        reasons.append("Det är oklart om förbättringen fortfarande fanns kvar vid försäljningen.")
        steps.append("Beskriv skicket vid köp och försäljning så att reparationsregeln kan bedömas.")

    if sale_year and year and year>sale_year and yq!="unknown":
        return {
            "status":"Ska inte räknas med","level":"blocked","ready":False,
            "reasons":["Projektets år ligger efter försäljningsåret."],
            "next":"Kontrollera årtalet."
        }

    # Placeholderår får aldrig användas som verkligt faktum.
    if yq=="unknown":
        return {
            "status":"Möjligt avdrag – behöver kompletteras","level":"needs_info","ready":False,
            "reasons":reasons,
            "next":" ".join(dict.fromkeys(steps))
        }

    assessed=assess(cost, sale_year, costs, home=case.get("home"))

    hard_unknown=(
        amount<=0 or aq=="unknown"
        or (cost.get("rot_known") is False and year>=2009)
        or (kind in ("basic","repair") and cost.get("existed_before") is None)
        or (kind=="repair" and cost.get("improved") is None)
    )
    if hard_unknown:
        return {
            "status":"Möjligt avdrag – behöver kompletteras","level":"needs_info","ready":False,
            "reasons":reasons or list(assessed.missing),
            "next":" ".join(dict.fromkeys(steps)) or "Komplettera de saknade uppgifterna."
        }

    # Ungefärliga belopp eller alternativt underlag ska hållas kvar som möjliga,
    # även när assess() konservativt sätter deklarationsbeloppet till 0.
    if aq=="approx" or ev in ("none","alternative"):
        return {
            "status":"Möjligt avdrag – behöver styrkas","level":"needs_evidence","ready":False,
            "reasons":reasons or list(assessed.missing),
            "next":" ".join(dict.fromkeys(steps)) or "Stärk underlaget innan beloppet behandlas som deklarationsklart."
        }

    if assessed.status=="Väntar på 5 000-kronorsgränsen":
        return {
            "status":"Redo i sig – väntar på 5 000 kr för året","level":"threshold_pending","ready":False,
            "reasons":list(assessed.reasons) + list(assessed.missing),
            "next":"Lägg in alla relevanta förbättringsutgifter från samma kalenderår. Projektet räknas in först när årets kvalificerade summa når gränsen."
        }

    if assessed.deductible_amount<=0:
        return {
            "status":"Ska inte räknas med ännu","level":"blocked","ready":False,
            "reasons":list(assessed.reasons) + list(assessed.missing) or [assessed.status],
            "next":"Kontrollera Bovinsts bedömning och de uppgifter som ligger bakom den."
        }

    return {
        "status":"Redo att använda","level":"ready","ready":True,
        "reasons":["Centrala uppgifter är ifyllda och Bovinsts regelbedömning ger ett deklarationsbart belopp."],
        "next":"Behåll underlaget tillsammans med deklarationsunderlaget."
    }

def readiness_summary(case, costs):
    out={"ready":0,"needs_evidence":0,"needs_info":0,"threshold_pending":0,"blocked":0,"inactive":0,"total":0}
    for c in costs:
        r=project_readiness(case,c,costs)
        out["total"]+=1
        out[r["level"]]=out.get(r["level"],0)+1
    active=out["total"]-out["inactive"]
    out["active"]=active
    out["all_ready"]=active>0 and out["ready"]==active
    return out

def project_recovery_plan(case, cost, costs=None):
    """Individuell plan för att göra ett osäkert projekt användbart."""
    r=project_readiness(case,cost,costs)
    plan=[]
    aq=amount_quality(cost)
    yq=cost.get("year_quality","exact")
    ev=evidence_quality(cost)
    year=int(cost.get("year") or 0)

    if yq in ("unknown","approx"):
        plan.append(("När gjordes det?",
                     "Sök i gamla foton, mejl, kalender, bygglov, garantier, offerter eller bankhändelser."))
    if aq in ("unknown","approx"):
        plan.append(("Vad kostade det?",
                     "Sök faktura, banköverföring, lån, delbetalning, offert eller annan betalningsspårning."))
    if ev in ("none","alternative"):
        plan.append(("Vilket stöd finns?",
                     "Samla foton före/efter, ritningar, bygglov, garantier, mejl/SMS och uppgift om företag eller butik."))
    if cost.get("rot_known") is False and year>=2009:
        plan.append(("Fanns ROT?",
                     "Kontrollera faktura eller Skatteverkets uppgifter så att nettokostnaden blir rätt."))
    if classify_from_answers(cost) in ("basic","repair") and cost.get("existed_before") is None:
        plan.append(("Fanns lösningen redan när du köpte?",
                     "Leta i prospekt, äldre foton och besiktningsprotokoll från köpet."))
    if classify_from_answers(cost)=="repair" and cost.get("improved") is None:
        plan.append(("Fanns förbättringen kvar vid försäljningen?",
                     "Jämför skicket vid köp och försäljning och dokumentera det du minns."))

    if not plan and r["ready"]:
        plan.append(("Klart","Projektet behöver ingen ytterligare underlagsjakt just nu."))
    elif not plan:
        plan.append(("Kontrollera bedömningen","Läs varför Bovinst ännu inte räknar projektet som deklarationsklart."))
    return {"name":cost.get("name","Projekt"),"status":r["status"],"steps":plan}


def declaration_ready_costs(case, costs):
    return [c for c in costs if project_readiness(case,c,costs).get("ready")]

def declaration_ready_summary(case, costs):
    sale_year=int(case.get("sellyear") or 0)
    ready=declaration_ready_costs(case,costs)
    sale_expenses=basic=repair=0.0
    threshold_pending=[]

    for c in costs:
        r=project_readiness(case,c,costs)
        if r.get("level")=="threshold_pending":
            threshold_pending.append({
                "name":c.get("name","Projekt"),
                "year":int(c.get("year") or sale_year),
                "amount":net_cost(c)
            })

    for c in ready:
        kind=classify_from_answers(c)
        amount=max(net_cost(c)-float(c.get("insurance_compensation",0) or 0),0)
        if kind=="sale":
            sale_expenses+=amount
        elif kind=="basic":
            basic+=amount
        elif kind=="repair":
            repair+=amount

    return {
        "sale_expenses":sale_expenses,
        "basic":basic,
        "repair":repair,
        "total":sale_expenses+basic+repair,
        "ready_count":len(ready),
        "threshold_pending":threshold_pending,
    }

def money_miss_checks(case, costs):
    """
    Prioriterad lista över lagliga, lättmissade kontrollpunkter.
    Returnerar bara sådant som fortfarande är relevant att kontrollera.
    """
    home=normalize_home_type(case.get("home"))
    answers=case.get("hunt_answers",{}) or {}
    tasks=[]

    def add(priority, key, title, why, action):
        tasks.append({
            "priority":priority,
            "key":key,
            "title":title,
            "why":why,
            "action":action,
        })

    if home in ("Småhus","Ägarlägenhet"):
        if answers.get("purchase_costs")!="Ja":
            add(1,"purchase_costs","Köpkostnader kan saknas",
                "Lagfart, stämpelskatt och vissa kostnader för pantbrev/inteckning missas ofta.",
                "Kontrollera köpehandlingar, lagfartsbeslut och bankens underlag från köpet.")

    if home=="Bostadsrätt":
        if answers.get("brf")!="Ja":
            add(1,"brf","Föreningens uppgifter kan saknas",
                "Kapitaltillskott och inre reparationsfond kan påverka K6 men är lätta att förbise.",
                "Leta fram kontrolluppgift eller årsbesked från bostadsrättsföreningen.")

    if answers.get("sale_costs")!="Ja":
        add(1,"sale_costs","Alla försäljningskostnader kanske inte är med",
            "Det är lätt att bara ta med mäklararvodet och glömma andra försäljningsutgifter.",
            "Kontrollera mäklarfaktura, besiktning, energideklaration, juridik, försäkring, fotografering och eventuell homestyling.")

    active=[c for c in costs if not c.get("inactive")]
    if not active:
        add(1,"no_projects","Inga förbättringsprojekt är registrerade",
            "Om bostaden har ägts ett tag är det värt att säkerställa att inga renoveringar eller ombyggnader har glömts.",
            "Gå igenom Avdragsminnet och tidslinjen innan du avslutar.")

    uncertain=[c for c in active if c.get("draft") or c.get("amount_quality")=="unknown" or c.get("evidence_level") in (None,"Vet ej","none")]
    if uncertain:
        add(1,"uncertain_projects",f"{len(uncertain)} projekt behöver mer underlag",
            "Osäker kostnad eller svagt underlag kan göra att ett annars relevant avdrag inte blir deklarationsklart.",
            "Öppna Underlagsdetektiven och börja med de största eller äldsta projekten.")

    old_projects=[c for c in active if int(c.get("year") or 9999) < int(case.get("sellyear") or 0)-5]
    if old_projects:
        add(2,"old_projects","Äldre projekt kan fortfarande vara relevanta",
            "Femårsregeln gäller reparation/underhåll men inte alla typer av grundförbättringar.",
            "Kontrollera särskilt ny-, till- eller ombyggnad samt saker som inte fanns när bostaden köptes.")

    material_signal=[c for c in active if c.get("better_material") or c.get("higher_standard")]
    if material_signal:
        add(2,"better_material","Bättre material kan behöva delas upp",
            "En tydlig standardhöjning kan i vissa fall innehålla en grundförbättringsdel.",
            "Kontrollera vad den gamla lösningen motsvarade och vad merkostnaden för högre standard var.")

    unknowns=uncertainty_tasks(case, active)
    if unknowns:
        add(2,"unknowns",f"{len(unknowns)} kontrollpunkter är fortfarande olösta",
            "Vet ej är tillåtet, men vissa osäkerheter påverkar om beloppet kan användas i deklarationen.",
            "Följ Bovinsts prioriterade Vet ej-plan och lös de viktigaste först.")

    timeline=timeline_summary(case)
    if timeline["total"] and (timeline["reviewed"]<timeline["total"] or timeline["unknown"]):
        add(3,"timeline","Tidslinjen är inte helt säkrad",
            "Projekt som användaren inte kom på rum för rum kan dyka upp när man går igenom åren.",
            "Gå klart tidslinjen och skriv ner sådant du minns i varje period.")

    coverage=coverage_summary(case)
    if coverage["reviewed"]<coverage["total"] or coverage["unknown"]:
        add(3,"coverage","Avdragsminnet är inte helt genomgånget",
            "Bovinst kan inte säga att sökningen är komplett om relevanta områden återstår eller är Vet ej.",
            "Gå igenom återstående områden och lämna Vet ej bara där du faktiskt inte kan avgöra svaret ännu.")

    dups=duplicate_candidates(active)
    if dups:
        add(1,"duplicates",f"{len(dups)} möjlig(a) dublett(er)",
            "Samma kostnad får inte räknas två gånger.",
            "Kontrollera de markerade projekten innan slutbeloppen används.")

    tasks.sort(key=lambda x:(x["priority"],x["title"]))
    return tasks

def money_miss_score(case, costs):
    tasks=money_miss_checks(case,costs)
    high=sum(1 for t in tasks if t["priority"]==1)
    medium=sum(1 for t in tasks if t["priority"]==2)
    low=sum(1 for t in tasks if t["priority"]==3)
    if high:
        status="Inte klar"
    elif medium:
        status="Nästan klar"
    elif low:
        status="Bra läge"
    else:
        status="Genomgången"
    return {"status":status,"high":high,"medium":medium,"low":low,"total":len(tasks)}

def normalize_home_type(raw):
    value=(raw or "").strip().lower()
    if value in ("villa","småhus","småhus/villa","radhus","fritidshus"):
        return "Småhus"
    if value in ("bostadsrätt","brf"):
        return "Bostadsrätt"
    if value in ("ägarlägenhet","agarlagenhet"):
        return "Ägarlägenhet"
    if value in ("annat","vet ej","okänd","okant",""):
        return "Vet ej"
    return raw

def housing_route(case):
    home=normalize_home_type(case.get("home"))
    if home=="Bostadsrätt":
        brf=case.get("brf_genuine")
        private=case.get("used_as_private_home")
        if brf=="Nej":
            return {"route":"special","form":"Specialkontroll","status":"block","reason":"Bostadsrätten verkar kunna vara ett specialfall och ska inte behandlas som vanlig privatbostadsrätt."}
        if private=="Nej":
            return {"route":"special","form":"Specialkontroll","status":"block","reason":"Bostaden verkar inte vara en vanlig privatbostad. Bovinst behöver särskild hantering."}
        if brf not in ("Ja","Nej") or private not in ("Ja","Nej"):
            return {"route":"K6","form":"K6","status":"needs_check","reason":"Bovinst kan förbereda K6-spåret men en kontrollfråga återstår."}
        return {"route":"K6","form":"K6","status":"ok","reason":"Vanlig privatbostadsrätt."}
    if home in ("Småhus","Ägarlägenhet"):
        private=case.get("used_as_private_home")
        if private=="Nej":
            return {"route":"special","form":"Specialkontroll","status":"block","reason":"Bostaden verkar inte vara en vanlig privatbostad. Bovinst behöver särskild hantering."}
        if private not in ("Ja","Nej"):
            return {"route":"K5","form":"K5","status":"needs_check","reason":"Bovinst kan förbereda K5-spåret men en kontrollfråga återstår."}
        return {"route":"K5","form":"K5","status":"ok","reason":"Småhus/ägarlägenhet som privatbostad."}
    return {"route":"unknown","form":"Inte valt","status":"block","reason":"Bovinst behöver veta vilken typ av bostad som har sålts."}

def housing_questions(case):
    home=normalize_home_type(case.get("home"))
    q=[]
    if home in ("Småhus","Bostadsrätt","Ägarlägenhet"):
        q.append(("used_as_private_home","Har bostaden huvudsakligen varit din eller närståendes privatbostad?"))
    if home=="Bostadsrätt":
        q.append(("brf_genuine","Är det en vanlig privatbostadsrätt i en privatbostadsförening?"))
    return q

def smart_deduction_checks(case, costs):
    """Lagliga kontrollpunkter som ofta missas. Inga aggressiva skatteantaganden."""
    home=case.get("home")
    checks=[]
    if home!="Bostadsrätt":
        checks.append(("Köpkostnader","Kontrollera lagfart, stämpelskatt och egna kostnader för pantbrev/inteckning vid köpet."))
    else:
        checks.append(("Föreningens uppgifter","Kontrollera kapitaltillskott och eventuell inre reparationsfond från bostadsrättsföreningens kontrolluppgift."))

    checks.extend([
        ("Försäljningskostnader","Kontrollera mäklare, juridisk hjälp, värdering, besiktning, dolda-fel-försäkring, energideklaration och försäljningsresor."),
        ("Homestyling","Konsultation, fotografering, hyra och magasinering inför visning kan vara relevant. Vanlig städning, flytt och inköp av möbler är privata kostnader."),
        ("Bättre material","Ett byte till väsentligt bättre/dyrare material kan behöva delas: merkostnaden kan vara grundförbättring även när arbetet ligger långt tillbaka."),
        ("Teknisk utveckling","Nyare teknik är inte automatiskt en grundförbättring. Ett normalt modernt utbyte kan fortfarande vara reparation/underhåll."),
        ("Gamla grundförbättringar","Ny-, till- och ombyggnad eller ny utrustning som inte fanns tidigare kan vara relevant långt tillbaka i tiden, med lagens historiska gränser."),
        ("Saknat kvitto","Avsaknad av kvitto betyder inte att projektet ska glömmas. Samla alternativa spår och låt beloppet vara osäkert tills det kan stödjas."),
    ])
    return checks

def eligible_year_total(costs, sale_year, home=None):
    """
    Summerar endast poster som klarar grundläggande individuell behörighet
    innan 5 000-kronorsgränsen testas. Osäkra/obehöriga poster ska inte
    hjälpa andra poster över årsgränsen.
    """
    totals={}
    for c in costs:
        if c.get("inactive"): continue
        amount=float(c.get("amount") or 0)
        if amount<=0: continue
        year=int(c.get("year") or sale_year)
        if year>sale_year: continue
        if c.get("self_labor"): continue
        kind=classify_from_answers(c)
        if kind=="repair":
            if year < sale_year-5: continue
            if c.get("improved") is False: continue
        if kind=="basic":
            if home=="Bostadsrätt" and year<1974: continue
            if home!="Bostadsrätt" and year<1952: continue
        net=max(0.0,amount-float(c.get("rot") or 0)-float(c.get("insurance") or 0))
        if net>0: totals[year]=totals.get(year,0)+net
    return totals

def timeline_periods(case):
    buy=int(case.get("buyyear") or case.get("purchase_year") or 0)
    sell=int(case.get("sellyear") or 0)
    if buy<=0 or sell<=0 or sell<buy:
        return []
    span=sell-buy
    if span<=5:
        return [(y,y) for y in range(buy,sell+1)]
    step=5 if span<=20 else 10
    periods=[]
    start=buy
    while start<=sell:
        end=min(start+step-1,sell)
        periods.append((start,end))
        start=end+1
    return periods

def period_label(period):
    a,b=period
    return str(a) if a==b else f"{a}–{b}"

def timeline_summary(case):
    periods=timeline_periods(case)
    answers=case.get("timeline_answers",{}) or {}
    reviewed=0
    yes=0
    unknown=0
    for p in periods:
        key=f"{p[0]}_{p[1]}"
        val=answers.get(key)
        if explicit_answer(val):
            reviewed+=1
        if val=="Ja":
            yes+=1
        elif val=="Vet ej":
            unknown+=1
    return {
        "total":len(periods),
        "reviewed":reviewed,
        "yes":yes,
        "unknown":unknown,
        "remaining":max(len(periods)-reviewed,0),
    }

def duplicate_candidates(costs):
    """
    Försiktig dublettsignal. Markerar kandidater men slår aldrig ihop automatiskt.
    """
    out=[]
    active=[(i,c) for i,c in enumerate(costs) if not c.get("inactive")]
    for pos,(i,a) in enumerate(active):
        for j,b in active[pos+1:]:
            na=(a.get("name") or "").strip().lower()
            nb=(b.get("name") or "").strip().lower()
            if not na or not nb:
                continue

            same_source = a.get("hunt_source") and a.get("hunt_source")==b.get("hunt_source")
            same_name = na==nb
            years_close = abs(int(a.get("year") or 0)-int(b.get("year") or 0))<=1
            aa=float(a.get("amount") or 0)
            ba=float(b.get("amount") or 0)
            if aa and ba:
                amount_close=abs(aa-ba) <= max(5000, 0.15*max(aa,ba))
            else:
                amount_close=True

            score=0
            reasons=[]
            if same_source:
                score+=3; reasons.append("samma område i Avdragsjakten")
            if same_name:
                score+=3; reasons.append("samma projektnamn")
            if years_close:
                score+=2; reasons.append("samma eller närliggande år")
            if amount_close:
                score+=1; reasons.append("liknande eller okänt belopp")

            if score>=5:
                out.append({
                    "i":i,"j":j,"score":score,
                    "reasons":reasons,
                    "a":a.get("name","Projekt"),"b":b.get("name","Projekt")
                })
    return sorted(out,key=lambda x:-x["score"])

def discovery_areas_for_home(home_type):
    common=[
        ("sale_costs","Försäljningen","Mäklare, fotografering, annonsering, besiktning, energideklaration, homestyling eller juridisk hjälp."),
        ("kitchen","Kök","Nytt kök, luckor, bänkskiva, vitvaror, flytt av kök, el eller rör."),
        ("bathroom","Badrum och toalett","Renovering, nytt badrum, tätskikt, dusch, toalett eller flytt av funktioner."),
        ("surface","Ytskikt","Målning, tapetsering, golv, innertak eller andra ytskikt."),
        ("systems","Värme, el, VVS och ventilation","Värmepump, elcentral, ledningar, rör, ventilation eller andra tekniska system."),
        ("layout","Planlösning och ombyggnad","Flyttade väggar, byggde om, skapade nya rum eller ändrade användningen av ytor."),
    ]
    if home_type=="Bostadsrätt":
        return common + [
            ("storage_balcony","Balkong, uteplats och förråd","Inglasning, förbättring av uteplats eller förråd om det hör till bostadsrätten."),
            ("brf","Föreningens uppgifter","Kapitaltillskott och inre reparationsfond kan behövas till deklarationen."),
        ]
    return common + [
        ("windows_roof","Tak, fönster och fasad","Takbyte, fönsterbyte, fasad, målning eller tilläggsisolering."),
        ("drainage","Dränering och grund","Dränering, fuktskydd, grundarbete eller källararbete."),
        ("outside","Tomt och uteplats","Altan, markarbete, murar, gångar eller andra större arbeten."),
        ("garage","Garage, carport och förråd","Nybyggnad, tillbyggnad eller större ombyggnad."),
        ("water_sewer","Vatten och avlopp","Brunn, avlopp, servis, vattenledning eller större VA-arbeten."),
        ("purchase_costs","Köpet av bostaden","Till exempel lagfart, pantbrev eller andra kända kostnader vid köpet."),
    ]

def explicit_answer(value):
    """Endast ett faktiskt användarsvar räknas som svarat."""
    return value in ("Ja","Nej","Vet ej")

def unanswered_label():
    return "Välj ett svar"

def coverage_summary(case):
    areas=discovery_areas_for_home(case.get("home"))
    answers=case.get("hunt_answers",{}) or {}
    reviewed=sum(1 for key,_,_ in areas if explicit_answer(answers.get(key)))
    yes=sum(1 for key,_,_ in areas if answers.get(key)=="Ja")
    unknown=sum(1 for key,_,_ in areas if answers.get(key)=="Vet ej")
    return {"total":len(areas),"reviewed":reviewed,"yes":yes,"unknown":unknown,"remaining":max(len(areas)-reviewed,0)}

def project_from_hunt(key, label, followup, sale_year):
    """
    Skapa en ofullständig kostnadspost direkt från Avdragsjakten.
    Syftet är att användaren inte ska behöva mata in samma projekt två gånger.
    """
    mapping={
        "kitchen":"Renoverade kök",
        "bathroom":"Renoverade badrum",
        "surface":"Målade eller tapetserade",
        "windows_roof":"Tak, fönster eller fasad",
        "systems":"Värme, el, VVS eller ventilation",
        "layout":"Byggde om eller ändrade planlösningen",
        "outside":"Utomhusarbete eller tomt",
        "storage_balcony":"Balkong, uteplats eller förråd",
        "drainage":"Dränering eller grund",
        "garage":"Garage, carport eller förråd",
        "water_sewer":"Vatten eller avlopp",
    }
    name=mapping.get(key,label)
    when=followup.get("when")
    year=followup.get("year_hint")
    if year is None:
        year=int(sale_year)

    paid=followup.get("paid")
    amount=float(followup.get("amount_hint") or 0)
    if paid=="Ja, ganska exakt":
        amount_quality="exact"
    elif paid=="Ja, ungefär":
        amount_quality="approx"
    else:
        amount_quality="unknown"
        amount=0.0

    docs=followup.get("docs")
    if docs=="Ja":
        evidence_level="Vet ej"
        evidence=False
    elif docs=="Nej":
        evidence_level="Inget underlag just nu"
        evidence=False
    else:
        evidence_level="Vet ej"
        evidence=False

    # Klassificeringsfrågor är ännu inte besvarade i jakten.
    return {
        "name":name,
        "work_type":"Renovering eller arbete på bostaden",
        "year":int(year),
        "year_quality":"exact" if when=="Jag vet årtalet" else "approx" if when=="Jag vet ungefär perioden" else "unknown",
        "period_hint":followup.get("period_hint"),
        "amount":amount,
        "amount_quality":amount_quality,
        "rot":0.0,
        "rot_known":False if int(year)>=2009 else False,
        "rot_answer":"Vet ej",
        "evidence_level":evidence_level,
        "evidence_types":[],
        "evidence":evidence,
        "existed_before":None,
        "changed_layout": True if key=="layout" else False,
        "added_new":False,
        "improved":None,
        "note":"Skapad automatiskt från Avdragsjakten.",
        "hunt_source":key,
        "hunt_generated":True,
        "hunt_label":label,
        "draft":True,
    }

def find_hunt_project(costs, key):
    for i,c in enumerate(costs):
        if c.get("hunt_source")==key and c.get("hunt_generated"):
            return i
    return None

def uncertainty_tasks(case, costs):
    tasks=[]
    sale_year=int(case.get("sellyear",2026) or 2026)
    hunt_answers=case.get("hunt_answers",{}) or {}
    hunt_followups=case.get("hunt_followups",{}) or {}

    for key,answer in hunt_answers.items():
        if answer=="Vet ej":
            tasks.append({"priority":2,"kind":"discovery","title":"Ta reda på om något gjordes inom området","text":"Sök gamla foton, mejl, kontoutdrag eller fråga eventuell medägare/familjemedlem. Målet är först bara att avgöra om ett projekt fanns.","source_key":key})

    for key,f in hunt_followups.items():
        if not isinstance(f,dict):
            continue
        if f.get("when")=="Vet ej":
            tasks.append({"priority":1,"kind":"date","title":"Försök tidsbestämma projektet","text":"Årtalet kan påverka vilka regler som gäller. Börja med foton, mejl, bygglov, garantibevis eller bankutdrag.","source_key":key})
        if f.get("paid") in ("Nej","Vet ej"):
            tasks.append({"priority":2,"kind":"amount","title":"Försök återskapa kostnaden","text":"Sök betalningar, lån, offerter, fakturor eller större uttag. Om exakt belopp inte går att hitta kan andra underlag fortfarande hjälpa.","source_key":key})
        if f.get("docs")=="Vet ej":
            tasks.append({"priority":3,"kind":"evidence","title":"Kontrollera om något underlag finns","text":"Sök brett: bank, mejl, bilder, molnlagring, gamla datorer och pärmar.","source_key":key})

    for idx,c in enumerate(costs):
        name=c.get("name",f"Projekt {idx+1}")
        year=int(c.get("year") or sale_year)
        if c.get("amount_quality")=="unknown":
            tasks.append({"priority":1,"kind":"amount","title":f"Återskapa kostnaden för {name}","text":"Börja med bankutdrag, lån, offerter och gamla fakturor. Bovinst ska inte hitta på ett belopp.","cost_index":idx})
        elif c.get("amount_quality")=="approx":
            tasks.append({"priority":2,"kind":"amount","title":f"Stärk beloppet för {name}","text":"Du har ett ungefärligt belopp. Leta efter något som kan snäva in summan eller stödja omfattningen.","cost_index":idx})
        if c.get("evidence_level") in ("Vet ej","Inget underlag just nu",None) and not c.get("evidence"):
            tasks.append({"priority":2,"kind":"evidence","title":f"Hitta spår för {name}","text":"Kontrollera foton, ritningar, bygglov, bankutdrag, lånehandlingar, mejl/SMS och garantibevis.","cost_index":idx})
        if c.get("rot_known") is False and year>=2009:
            tasks.append({"priority":1,"kind":"rot","title":f"Kontrollera ROT för {name}","text":"Kontrollera gammal faktura eller dina uppgifter hos Skatteverket så att Bovinst inte räknar med fel nettokostnad.","cost_index":idx})
        if c.get("existed_before") is None:
            tasks.append({"priority":2,"kind":"baseline","title":f"Ta reda på vad som fanns före {name}","text":"Gamla objektsbilder, prospekt eller foton från köpet kan hjälpa.","cost_index":idx})
        if c.get("improved") is None and classify_from_answers(c)=="repair":
            tasks.append({"priority":1,"kind":"condition","title":f"Kontrollera skicket vid försäljningen för {name}","text":"För reparation och underhåll behöver Bovinst veta om bostaden fortfarande var i bättre skick tack vare arbetet jämfört med när du köpte.","cost_index":idx})

    seen=set()
    out=[]
    for t in sorted(tasks,key=lambda x:(x["priority"],x["title"])):
        ident=(t["title"],t.get("cost_index"),t.get("source_key"))
        if ident not in seen:
            seen.add(ident)
            out.append(t)
    return out

def declaration_summary(case,costs):
    sale=float(case.get("sell",0) or 0)
    buy=float(case.get("buy",0) or 0)
    sy=int(case.get("sellyear",2026) or 2026)
    home=case.get("home")
    sale_costs=0.0
    improvements=0.0
    active_costs=[c for c in costs if not c.get("inactive")]
    for c in active_costs:
        r=assess(c,sy,active_costs,home=home)
        if r.deductible_amount<=0:
            continue
        if classify_from_answers(c)=="sale":
            sale_costs+=r.deductible_amount
        else:
            improvements+=r.deductible_amount
    total=sale_costs+improvements
    return {
        "sale_price":sale,
        "purchase_price":buy,
        "sale_costs":sale_costs,
        "improvements":improvements,
        "deductions_considered":total,
        "preliminary_gain":sale-buy-total
    }

def completeness_checks(case,costs):
    out=[]
    home=case.get("home")
    acquisition=case.get("acquisition")
    sale=float(case.get("sell",0) or 0)
    buy=float(case.get("buy",0) or 0)
    sy=int(case.get("sellyear",2026) or 2026)

    if sale<=0:
        out.append({"level":"blocker","title":"Försäljningspriset saknas","text":"Fyll i priset som stod i köpekontraktet."})
    if acquisition=="Köpte den" and buy<=0:
        out.append({"level":"blocker","title":"Inköpspriset saknas","text":"Fyll i vad du betalade när du köpte bostaden."})
    if acquisition and acquisition!="Köpte den":
        out.append({"level":"blocker","title":"Bostaden kom till dig på annat sätt än genom vanligt köp","text":"Arv, gåva, testamente och bodelning kan kräva andra uppgifter om anskaffningsvärdet."})
    if home=="Bostadsrätt" and not case.get("genuine_br",True):
        out.append({"level":"blocker","title":"Bostadsrättens typ behöver kontrolleras","text":"En oäkta bostadsrätt deklareras annorlunda. Bovinst använder därför inte vanlig K6-logik här."})

    for c in costs:
        r=assess(c,sy,costs,home=home)
        if r.confidence=="low":
            out.append({"level":"warning","title":f"{c.get('name','En kostnad')} behöver kontrolleras","text":r.plain_summary})
        elif r.missing:
            out.append({"level":"warning","title":f"Underlag eller uppgift saknas för {c.get('name','en kostnad')}","text":r.missing[0]})

    if home=="Bostadsrätt":
        # v0.5+ can capture these, but zero can be a valid actual value. We therefore
        # ask user to confirm source rather than assuming missing solely from zero.
        if not case.get("brf_values_confirmed",False):
            out.append({"level":"warning","title":"Föreningens uppgifter behöver bekräftas","text":"Kontrollera kapitaltillskott och eventuell inre reparationsfond mot kontrolluppgiften från bostadsrättsföreningen."})
    return out

def k5_rows(case,costs):
    dr=declaration_ready_summary(case,costs)
    purchase_extra=float(case.get("purchase_extra",0) or 0)
    purchase_total=float(case.get("buy",0) or 0)+purchase_extra
    gain=(
        float(case.get("sell",0) or 0)
        -dr["sale_expenses"]
        -purchase_total
        -dr["basic"]
        -dr["repair"]
    )
    return [
        ("K5 punkt 1","Försäljningspris",float(case.get("sell",0) or 0)),
        ("K5 punkt 2","Utgifter för försäljningen",dr["sale_expenses"]),
        ("K5 punkt 3","Inköpspris, lagfartskostnad m.m.",purchase_total),
        ("K5 punkt 4","Grundförbättringar / ny-, till- eller ombyggnad",dr["basic"]),
        ("K5 punkt 5","Förbättrande reparationer och underhåll",dr["repair"]),
        ("K5 punkt 6","Vinst eller förlust före ägarandel och uppskov",gain),
    ]

def k6_rows(case,costs):
    dr=declaration_ready_summary(case,costs)
    capital=float(case.get("capital_contribution",0) or 0)
    fund_sale=float(case.get("fund_sale",0) or 0)
    fund_buy=float(case.get("fund_buy",0) or 0)
    purchase=float(case.get("buy",0) or 0)
    gain=(
        float(case.get("sell",0) or 0)
        -dr["sale_expenses"]
        -purchase
        -dr["basic"]
        -dr["repair"]
        -capital
        -fund_sale
        +fund_buy
    )
    return [
        ("K6 punkt 1","Försäljningspris",float(case.get("sell",0) or 0)),
        ("K6 punkt 2","Försäljningsutgifter",dr["sale_expenses"]),
        ("K6 punkt 3","Inköpspris m.m.",purchase),
        ("K6 punkt 4","Grundförbättringar / ny-, till- eller ombyggnad",dr["basic"]),
        ("K6 punkt 5","Förbättrande reparationer och underhåll",dr["repair"]),
        ("K6 punkt 6","Kapitaltillskott",capital),
        ("K6 punkt 7","Andel av inre reparationsfond vid försäljningen",fund_sale),
        ("K6 punkt 8","Andel av inre reparationsfond vid köpet",fund_buy),
        ("K6 punkt 9","Vinst eller förlust före ägarandel och uppskov",gain),
    ]

def declaration_delivery(case,costs):
    """
    Skapar en försiktig slutleverans. 'ready' betyder att Bovinsts egna kontroller
    inte hittar kvarvarande blockerare; det är inte en myndighetsgaranti.
    """
    route=housing_route(case)
    home=normalize_home_type(case.get("home"))
    form=route.get("form","Inte valt")
    rows=k6_rows(case,costs) if form=="K6" else k5_rows(case,costs) if form=="K5" else []

    readiness=readiness_summary(case,costs)
    coverage=coverage_summary(case)
    timeline=timeline_summary(case)
    duplicates=duplicate_candidates(costs)
    checks=completeness_checks(case,costs)
    miss=money_miss_checks(case,costs)

    blockers=[]
    warnings=[]

    if route.get("status")=="block":
        blockers.append(route.get("reason","Bostadstypen behöver kontrolleras."))
    elif route.get("status")=="needs_check":
        warnings.append(route.get("reason","Bostadskontrollen behöver slutföras."))

    for item in checks:
        text=f"{item.get('title','Kontroll')}: {item.get('text','')}".strip()
        if item.get("level")=="blocker":
            blockers.append(text)
        else:
            warnings.append(text)

    if duplicates:
        blockers.append(f"{len(duplicates)} möjlig(a) dublett(er) behöver kontrolleras.")
    if coverage.get("reviewed",0)<coverage.get("total",0):
        warnings.append("Avdragsminnet är inte helt genomgånget.")
    elif coverage.get("unknown",0)>0:
        warnings.append(f"{coverage['unknown']} område(n) i Avdragsminnet är fortfarande Vet ej.")
    if timeline.get("total",0) and timeline.get("reviewed",0)<timeline.get("total",0):
        warnings.append("Tidslinjen är inte helt genomgången.")
    if readiness.get("needs_info",0)>0:
        blockers.append(f"{readiness['needs_info']} projekt behöver kompletteras.")
    if readiness.get("needs_evidence",0)>0:
        warnings.append(f"{readiness['needs_evidence']} projekt behöver stärkt underlag.")
    if readiness.get("threshold_pending",0)>0:
        warnings.append(f"{readiness['threshold_pending']} projekt väntar på 5 000-kronorsgränsen för sitt år.")
    if miss:
        high=sum(1 for x in miss if x.get("priority")==1)
        if high:
            warnings.append(f"{high} viktig(a) 'Missar du pengar?'-kontroll(er) återstår.")

    # Dedupe while preserving order.
    blockers=list(dict.fromkeys(blockers))
    warnings=list(dict.fromkeys(warnings))

    share=float(case.get("share",100) or 100)/100.0
    raw_gain=rows[-1][2] if rows else 0.0
    own_gain=raw_gain*share

    status="Klar att föra över" if rows and not blockers and not warnings else (
        "Nästan klar" if rows and not blockers else "Inte klar"
    )

    return {
        "status":status,
        "form":form,
        "rows":rows,
        "blockers":blockers,
        "warnings":warnings,
        "owner_share":share,
        "gain_before_share":raw_gain,
        "owner_gain":own_gain,
        "ready_projects":readiness.get("ready",0),
        "active_projects":readiness.get("active",0),
        "home":home,
    }

def declaration_delivery_text(case,costs):
    d=declaration_delivery(case,costs)
    lines=[
        "BOVINST – DEKLARATIONSUNDERLAG",
        f"Status: {d['status']}",
        f"Bilaga: {d['form']}",
        "",
        "FYLL I SÅ HÄR",
    ]
    for point,label,value in d["rows"]:
        lines.append(f"{point} – {label}: {value:,.0f} kr".replace(","," "))
    lines += [
        "",
        f"Ägarandel: {d['owner_share']*100:.0f} %",
        f"Vinst/förlust före ägarandel och uppskov: {d['gain_before_share']:,.0f} kr".replace(","," "),
        f"Din andel: {d['owner_gain']:,.0f} kr".replace(","," "),
    ]
    if d["blockers"]:
        lines += ["","MÅSTE LÖSAS FÖRST"]
        lines += [f"- {x}" for x in d["blockers"]]
    if d["warnings"]:
        lines += ["","BÖR KONTROLLERAS"]
        lines += [f"- {x}" for x in d["warnings"]]
    lines += [
        "",
        "Obs: Bovinst är ett besluts- och sammanställningsstöd. Kontrollera uppgifterna innan de lämnas in."
    ]
    return "\n".join(lines)

def uppskov_screening(case,gain_for_owner):
    result={"eligible_hint":False,"type":None,"max_hint":0.0,"checks":[],"notes":[]}
    if gain_for_owner<=0:
        result["checks"].append("Det finns ingen positiv preliminär vinst att skjuta upp beskattningen av.")
        return result
    if case.get("permanent_home") is not True:
        result["checks"].append("Den sålda bostaden behöver normalt ha varit din permanentbostad.")
    if case.get("lived_rule") is not True:
        result["checks"].append("Bosättningstiden behöver kontrolleras: normalt minst ett år direkt före försäljningen eller minst tre av de senaste fem åren.")
    status=case.get("replacement_status")
    if status=="Köpt och inflyttad i tid":
        result["type"]="Slutligt uppskov kan vara möjligt"
    elif status in ("Inte köpt ännu","Köpt men inte flyttat in i tid"):
        result["type"]="Preliminärt uppskov kan vara möjligt"
    else:
        result["checks"].append("Bovinst behöver veta mer om den nya bostaden och datumen.")
    prior=float(case.get("prior_uppskov",0) or 0)
    if prior>0:
        result["notes"].append("Du har angett ett tidigare uppskov. Det behöver återföras i beräkningen innan ett nytt uppskov fastställs.")
    if gain_for_owner<50000:
        result["checks"].append("Din preliminära vinst är lägre än 50 000 kr, vilket normalt är under miniminivån för uppskov.")
    share=float(case.get("share",100) or 100)/100
    result["max_hint"]=min(max(gain_for_owner+prior,0),3000000.0*share)
    replacement=float(case.get("replacement_price",0) or 0)
    sold_owner=float(case.get("sold_price_owner",0) or 0)
    if replacement>0 and sold_owner>0:
        if replacement>=sold_owner:
            result["notes"].append("Den nya bostaden är minst lika dyr som din andel av den sålda bostaden.")
        else:
            result["notes"].append("Den nya bostaden verkar billigare. Uppskovet kan därför behöva begränsas enligt proportioneringsregeln.")
    result["eligible_hint"]=not result["checks"] and result["type"] is not None and gain_for_owner>=50000
    return result
