import streamlit as st
import uuid
from storage import save_local, load_local, delete_local
from rules import assess, classify_from_answers, declaration_summary, completeness_checks, k5_rows, k6_rows, uppskov_screening, evidence_label, uncertainty_tasks, project_from_hunt, find_hunt_project, discovery_areas_for_home, coverage_summary, timeline_periods, period_label, timeline_summary, duplicate_candidates, smart_deduction_checks, normalize_home_type, housing_route, housing_questions, money_miss_checks, money_miss_score, project_readiness, readiness_summary, project_recovery_plan, declaration_ready_summary, declaration_ready_costs, declaration_delivery, declaration_delivery_text, explicit_answer, unanswered_label, RULESET_VERSION, VERIFIED_DATE

st.set_page_config(page_title="Bovinst", page_icon="🏠", layout="wide")

st.markdown('''
<style>
.block-container{max-width:1100px;padding-top:1.4rem}
[data-testid="stMetric"]{border:1px solid color-mix(in srgb,currentColor 18%,transparent);border-radius:16px;padding:16px}
.bv-card{border:1px solid color-mix(in srgb,currentColor 18%,transparent);border-radius:16px;padding:16px 18px;margin:.4rem 0 1rem}
.bv-muted{opacity:.78}
</style>
''', unsafe_allow_html=True)

if "case" not in st.session_state: st.session_state.case={}
if "costs" not in st.session_state: st.session_state.costs=[]
if "case_id" not in st.session_state: st.session_state.case_id=str(uuid.uuid4())
if "last_saved" not in st.session_state: st.session_state.last_saved=None

def save_now():
    st.session_state.last_saved = save_local(
        st.session_state.case_id,
        st.session_state.case,
        st.session_state.costs
    )

def autosave():
    # Säkerhetsnät för prototypen. I Streamlit Community Cloud är lokal disk inte en
    # tillförlitlig permanent databas mellan omstarter/deploys.
    save_now()

def money(v): return f"{float(v):,.0f} kr".replace(","," ")

st.title("Bovinst")
st.caption("Hitta avdragen du riskerar att missa – utan att behöva kunna skatt eller deklaration.")
st.info("Bovinsts viktigaste jobb är att hjälpa dig hitta kostnader du annars riskerar att glömma – och sedan kontrollera hur de ska hanteras i deklarationen.")

with st.expander("Spara och fortsätt senare"):
    st.write(
        "Den här prototypversionen kan spara ett ärende lokalt som ett säkerhetsnät. "
        "På den publicerade Streamlit-appen är detta **inte** samma sak som säker molnlagring: "
        "lokala filer kan försvinna vid omstart eller ny deploy."
    )
    st.code(st.session_state.case_id, language=None)
    a_save,b_load,b_delete=st.columns(3)
    if a_save.button("Spara nu"):
        save_now()
        st.success("Ärendet sparades i den lokala prototypmiljön.")
    if b_load.button("Läs in sparat"):
        loaded=load_local(st.session_state.case_id)
        if loaded:
            st.session_state.case=loaded.get("case",{})
            st.session_state.costs=loaded.get("costs",[])
            st.session_state.last_saved=loaded.get("saved_at")
            st.success("Sparat ärende lästes in.")
            st.rerun()
        else:
            st.warning("Det finns inget lokalt sparat ärende med detta id.")
    if b_delete.button("Radera lokal kopia"):
        if delete_local(st.session_state.case_id):
            st.success("Den lokala kopian raderades.")
        else:
            st.info("Ingen lokal kopia fanns att radera.")
    if st.session_state.last_saved:
        st.caption(f"Senast sparad: {st.session_state.last_saved}")

tabs=st.tabs(["1 · Bostaden","2 · Avdragsjakten","3 · Dina kostnader","4 · Underlagsdetektiven","5 · Din deklaration","6 · Uppskov"])

with tabs[0]:
    st.header("Vi börjar med bostaden")
    a,b=st.columns(2)
    with a:
        home=st.selectbox("Vad var det för typ av bostad?",["Villa","Radhus","Parhus","Fritidshus","Ägarlägenhet","Bostadsrätt"])
        buy=st.number_input("Vad betalade du när du köpte bostaden?",min_value=0,step=10000)
        buyyear=st.number_input("Vilket år köpte du bostaden?",1900,2100,2015)
        acquisition=st.selectbox("Hur fick du bostaden?",["Köpte den","Arv","Gåva","Testamente","Bodelning","Annat"])
    with b:
        sell=st.number_input("Vad sålde du bostaden för?",min_value=0,step=10000)
        sellyear=st.number_input("Vilket år skrevs försäljningen?",1900,2100,2026)
        share=st.slider("Hur stor del av bostaden ägde du?",1,100,100,format="%d %%")
        genuine=True
        if home=="Bostadsrätt":
            br=st.radio("Var det en vanlig privatbostadsrätt?",["Ja","Nej / oäkta bostadsrätt","Vet inte"],horizontal=True)
            genuine=(br=="Ja")
    purchase_extra=0
    capital_contribution=0
    fund_sale=0
    fund_buy=0
    if home!="Bostadsrätt":
        purchase_extra=st.number_input(
            "Lagfart, pantbrev eller andra kostnader när du köpte",
            min_value=0,step=1000,
            help="Skriv bara kostnader du faktiskt känner till. Bovinst lägger dem tillsammans med inköpspriset i K5-guiden."
        )
    else:
        st.subheader("Uppgifter från bostadsrättsföreningen")
        st.write("De här uppgifterna brukar finnas i kontrolluppgiften eller materialet från föreningen.")
        capital_contribution=st.number_input("Kapitaltillskott",min_value=0,step=1000)
        fund_sale=st.number_input("Din andel av inre reparationsfond vid försäljningen",min_value=0,step=1000)
        fund_buy=st.number_input("Din andel av inre reparationsfond vid köpet",min_value=0,step=1000)
        brf_values_confirmed=st.checkbox("Jag har kontrollerat dessa uppgifter mot föreningens kontrolluppgift")

    st.session_state.case={
        "home":home,"buy":buy,"buyyear":int(buyyear),"sell":sell,"sellyear":int(sellyear),
        "share":int(share),"acquisition":acquisition,"genuine_br":genuine,
        "purchase_extra":float(purchase_extra),
        "capital_contribution":float(capital_contribution),
        "fund_sale":float(fund_sale),
        "fund_buy":float(fund_buy),
        "brf_values_confirmed": bool(brf_values_confirmed) if home=="Bostadsrätt" else False,
    }
    if acquisition!="Köpte den":
        st.warning("Bovinst sparar ärendet, men deklarationen kan inte kallas klar förrän rätt anskaffningsvärde har kontrollerats.")

