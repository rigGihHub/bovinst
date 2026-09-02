import streamlit as st
from rules import assess, classify_from_answers, RULESET_VERSION, VERIFIED_DATE

st.set_page_config(page_title="Bovinst", page_icon="🏠", layout="wide")

st.markdown("""
<style>
.block-container{max-width:1100px;padding-top:1.5rem}
[data-testid="stMetric"]{border:1px solid #e6e8eb;border-radius:16px;padding:17px;background:#fff}
.beginner{background:#f7f8fa;border-radius:14px;padding:14px 16px;margin:8px 0 14px}
.status{font-size:1.05rem;font-weight:700}
.small{color:#667085;font-size:.92rem}
</style>
""", unsafe_allow_html=True)

if "case" not in st.session_state: st.session_state.case={}
if "costs" not in st.session_state: st.session_state.costs=[]

def money(v): return f"{float(v):,.0f} kr".replace(","," ")

def explain(title, text):
    with st.expander("Vad betyder detta?"):
        st.write(f"**{title}**")
        st.write(text)

st.title("Bovinst")
st.caption("Vi hjälper dig steg för steg. Du behöver inte kunna något om skatt eller deklaration.")
st.info("Du berättar vad du har gjort och betalat. Bovinst försöker sortera uppgifterna åt dig och visar vad som behöver kontrolleras.")

tabs=st.tabs(["1 · Börja här","2 · Vad har du betalat för?","3 · Dina kostnader","4 · Saknas kvitto?","5 · Din översikt"])

with tabs[0]:
    st.header("Vi börjar med bostaden")
    st.write("Det räcker med några grunduppgifter. Vi använder dem senare för att räkna och ställa rätt frågor.")

    a,b=st.columns(2)
    with a:
        home=st.selectbox(
            "Vad var det för typ av bostad?",
            ["Villa","Radhus","Parhus","Fritidshus","Ägarlägenhet","Bostadsrätt"],
            help="Välj det alternativ som bäst beskriver bostaden du sålde."
        )
        buy=st.number_input(
            "Ungefär vad betalade du när du köpte bostaden?",
            min_value=0,step=10000,
            help="Skriv själva inköpspriset. Senare hjälper Bovinst dig med andra kostnader kring köpet."
        )
        buyyear=st.number_input("Vilket år köpte du bostaden?",1900,2100,2015)
    with b:
        sell=st.number_input(
            "Vad sålde du bostaden för?",
            min_value=0,step=10000,
            help="Skriv priset som stod i köpekontraktet."
        )
        sellyear=st.number_input("Vilket år skrevs försäljningen?",1900,2100,2026)
        share=st.slider(
            "Hur stor del av bostaden ägde du?",
            1,100,100,format="%d %%",
            help="Om ni ägde hälften var väljer du 50 %. Ägde du hela bostaden väljer du 100 %."
        )

    st.session_state.case={"home":home,"buy":buy,"buyyear":buyyear,"sell":sell,"sellyear":sellyear,"share":share}

    explain(
        "Varför frågar vi om köp- och försäljningspris?",
        "När en bostad säljs räknar man förenklat skillnaden mellan vad du fick betalt och vad bostaden kostade dig. "
        "Vissa kostnader får minska den skillnaden. En lägre vinst kan innebära lägre skatt."
    )
    st.success("Bra. Nästa steg är att leta efter kostnader som kan vara viktiga.")