with tabs[1]:
    st.header("Avdragsjakten")
    st.write(
        "Det viktigaste är att vi först hittar sådant du faktiskt har gjort eller betalat för. "
        "Du ska inte behöva komma ihåg skatteregler eller själv veta vad som är avdragsgillt."
    )
    st.info("**Vet ej är alltid ett tillåtet svar när du inte minns.** Bovinst ska hellre spara osäkerheten än tvinga fram ett gissat Ja eller Nej.")

    home_type = st.session_state.case.get("home", "Villa")
    st.subheader("Snabb genomgång")
    st.caption("Markera sådant som stämmer. Bovinst använder svaren som en minneslista och visar vad du bör gå vidare med.")

    st.subheader("Saker som är lätta att missa")
    st.caption("Det här är lagliga kontrollpunkter – inte kryphål. Bovinst ska hitta rätt avdrag, inte tänja på reglerna.")
    with st.expander("Visa smarta kontroller"):
        for title,text in smart_deduction_checks(st.session_state.case,st.session_state.costs):
            st.markdown(f"**{title}**")
            st.write(text)

    st.subheader("Bostadskontroll")
    st.write("Bovinst väljer deklarationsspår åt dig. Du behöver inte veta vad K5 eller K6 betyder.")
    home_map={
        "Villa/radhus/fritidshus":"Småhus",
        "Bostadsrätt":"Bostadsrätt",
        "Ägarlägenhet":"Ägarlägenhet",
        "Vet ej / annat":"Vet ej",
    }
    reverse_home={"Småhus":"Villa/radhus/fritidshus","Bostadsrätt":"Bostadsrätt","Ägarlägenhet":"Ägarlägenhet","Vet ej":"Vet ej / annat"}
    home_options=[unanswered_label(),"Villa/radhus/fritidshus","Bostadsrätt","Ägarlägenhet","Vet ej / annat"]
    saved_home=normalize_home_type(st.session_state.case.get("home"))
    default_home=reverse_home.get(saved_home,unanswered_label()) if st.session_state.case.get("home") else unanswered_label()
    home_choice=st.radio(
        "Vad har du sålt?",
        home_options,
        key="housing_type_choice",
        index=home_options.index(default_home)
    )
    if home_choice!=unanswered_label():
        st.session_state.case["home"]=home_map[home_choice]

    for key,label in housing_questions(st.session_state.case):
        current=st.session_state.case.get(key)
        options=[unanswered_label(),"Ja","Nej","Vet ej"]
        default=current if explicit_answer(current) else unanswered_label()
        answer=st.radio(
            label,options,
            horizontal=True,key=f"housing_{key}",
            index=options.index(default)
        )
        if answer!=unanswered_label():
            st.session_state.case[key]=answer

    route=housing_route(st.session_state.case)
    if route["status"]=="ok":
        st.success(f"Bovinst använder **{route['form']}**-spåret. {route['reason']}")
    elif route["status"]=="needs_check":
        st.info(f"Preliminärt spår: **{route['form']}**. {route['reason']}")
    else:
        st.warning(route["reason"])
    autosave()
    st.divider()

    score_preview=money_miss_score(st.session_state.case, st.session_state.costs)
    if score_preview["total"]:
        st.caption(f"Bovinst har just nu **{score_preview['total']}** saker kvar att dubbelkolla innan deklarationen är redo.")

    st.subheader("Avdragsminnet")
    st.write(
        "Gå igenom bostaden område för område. Svara bara vad du minns. "
        "Bovinst avgör senare vad som kan vara relevant skattemässigt."
    )
    home_type=st.session_state.case.get("home","Småhus")
    discovery=discovery_areas_for_home(home_type)
    st.caption(f"Frågorna är anpassade för: **{home_type}**")

    answers = dict(st.session_state.case.get("hunt_answers",{}) or {})
    st.caption("På varje fråga kan du svara **Ja**, **Nej** eller **Vet ej**. Inget räknas som genomgånget förrän du själv har valt ett svar.")
    for key, label, help_text in discovery:
        options=[unanswered_label(),"Ja","Nej","Vet ej"]
        current=answers.get(key)
        default=current if explicit_answer(current) else unanswered_label()
        answer=st.radio(
            label,
            options,
            horizontal=True,
            key=f"hunt_{key}",
            help=help_text,
            index=options.index(default)
        )
        if answer!=unanswered_label():
            answers[key]=answer
        else:
            answers.pop(key,None)

    selected = [(key,label) for key,label,_ in discovery if answers.get(key)=="Ja"]
    unknown = [(key,label) for key,label,_ in discovery if answers.get(key)=="Vet ej"]

    if selected:
        st.success(f"Du har hittat {len(selected)} område(n) att gå vidare med.")
    if unknown:
        st.info(f"{len(unknown)} område(n) är markerade som Vet ej. De sparas som kontrollpunkter i stället för att räknas som Nej.")

    # Adaptiva följdfrågor: bara för områden användaren sagt Ja till.
    followups={}
    for key,label in selected:
        with st.expander(f"Följdfrågor · {label}", expanded=len(selected)==1):
            if key in ("kitchen","bathroom","surface","windows_roof","systems","layout","outside","storage_balcony","drainage","garage","water_sewer"):
                when_options=[unanswered_label(),"Jag vet årtalet","Jag vet ungefär perioden","Vet ej"]
                when=st.radio(
                    "Ungefär när gjordes detta?",
                    when_options,
                    key=f"hunt_when_{key}",
                    index=0
                )
                year_hint=None
                period_hint=None
                if when=="Jag vet årtalet":
                    year_hint=st.number_input("År",1900,2100,int(st.session_state.case.get("sellyear",2026)),key=f"hunt_year_{key}")
                elif when=="Jag vet ungefär perioden":
                    period_hint=st.text_input("Skriv ungefär, till exempel 2015–2018 eller 'några år efter köpet'",key=f"hunt_period_{key}")

                paid_options=[unanswered_label(),"Ja, ganska exakt","Ja, ungefär","Nej","Vet ej"]
                paid=st.radio(
                    "Vet du ungefär vad projektet kostade?",
                    paid_options,
                    key=f"hunt_paid_{key}",
                    index=0
                )
                amount_hint=0.0
                if paid in ("Ja, ganska exakt","Ja, ungefär"):
                    amount_hint=st.number_input("Ungefärligt belopp",min_value=0,step=1000,key=f"hunt_amount_{key}")

                docs_options=[unanswered_label(),"Ja","Nej","Vet ej"]
                docs=st.radio(
                    "Har du något underlag kvar?",
                    docs_options,
                    horizontal=True,
                    key=f"hunt_docs_{key}",
                    index=0
                )
                followups[key]={
                    "when":when,"year_hint":year_hint,"period_hint":period_hint,
                    "paid":paid,"amount_hint":float(amount_hint),"docs":docs
                }

            elif key=="sale_costs":
                followups[key]={"note":"Gå vidare till Försäljningskostnad nedan. Du kan även svara Vet ej på underlaget."}
                st.write("Lägg in det du minns nedan. Du behöver inte känna till om kostnaden är avdragsgill.")
            elif key=="purchase_costs":
                st.write("Bovinst påminner dig senare om exempelvis lagfart och pantbrev. Om du inte vet beloppet nu kan det lämnas till senare.")
                followups[key]={"note":"purchase_costs"}
            elif key=="brf":
                st.write("Om du inte har kontrolluppgiften från föreningen nu är det okej. Bovinst markerar den som något att hämta senare.")
                followups[key]={"note":"brf"}

    st.session_state.case["hunt_answers"]=answers
    st.session_state.case["hunt_followups"]=followups

    # Skapa/uppdatera projekt automatiskt för renoveringsområden som användaren svarat Ja på.
    generated_count=0
    for key,label in selected:
        if key not in ("kitchen","bathroom","surface","windows_roof","systems","layout","outside","storage_balcony","drainage","garage","water_sewer"):
            continue
        f=followups.get(key)
        if not isinstance(f,dict):
            continue
        if f.get("when")==unanswered_label() and f.get("paid")==unanswered_label() and f.get("docs")==unanswered_label():
            continue
        draft=project_from_hunt(key,label,f,int(st.session_state.case.get("sellyear",2026)))
        idx=find_hunt_project(st.session_state.costs,key)
        if idx is None:
            st.session_state.costs.append(draft)
            generated_count+=1
        else:
            # Behåll uppgifter användaren senare kompletterat manuellt.
            existing=st.session_state.costs[idx]
            if existing.get("draft",True):
                st.session_state.costs[idx]={**existing,**draft}

    # Om användaren ändrar ett tidigare Ja till Nej tar vi inte bort en eventuell
    # kompletterad post automatiskt. Vi markerar bara utkastet som inaktivt.
    for key,label,_ in discovery:
        if answers.get(key)=="Nej":
            idx=find_hunt_project(st.session_state.costs,key)
            if idx is not None and st.session_state.costs[idx].get("draft",True):
                st.session_state.costs[idx]["inactive"]=True
        elif answers.get(key)=="Ja":
            idx=find_hunt_project(st.session_state.costs,key)
            if idx is not None:
                st.session_state.costs[idx]["inactive"]=False

    autosave()
    if generated_count:
        st.success(f"Bovinst skapade automatiskt {generated_count} projektutkast. Du slipper lägga in samma projekt en gång till.")

    coverage=coverage_summary(st.session_state.case)
    st.subheader("Hur långt har du kommit?")
    st.progress(coverage["reviewed"]/coverage["total"] if coverage["total"] else 0.0)
    st.write(
        f"Du har gått igenom **{coverage['reviewed']} av {coverage['total']} områden**. "
        f"Du har hittat något i **{coverage['yes']}** och svarat Vet ej i **{coverage['unknown']}**."
    )
    if coverage["remaining"]>0:
        st.caption("Bovinst säger inte att allt är hittat förrän alla relevanta områden har gåtts igenom.")
    elif coverage["unknown"]>0:
        st.info("Alla områden är genomgångna, men några svar är fortfarande Vet ej och behöver följas upp.")
    else:
        st.success("Alla relevanta områden är genomgångna. Nästa steg är att kontrollera projekten och underlaget.")

    st.divider()
    st.subheader("Minns du något mer om åren mellan köp och försäljning?")
    periods=timeline_periods(st.session_state.case)
    if not periods:
        st.info("När köpår och försäljningsår är ifyllda kan Bovinst hjälpa dig gå igenom tiden period för period.")
    else:
        st.write(
            "Tidslinjen är ett extra minnesstöd. Den ska fånga projekt som inte dök upp när du tänkte rum för rum."
        )
        timeline_answers=st.session_state.case.get("timeline_answers",{}) or {}
        timeline_notes=st.session_state.case.get("timeline_notes",{}) or {}
        for p in periods:
            pkey=f"{p[0]}_{p[1]}"
            options=[unanswered_label(),"Ja","Nej","Vet ej"]
            current=timeline_answers.get(pkey)
            default=current if explicit_answer(current) else unanswered_label()
            ans=st.radio(
                f"Gjordes något större i bostaden under {period_label(p)}?",
                options,
                horizontal=True,
                key=f"timeline_{pkey}",
                index=options.index(default)
            )
            if ans!=unanswered_label():
                timeline_answers[pkey]=ans
            else:
                timeline_answers.pop(pkey,None)
            if ans=="Ja":
                note=st.text_input(
                    "Vad minns du? Skriv fritt, till exempel 'värmepump och målning'.",
                    value=timeline_notes.get(pkey,""),
                    key=f"timeline_note_{pkey}"
                )
                timeline_notes[pkey]=note
        st.session_state.case["timeline_answers"]=timeline_answers
        st.session_state.case["timeline_notes"]=timeline_notes
        autosave()

        ts=timeline_summary(st.session_state.case)
        st.progress(ts["reviewed"]/ts["total"] if ts["total"] else 0.0)
        st.caption(
            f"Tidslinje: {ts['reviewed']} av {ts['total']} perioder genomgångna · "
            f"{ts['yes']} med något du minns · {ts['unknown']} Vet ej."
        )

    st.divider()
    st.subheader("Lägg till något själv")
    st.write("Det här är en reservväg om något inte passar in i Avdragsminnet. Du ska normalt inte behöva skriva in samma projekt igen.")
    work=st.selectbox("Vad vill du lägga till?",["Renovering eller arbete på bostaden","Försäljningskostnad"])
    if work=="Försäljningskostnad":
        name=st.selectbox("Vad betalade du för?",["Mäklararvode","Fotografering","Annonsering","Besiktning","Energideklaration","Homestyling","Juridisk hjälp","Annat"])
        year=st.number_input("Vilket år betalade du?",1900,2100,int(st.session_state.case.get("sellyear",2026)),key="sale_y")
        amount=st.number_input("Hur mycket betalade du?",min_value=0,step=1000,key="sale_a")
        ev=st.selectbox("Vad har du som stöd?",["Kvitto/faktura och betalning","Kvitto eller faktura","Bankutdrag/betalning","Annat underlag","Inget underlag just nu","Vet ej"],key="sale_ev")
        note=st.text_area("Vill du skriva något mer? Det är frivilligt.",key="sale_n")
        if st.button("Spara kostnaden",type="primary",key="save_sale"):
            st.session_state.costs.append({"name":name,"work_type":"Försäljningskostnad","year":int(year),"amount":float(amount),"rot":0.0,"evidence_level":ev,"evidence":ev not in ("Inget underlag just nu","Vet ej"),"existed_before":None,"changed_layout":False,"added_new":False,"improved":None,"note":note})
            autosave()
            st.rerun()
    else:
        name=st.selectbox("Vad gjorde du?",["Renoverade badrum","Renoverade kök","Bytte tak","Bytte fönster","Dränerade huset","Installerade eller bytte värmesystem","Gjorde elarbete","Gjorde VVS-arbete","Byggde till","Ändrade planlösningen","Byggde garage eller carport","Målade eller tapetserade","Annat"])
        year=st.number_input("Vilket år gjordes arbetet?",1900,2100,int(st.session_state.case.get("sellyear",2026)),key="reno_y")
        amount=st.number_input("Vad kostade det totalt?",min_value=0,step=1000,key="reno_a")
        rot=0.0
        rot_known=True
        if int(year)>=2009:
            rot_answer=st.radio(
                "Fick du ROT på fakturan?",
                ["Ja","Nej","Vet ej"],
                horizontal=True,
                key="reno_rot_answer"
            )
            if rot_answer=="Ja":
                rot=st.number_input("Hur mycket ROT drogs av? Om du inte vet exakt kan du skriva 0 och komplettera senare.",min_value=0,step=1000,key="reno_r")
            elif rot_answer=="Vet ej":
                rot_known=False
                st.info("Okej. Bovinst sparar att ROT behöver kontrolleras och räknar inte med någon okänd ROT-reduktion.")
        else:
            rot_answer="Vet ej"
            rot_known=False
            st.caption("För äldre arbeten använder Bovinst inte dagens ROT-regel automatiskt. Historiskt stöd behöver kontrolleras separat.")
        existed=st.radio("Fanns det som du arbetade med redan när du köpte bostaden?",["Ja","Nej","Vet inte"],horizontal=True)
        layout=st.checkbox("Jag flyttade väggar eller ändrade planlösningen")
        added=st.checkbox("Jag lade till något som inte fanns tidigare")
        improved=st.radio("När du sålde – var bostaden fortfarande bättre tack vare arbetet jämfört med när du köpte?",["Ja","Nej","Vet inte"],horizontal=True)
        st.subheader("Underlag – kvitto saknas ofta")
        st.caption(
            "Bovinst är byggd för verkligheten. Ett gammalt projekt får sparas även om kvittot är borta "
            "eller om du inte minns kostnaden exakt."
        )

        amount_quality_text=st.radio(
            "Hur säker är du på kostnaden ovan?",
            ["Jag vet beloppet ganska exakt","Beloppet är ungefärligt","Jag vet inte vad det kostade"],
            key="reno_amount_quality"
        )
        amount_quality_map={
            "Jag vet beloppet ganska exakt":"exact",
            "Beloppet är ungefärligt":"approx",
            "Jag vet inte vad det kostade":"unknown"
        }
        amount_quality_value=amount_quality_map[amount_quality_text]

        ev=st.selectbox(
            "Vad har du som stöd?",
            [
                "Kvitto/faktura och betalning",
                "Kvitto eller faktura",
                "Bankutdrag/betalning",
                "Foton/ritningar/bygglov eller annat",
                "Inget underlag just nu",
                "Vet ej"
            ],
            key="reno_ev"
        )

        evidence_types=[]
        if ev=="Foton/ritningar/bygglov eller annat":
            st.write("Markera det du har eller tror att du kan hitta:")
            for label in [
                "Foton före/efter","Ritningar eller bygglov","Bankutdrag",
                "Lånehandlingar","Offert eller avtal","Mejl eller SMS",
                "Garantibevis/manual","Annat"
            ]:
                if st.checkbox(label,key=f"alt_ev_{label}"):
                    evidence_types.append(label)
        elif ev in ("Inget underlag just nu","Vet ej"):
            st.info(
                "Spara ändå. Bovinst markerar underlaget som okänt och hjälper dig återkomma till det senare."
            )

        note=st.text_area("Beskriv gärna med egna ord vad som gjordes.",key="reno_n")
        if st.button("Spara och låt Bovinst bedöma",type="primary",key="save_reno"):
            st.session_state.costs.append({
                "name":name,
                "work_type":"Renovering eller arbete på bostaden",
                "year":int(year),
                "amount":0.0 if amount_quality_value=="unknown" else float(amount),
                "amount_quality":amount_quality_value,
                "rot":float(rot),
                "rot_known":bool(rot_known),
                "rot_answer":rot_answer,
                "evidence_level":ev,
                "evidence_types":evidence_types,
                "evidence":ev not in ("Inget underlag just nu","Vet ej","Foton/ritningar/bygglov eller annat"),
                "existed_before":True if existed=="Ja" else False if existed=="Nej" else None,
                "changed_layout":layout,
                "added_new":added,
                "improved":True if improved=="Ja" else False if improved=="Nej" else None,
                "note":note
            })
            autosave()
            st.rerun()

with tabs[2]:
    st.header("Dina kostnader")
    sy=int(st.session_state.case.get("sellyear",2026))
    if not st.session_state.costs:
        st.info("Du har inte lagt till någon kostnad ännu.")

    dups=duplicate_candidates(st.session_state.costs)
    if dups:
        st.warning(f"Bovinst ser {len(dups)} möjlig(a) dublett(er). Inget slås ihop automatiskt.")
        with st.expander("Kontrollera möjliga dubletter"):
            for d in dups:
                st.write(f"• **{d['a']}** och **{d['b']}** kan vara samma projekt – " + ", ".join(d["reasons"]) + ".")
            st.caption("Ta bara bort eller slå ihop poster när du själv är säker på att de avser samma kostnad.")

    for i,cost in enumerate(st.session_state.costs):
        r=assess(cost,sy,st.session_state.costs,home=st.session_state.case.get("home"))
        draft_badge=" · Utkast från Avdragsjakten" if cost.get("hunt_generated") and cost.get("draft",True) else ""
        inactive_badge=" · Inaktiv" if cost.get("inactive") else ""
        with st.expander(f"{cost['name']} · {money(cost['amount'])} · {r.status}{draft_badge}{inactive_badge}"):
            st.write(r.plain_summary)
            st.write(f"**Belopp som Bovinst just nu räknar som möjligt:** {money(r.deductible_amount)}")
            for x in r.reasons: st.write("✓",x)
            for x in r.missing: st.write("⚠",x)

            if cost.get("hunt_generated") and cost.get("draft",True) and not cost.get("inactive"):
                st.markdown("**Komplettera projektutkastet när du vill**")
                c1,c2=st.columns(2)
                new_year=c1.number_input("År",1900,2100,int(cost.get("year",sy)),key=f"draft_year_{i}")
                new_amount=c2.number_input("Belopp",min_value=0,step=1000,value=int(cost.get("amount",0)),key=f"draft_amount_{i}")
                aq=st.selectbox("Hur säker är du på beloppet?",["exact","approx","unknown"],index=["exact","approx","unknown"].index(cost.get("amount_quality","unknown")),format_func=lambda x:{"exact":"Ganska exakt","approx":"Ungefärligt","unknown":"Vet ej"}[x],key=f"draft_aq_{i}")
                existed=st.radio("Fanns detta redan när du köpte?",["Ja","Nej","Vet ej"],horizontal=True,key=f"draft_existed_{i}",index=2)
                improved=st.radio("Var bostaden fortfarande bättre tack vare arbetet när du sålde?",["Ja","Nej","Vet ej"],horizontal=True,key=f"draft_improved_{i}",index=2)
                if st.button("Spara kompletteringen",key=f"complete_draft_{i}"):
                    cost["year"]=int(new_year)
                    cost["amount"]=0.0 if aq=="unknown" else float(new_amount)
                    cost["amount_quality"]=aq
                    cost["existed_before"]=True if existed=="Ja" else False if existed=="Nej" else None
                    cost["improved"]=True if improved=="Ja" else False if improved=="Nej" else None
                    cost["draft"]=False if aq!="unknown" and existed!="Vet ej" and improved!="Vet ej" else True
                    autosave()
                    st.rerun()

            if st.button("Ta bort posten",key=f"del_{i}"):
                st.session_state.costs.pop(i); st.rerun()