with tabs[1]:
    st.header("Vad har du betalat för?")
    st.write("Tänk inte på vad som är avdragsgillt. Svara bara på vad du faktiskt gjorde eller betalade för.")

    work=st.selectbox("Vad vill du lägga till?",[
        "Renovering eller arbete på bostaden",
        "Försäljningskostnad"
    ])

    if work=="Försäljningskostnad":
        name=st.selectbox("Vad betalade du för?",[
            "Mäklararvode","Fotografering","Annonsering","Besiktning",
            "Energideklaration","Homestyling","Juridisk hjälp","Annat"
        ])
        year=st.number_input("Vilket år betalade du?",1900,2100,int(st.session_state.case.get("sellyear",2026)),key="sale_y")
        amount=st.number_input("Hur mycket betalade du?",min_value=0,step=1000,key="sale_a")
        evidence=st.checkbox("Jag har något som visar kostnaden, till exempel faktura, kvitto eller bankbetalning",key="sale_e")
        note=st.text_area("Vill du skriva något mer? Det är frivilligt.",key="sale_n")

        if st.button("Spara kostnaden",type="primary",key="save_sale"):
            st.session_state.costs.append({
                "name":name,"work_type":"Försäljningskostnad","year":year,"amount":amount,"rot":0,
                "evidence":evidence,"existed_before":None,"changed_layout":False,"added_new":False,
                "improved":None,"note":note
            })
            st.rerun()

        explain(
            "Vad är en försäljningskostnad?",
            "Det är en kostnad som uppstod därför att bostaden skulle säljas. Ett vanligt exempel är mäklararvodet."
        )

    else:
        name=st.selectbox("Vad gjorde du?",[
            "Renoverade badrum","Renoverade kök","Bytte tak","Bytte fönster",
            "Dränerade huset","Installerade eller bytte värmesystem","Gjorde elarbete",
            "Gjorde VVS-arbete","Byggde till","Ändrade planlösningen",
            "Byggde garage eller carport","Målade eller tapetserade","Annat"
        ])
        year=st.number_input("Vilket år gjordes arbetet?",1900,2100,int(st.session_state.case.get("sellyear",2026)),key="reno_y")
        amount=st.number_input("Vad kostade det totalt?",min_value=0,step=1000,key="reno_a")
        rot=st.number_input(
            "Fick du ROT-avdrag på fakturan? Skriv i så fall hur mycket.",
            min_value=0,step=1000,key="reno_r",
            help="ROT är skattereduktionen som kan stå på hantverkarens faktura. Den delen ska inte räknas två gånger."
        )

        existed_answer=st.radio(
            "Fanns det som du arbetade med redan när du köpte bostaden?",
            ["Ja","Nej","Vet inte"],
            horizontal=True
        )
        changed_layout=st.checkbox("Jag flyttade väggar eller ändrade planlösningen")
        added_new=st.checkbox("Jag lade till något som inte fanns tidigare")
        improved_answer=st.radio(
            "När du sålde bostaden – var den fortfarande bättre tack vare det här arbetet jämfört med när du köpte?",
            ["Ja","Nej","Vet inte"],
            horizontal=True
        )
        evidence=st.checkbox("Jag har något som visar kostnaden eller arbetet",key="reno_e")
        note=st.text_area("Beskriv gärna med egna ord vad som gjordes. Du behöver inte använda facktermer.",key="reno_n")

        if st.button("Spara och låt Bovinst bedöma",type="primary",key="save_reno"):
            st.session_state.costs.append({
                "name":name,"work_type":"Renovering eller arbete på bostaden",
                "year":year,"amount":amount,"rot":rot,"evidence":evidence,
                "existed_before": True if existed_answer=="Ja" else False if existed_answer=="Nej" else None,
                "changed_layout":changed_layout,"added_new":added_new,
                "improved": True if improved_answer=="Ja" else False if improved_answer=="Nej" else None,
                "note":note
            })
            st.rerun()

        explain(
            "Varför frågar vi om något fanns tidigare?",
            "Skattereglerna skiljer på att till exempel renovera något som redan fanns och att bygga något nytt eller göra en större ombyggnad. "
            "Du behöver inte avgöra vilken kategori det är – dina svar hjälper Bovinst att göra sorteringen."
        )
        explain(
            "Vad är 5 000-kronorsregeln?",
            "För förbättringar tittar man på hur mycket sådana kostnader du haft under hela kalenderåret. "
            "Exempel: 3 000 kr för en sak och 4 000 kr för en annan samma år blir tillsammans 7 000 kr. "
            "Därför ska du lägga in även mindre poster så att Bovinst kan summera året."
        )

with tabs[2]:
    st.header("Dina kostnader")
    if not st.session_state.costs:
        st.info("Du har inte lagt till någon kostnad ännu.")
    sy=int(st.session_state.case.get("sellyear",2026))

    for i,c in enumerate(st.session_state.costs):
        a=assess(c,sy,st.session_state.costs)
        with st.expander(f"{c['name']} · {money(c['amount'])} · {a.status}"):
            st.markdown(f"### {a.status}")
            st.write(a.plain_summary)
            st.write(f"**Belopp som Bovinst just nu räknar som möjligt:** {money(a.deductible_amount)}")
            if c.get("rot"):
                st.caption(f"Du angav {money(c['rot'])} i ROT. Den delen har räknats bort från kostnaden här.")

            if a.reasons:
                st.write("**Det här talar för bedömningen:**")
                for r in a.reasons: st.write("✓",r)
            if a.missing:
                st.write("**Det här behöver du kontrollera:**")
                for m in a.missing: st.write("⚠",m)

            tax_kind=classify_from_answers(c)
            with st.expander("Visa skatteordet – bara om du vill"):
                label={"sale":"försäljningsutgift","basic":"grundförbättring","repair":"förbättrande reparation eller underhåll"}[tax_kind]
                st.write(f"Skatteverkets kategori som Bovinst preliminärt kopplar detta till är **{label}**.")
                st.write("Du behöver inte kunna eller komma ihåg ordet för att fortsätta.")

            if st.button("Ta bort posten",key=f"delete_{i}"):
                st.session_state.costs.pop(i); st.rerun()