with tabs[3]:
    st.header("Underlagsdetektiven 3.0")
    rs=readiness_summary(st.session_state.case,st.session_state.costs)
    st.write(
        f"**{rs['ready']} redo** · {rs['threshold_pending']} väntar på 5 000 kr/år · "
        f"{rs['needs_evidence']} behöver styrkas · {rs['needs_info']} behöver kompletteras · "
        f"{rs['blocked']} ska inte räknas med ännu."
    )
    if st.session_state.costs:
        st.subheader("Din plan projekt för projekt")
        for c in st.session_state.costs:
            if c.get("inactive"):
                continue
            plan=project_recovery_plan(st.session_state.case,c,st.session_state.costs)
            with st.expander(f"{plan['name']} — {plan['status']}"):
                for title,text in plan["steps"]:
                    st.markdown(f"**{title}**")
                    st.write(text)
        st.divider()
    st.write(
        "Många äldre renoveringar saknar kvitto eller faktura. Det betyder inte att projektet ska glömmas bort. "
        "Här samlar Bovinst vad du minns och visar vilka andra spår som kan hjälpa."
    )
    st.info(
        "Skatteverket anger att avdrag kan begäras även när kvitton saknas. "
        "Då behövs andra underlag som kan visa förbättringen, omfattningen och när arbetet gjordes. "
        "Bovinst hjälper dig samla detta men hittar aldrig på ett belopp."
    )

    sy=int(st.session_state.case.get("sellyear",2026))
    if not st.session_state.costs:
        st.info("Lägg först in sådant du minns under Avdragsjakten.")
    else:
        for i,cost in enumerate(st.session_state.costs):
            result=assess(cost,sy,st.session_state.costs,home=st.session_state.case.get("home"))
            with st.expander(f"{cost.get('name','Projekt')} · {evidence_label(cost)}"):
                st.write(f"**Underlagsstatus:** {evidence_label(cost)}")
                aq=cost.get("amount_quality","exact" if cost.get("amount") else "unknown")
                aq_label={"exact":"Ganska exakt belopp","approx":"Ungefärligt belopp","unknown":"Kostnad okänd"}.get(aq,"Okänd")
                st.write(f"**Kostnadsstatus:** {aq_label}")
                if cost.get("amount"):
                    st.write(f"Registrerat belopp: **{money(cost.get('amount',0))}**")

                ev_types=cost.get("evidence_types",[])
                if ev_types:
                    st.write("**Spår som redan finns:**")
                    for x in ev_types:
                        st.write("✓",x)

                st.write("**Vad du kan göra nu:**")
                q=evidence_label(cost)
                if cost.get("evidence_level")=="Vet ej":
                    st.write("• du har svarat Vet ej – börja med att kontrollera om något underlag alls finns")
                    st.write("• sök i bank, mejl, foton och gamla dokument utan att behöva veta exakt vad du letar efter")
                elif q=="Inget underlag just nu":
                    st.write("• sök bankutdrag runt året arbetet gjordes")
                    st.write("• leta efter gamla foton, ritningar eller bygglov")
                    st.write("• sök gamla mejl/SMS efter hantverkare eller butik")
                    st.write("• kontrollera om renoveringen finansierades med lån")
                    st.write("• försök identifiera företag, butik och ungefärlig tidsperiod")
                elif q=="Alternativt underlag":
                    st.write("• samla spåren på samma projekt")
                    st.write("• försök komplettera med betalning eller ytterligare daterat underlag")
                else:
                    st.write("• kontrollera att datum, belopp och vad arbetet avsåg går att följa")

                st.caption(result.plain_summary)

    st.subheader("Bovinsts plan för det du inte vet")
    tasks=uncertainty_tasks(st.session_state.case,st.session_state.costs)
    if not tasks:
        st.success("Just nu finns inga Vet ej-punkter eller andra tydliga luckor som Bovinst kan prioritera.")
    else:
        st.write("Bovinst prioriterar det som mest påverkar om en kostnad kan bedömas. Du behöver inte lösa allt på en gång.")
        labels={1:"Börja här",2:"Viktigt därefter",3:"Bra att kontrollera"}
        for task in tasks:
            with st.container(border=True):
                st.markdown(f"**{labels.get(task['priority'],'Att kontrollera')} · {task['title']}**")
                st.write(task["text"])

    with st.expander("Exempel på underlag när kvittot är borta"):
        st.write("• foton före och efter")
        st.write("• ritningar eller bygglov")
        st.write("• kontoutdrag eller lånehandlingar")
        st.write("• offert eller avtal")
        st.write("• gamla mejl eller SMS")
        st.write("• uppgift om företag eller butik")
        st.write("• garantibevis, manualer eller annan daterad dokumentation")
        st.caption(
            "Sådana underlag betyder inte automatiskt att ett visst belopp godtas. "
            "De kan hjälpa till att visa att arbetet gjordes, omfattningen och tidpunkten."
        )

with tabs[4]:
    st.header("Din deklaration")
    case=st.session_state.case
    summary=declaration_summary(case,st.session_state.costs)
    checks=completeness_checks(case,st.session_state.costs)
    home=case.get("home")
    if home=="Bostadsrätt":
        st.write("**Du har valt bostadsrätt.** För en vanlig privatbostadsrätt används normalt K6. K6 är bara namnet på bilagan där försäljningen redovisas.")
    else:
        st.write(f"**Du har valt {home or 'småhus'}.** För den här typen av privatbostad används normalt K5. K5 är bara namnet på bilagan där försäljningen redovisas.")
    a,b,c=st.columns(3)
    a.metric("Försäljningspris",money(summary["sale_price"]))
    b.metric("Möjliga kostnader hittills",money(summary["deductions_considered"]))
    c.metric("Preliminär vinst",money(summary["preliminary_gain"]))
    st.caption("Beloppen är preliminära tills slutkontrollen är grön.")
    route=housing_route(case)
    coverage=coverage_summary(case)
    timeline=timeline_summary(case)
    duplicates=duplicate_candidates(st.session_state.costs)
    st.subheader("Deklarationsklar totalsumma")
    dr=declaration_ready_summary(case,st.session_state.costs)
    c1,c2,c3=st.columns(3)
    c1.metric("Försäljningskostnader",f"{dr['sale_expenses']:,.0f} kr".replace(","," "))
    c2.metric("Grundförbättringar",f"{dr['basic']:,.0f} kr".replace(","," "))
    c3.metric("Reparation/underhåll",f"{dr['repair']:,.0f} kr".replace(","," "))
    st.metric("Summa deklarationsklara avdrag",f"{dr['total']:,.0f} kr".replace(","," "))
    st.caption(f"Endast projekt som klarar Bovinsts nuvarande deklarationskontroll ingår. Antal: {dr['ready_count']}.")
    if dr["threshold_pending"]:
        st.warning(
            f"{len(dr['threshold_pending'])} projekt är i övrigt klara men ligger i kalenderår "
            "där de kvalificerade förbättringsutgifterna ännu inte når 5 000 kr."
        )
        with st.expander("Visa projekt som väntar på 5 000-kronorsgränsen"):
            for item in dr["threshold_pending"]:
                st.write(f"• {item['year']} · {item['name']} · {item['amount']:,.0f} kr".replace(","," "))
    if not dr["ready_count"] and st.session_state.costs:
        st.info("Det finns registrerade projekt men inget deklarationsklart slutbelopp ännu. Bovinst visar därför 0 kr här.")

    st.subheader("Deklarationsberedskap")
    ready_summary=readiness_summary(case,st.session_state.costs)
    st.write(
        f"**{ready_summary['ready']} projekt redo att använda** · "
        f"{ready_summary['threshold_pending']} väntar på 5 000 kr/år · "
        f"{ready_summary['needs_evidence']} behöver styrkas · "
        f"{ready_summary['needs_info']} behöver kompletteras · "
        f"{ready_summary['blocked']} ska inte räknas med ännu."
    )
    if ready_summary["all_ready"]:
        st.success("Alla aktiva projekt är deklarationsredo enligt Bovinsts nuvarande kontroll.")
    elif ready_summary["active"]:
        st.info("Bovinst skiljer nu på projekt som är möjliga och projekt som faktiskt är redo att användas.")

    st.subheader("Missar du pengar?")
    miss_score=money_miss_score(case, st.session_state.costs)
    miss_tasks=money_miss_checks(case, st.session_state.costs)
    st.write(
        f"Status: **{miss_score['status']}** · "
        f"{miss_score['high']} viktiga · {miss_score['medium']} mellan · {miss_score['low']} lägre prioriterade kontroller."
    )
    if not miss_tasks:
        st.success("Bovinst hittar just nu inga uppenbara kvarvarande kontrollpunkter i avdragsjakten.")
    else:
        for task in miss_tasks:
            prefix="🔴" if task["priority"]==1 else ("🟠" if task["priority"]==2 else "🟡")
            with st.expander(f"{prefix} {task['title']}"):
                st.write(task["why"])
                st.markdown(f"**Gör så här:** {task['action']}")
        st.caption("Det här är en kontrollista för korrekta avdrag – inte en garanti för att varje post är avdragsgill.")

    st.divider()
    st.subheader("Slutkontroll")
    if route["status"]=="block":
        st.error("Bostadskontrollen är inte klar: " + route["reason"])
    elif route["status"]=="needs_check":
        st.warning("Bostadskontrollen har en kvarstående kontrollpunkt innan deklarationen kan räknas som färdig.")
    else:
        st.caption(f"Deklarationsspår: {route['form']}")
    if duplicates:
        st.warning(
            f"Bovinst ser {len(duplicates)} möjlig(a) dublett(er). Kontrollera dem innan slutbeloppen används."
        )
    if timeline["total"] and timeline["reviewed"] < timeline["total"]:
        st.info(
            f"Tidslinjen är inte helt genomgången: {timeline['reviewed']} av {timeline['total']} perioder."
        )

    if coverage["reviewed"] < coverage["total"]:
        st.warning(
            f"Avdragsminnet är inte färdigt: {coverage['reviewed']} av {coverage['total']} områden är genomgångna. "
            "Bovinst kan därför inte ännu säga att sökningen efter kostnader är komplett."
        )
    elif coverage["unknown"]>0:
        st.warning(
            f"Alla områden är genomgångna, men {coverage['unknown']} svar är Vet ej. "
            "De ska finnas kvar som kontrollpunkter."
        )
    blockers=[x for x in checks if x["level"]=="blocker"]
    warnings=[x for x in checks if x["level"]=="warning"]
    if blockers:
        st.error(f"{len(blockers)} sak behöver lösas innan Bovinst kan kalla sammanställningen deklarationsklar.")
        for x in blockers: st.markdown(f"**• {x['title']}**  \n{x['text']}")
    elif warnings:
        st.warning(f"{len(warnings)} sak behöver kontrolleras innan du för över beloppen.")
        for x in warnings: st.markdown(f"**• {x['title']}**  \n{x['text']}")
    else:
        st.success("Bovinst hittar inget mer som behöver kompletteras i de uppgifter du har lämnat.")
    st.subheader("Din deklarationsleverans")
    delivery=declaration_delivery(case,st.session_state.costs)
    if delivery["status"]=="Klar att föra över":
        st.success("Bovinsts kontroller är klara för de uppgifter du har lämnat. Du kan använda raderna nedan som underlag när du deklarerar.")
    elif delivery["status"]=="Nästan klar":
        st.warning("Beloppen är framräknade, men några kontroller återstår innan Bovinst rekommenderar att du för över dem.")
    else:
        st.error("Deklarationsleveransen är inte klar ännu. Lös punkterna nedan först.")

    a,b,c=st.columns(3)
    a.metric("Bilaga",delivery["form"])
    b.metric("Redo projekt",f"{delivery['ready_projects']} av {delivery['active_projects']}")
    c.metric("Din ägarandel",f"{delivery['owner_share']*100:.0f} %")

    if delivery["blockers"]:
        with st.expander("Måste lösas först",expanded=True):
            for text in delivery["blockers"]:
                st.write(f"• {text}")
    if delivery["warnings"]:
        with st.expander("Bör kontrolleras",expanded=delivery["status"]!="Klar att föra över"):
            for text in delivery["warnings"]:
                st.write(f"• {text}")

    delivery_text=declaration_delivery_text(case,st.session_state.costs)
    st.download_button(
        "Hämta deklarationsunderlaget som textfil",
        data=delivery_text,
        file_name=f"bovinst_deklarationsunderlag_{case.get('sellyear',2026)}.txt",
        mime="text/plain"
    )
    st.caption("Textfilen är en sammanställning för överföring och egen kontroll – inte en inskickad deklaration.")

    st.subheader("Fyll i så här")
    st.write(
        "Det här är Bovinsts översättning från dina svar till deklarationsbilagan. "
        "Du behöver inte kunna skatteorden – använd beloppen som kontrollstöd när du deklarerar."
    )

    rows=delivery["rows"]

    for point,label,value in rows:
        st.markdown(f"**{point} – {label}**")
        st.write(money(value))

    st.caption("Punktnumren ovan gäller huvudberäkningen på K5/K6. Uppskov och specialfall visas ännu inte som färdiga ifyllnadsrader.")

    share=float(case.get("share",100) or 100)/100
    raw_gain=rows[-1][2] if rows else 0.0
    own_gain=raw_gain*share
    st.subheader("Din ägarandel")
    if int(case.get("share",100))<100:
        st.write(
            f"Du har angett att du ägde **{int(case.get('share',100))} %**. "
            f"Din preliminära andel av vinsten/förlusten blir därför **{money(own_gain)}**."
        )
    else:
        st.write(f"Du har angett att du ägde hela bostaden. Preliminär vinst/förlust: **{money(own_gain)}**.")

    st.subheader("Vad återstår innan vi kan säga 'klart att deklarera'?")
    if home=="Bostadsrätt":
        st.write(
            "Bovinst har nu med kapitaltillskott och inre reparationsfond i K6-guiden. "
            "Nästa steg är att bygga klart uppskov, tidigare uppskov och fler specialfall."
        )
    else:
        st.write(
            "K5-guiden har nu huvudraderna för försäljningspris, försäljningskostnader, inköpspris "
            "och förbättringsutgifter. Nästa steg är uppskov, tidigare uppskov och specialfall."
        )

    st.markdown(
        f"<div class='bv-card'><b>Regler kontrollerade mot Skatteverket:</b> {VERIFIED_DATE}<br>"
        f"<span class='bv-muted'>Regelversion: {RULESET_VERSION}</span></div>",
        unsafe_allow_html=True
    )