with tabs[3]:
    st.header("Saknas kvitto eller faktura?")
    st.write("Låt kostnaden ligga kvar. Vi skiljer på att du minns en kostnad och att du kan visa underlag för den.")

    missing=[c for c in st.session_state.costs if not c.get("evidence")]
    if not st.session_state.costs:
        st.info("Du har inte lagt in några kostnader ännu.")
    elif not missing:
        st.success("Alla dina poster är markerade med någon form av underlag.")
    else:
        for c in missing:
            st.warning(f"{c['name']} – du har inte markerat något underlag ännu")

        st.markdown("""
**Sådant du kan leta efter:**
- bankbetalning eller gammalt kontoutdrag
- faktura eller kvitto
- mejl från hantverkare eller butik
- offert eller avtal
- fotografier före och efter
- bygglov eller andra handlingar
- dokument från entreprenören
""")
    explain(
        "Måste man alltid ha ett kvitto?",
        "Bovinst ska inte påstå att en uppskattning automatiskt godtas. Underlag kan bestå av mer än ett kvitto, "
        "men hur väl en kostnad kan styrkas måste bedömas i det enskilda fallet."
    )

with tabs[4]:
    st.header("Din översikt")
    st.write("Det här är en arbetsöversikt – inte en färdig deklaration.")

    sy=int(st.session_state.case.get("sellyear",2026))
    aa=[assess(c,sy,st.session_state.costs) for c in st.session_state.costs]
    strong=sum(x.deductible_amount for x in aa if x.confidence=="strong")
    possible=sum(x.deductible_amount for x in aa if x.confidence=="medium")
    needs=sum(1 for x in aa if x.confidence=="low")

    a,b,c=st.columns(3)
    a.metric("Har bra stöd just nu",money(strong))
    b.metric("Kan vara möjligt",money(possible))
    c.metric("Behöver kontrolleras",needs)

    explain(
        "Vad betyder de tre rutorna?",
        "Första rutan är poster där dina svar och underlag just nu ser relativt starka ut. "
        "Andra rutan är poster som kan vara relevanta men fortfarande behöver viss kontroll. "
        "Den tredje visar sådant som Bovinst ännu inte tycker att vi ska räkna med."
    )

    sale=float(st.session_state.case.get("sell",0))
    buy=float(st.session_state.case.get("buy",0))
    raw=sale-buy
    st.subheader("Mycket förenklad bild")
    st.write(f"Du sålde för: **{money(sale)}**")
    st.write(f"Du köpte för: **{money(buy)}**")
    st.write(f"Skillnaden är: **{money(raw)}**")

    st.markdown("""
<div class="beginner">
<b>Viktigt:</b> Skillnaden ovan är inte samma sak som den slutliga beskattningsbara vinsten.
Fler uppgifter kan behöva läggas till innan en korrekt deklarationsberäkning kan göras.
</div>
""", unsafe_allow_html=True)

    if st.session_state.case.get("home")=="Bostadsrätt":
        st.info("Eftersom du har valt bostadsrätt kommer en senare version även fråga om uppgifter från bostadsrättsföreningen, till exempel kapitaltillskott. Bovinst ska förklara vad det betyder när frågan kommer.")
    else:
        st.info("För hus kommer en senare version även fråga om vissa kostnader från när bostaden köptes, till exempel lagfart och i vissa fall pantbrev. Bovinst ska förklara orden när de behövs.")

    st.warning("Vi visar ännu ingen slutlig skatt. Det vore missvisande innan hela K5/K6-logiken och specialfallen är klara.")

st.divider()
st.caption(f"Bovinst v0.3.0 · Regelverk {RULESET_VERSION} · regler kontrollerade mot Skatteverket {VERIFIED_DATE}")