with tabs[5]:
    st.header("Uppskov")
    st.write("Uppskov betyder att du skjuter upp beskattningen av hela eller delar av vinsten.")

    perm=st.radio("Var den sålda bostaden din permanentbostad?",["Ja","Nej","Vet inte"],horizontal=True,key="perm_home")
    lived=st.radio("Bodde du där minst ett år direkt före försäljningen, eller minst tre av de senaste fem åren?",["Ja","Nej","Vet inte"],horizontal=True,key="lived_rule")

    status=st.selectbox("Vilket stämmer bäst om din nya bostad?",[
        "Köpt och inflyttad i tid",
        "Inte köpt ännu",
        "Köpt men inte flyttat in i tid",
        "Vet inte / annat"
    ])

    replacement=st.number_input("Vad kostade din andel av den nya bostaden? (om du vet)",min_value=0,step=10000,key="replacement_price")
    prior=st.number_input("Har du ett gammalt uppskov? Skriv beloppet om du vet.",min_value=0,step=10000,key="prior_uppskov")

    case=st.session_state.case
    case["permanent_home"]=True if perm=="Ja" else False if perm=="Nej" else None
    case["lived_rule"]=True if lived=="Ja" else False if lived=="Nej" else None
    case["replacement_status"]=status
    case["replacement_price"]=float(replacement)
    case["prior_uppskov"]=float(prior)
    case["sold_price_owner"]=float(case.get("sell",0) or 0)*(float(case.get("share",100) or 100)/100)
    st.session_state.case=case

    rows=k6_rows(case,st.session_state.costs) if case.get("home")=="Bostadsrätt" else k5_rows(case,st.session_state.costs)
    own_gain=float(rows[-1][2])*(float(case.get("share",100) or 100)/100)
    screen=uppskov_screening(case,own_gain)

    st.subheader("Bovinsts första kontroll")
    if screen["eligible_hint"]:
        st.success(screen["type"])
    else:
        st.warning("Uppskov är inte klart ännu – några saker behöver kontrolleras.")

    st.write(f"Din preliminära andel av vinsten/förlusten: **{money(own_gain)}**")
    if own_gain>0:
        st.write(f"Preliminär övre gräns enligt vinst och takbelopp: **{money(screen['max_hint'])}**")
        st.caption("Detta är inte ett slutligt uppskovsbelopp. Billigare ersättningsbostad, tidigare uppskov eller specialfall kan ändra beloppet.")

    for item in screen["checks"]:
        st.write("⚠",item)
    for item in screen["notes"]:
        st.write("ℹ️",item)

    st.info("Slutligt eller preliminärt uppskov beror bland annat på när den nya bostaden köps och när du flyttar in.")

st.divider()
st.caption("Bovinst är ett beslutsstöd. Vid osäkra eller ovanliga situationer behöver uppgifterna kontrolleras mot Skatteverket.")
st.caption("Lagring i v0.8 är en prototypmekanism. Innan skarp användning ska ärenden lagras i en riktig databas med användarautentisering, åtkomstkontroll och RLS – inte enbart på Streamlits lokala disk.")

