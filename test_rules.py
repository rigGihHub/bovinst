import pytest
from rules import assess, annual_improvement_total, declaration_summary

def reno(name,year,amount,**kw):
    x={
        "name":name,
        "work_type":"Renovering eller arbete på bostaden",
        "year":year,
        "amount":amount,
        "rot":0,
        "evidence":True,
        "existed_before":True,
        "changed_layout":False,
        "added_new":False,
        "improved":True,
    }
    x.update(kw)
    return x

def sale_cost(name,amount,**kw):
    x={
        "name":name,
        "work_type":"Försäljningskostnad",
        "year":2026,
        "amount":amount,
        "rot":0,
        "evidence":True,
    }
    x.update(kw)
    return x

def test_two_small_improvements_same_year_cross_5000_threshold():
    a=reno("Målning",2024,3000)
    b=reno("Golv",2024,4000)
    costs=[a,b]
    assert annual_improvement_total(costs,2024,2026)==7000
    assert assess(a,2026,costs,home="Villa").deductible_amount==3000
    assert assess(b,2026,costs,home="Villa").deductible_amount==4000

def test_under_5000_for_year_not_counted_yet():
    a=reno("Målning",2024,4999)
    r=assess(a,2026,[a],home="Villa")
    assert r.deductible_amount==0
    assert r.confidence=="low"

def test_repair_2020_too_old_for_sale_2026():
    a=reno("Takunderhåll",2020,100000)
    r=assess(a,2026,[a],home="Villa")
    assert r.deductible_amount==0

def test_repair_2021_inside_window_for_sale_2026():
    a=reno("Takunderhåll",2021,100000)
    r=assess(a,2026,[a],home="Villa")
    assert r.deductible_amount==100000

def test_basic_improvement_not_subject_to_six_year_window():
    a=reno("Tillbyggnad",2000,250000,existed_before=False,added_new=True)
    r=assess(a,2026,[a],home="Villa")
    assert r.deductible_amount==250000

def test_basic_smallhouse_before_1952_blocked():
    a=reno("Tillbyggnad",1951,250000,existed_before=False,added_new=True)
    r=assess(a,2026,[a],home="Villa")
    assert r.deductible_amount==0

def test_basic_bostadsratt_before_1974_blocked():
    a=reno("Ombyggnad",1973,50000,changed_layout=True)
    r=assess(a,2026,[a],home="Bostadsrätt")
    assert r.deductible_amount==0

def test_rot_subtracted_from_modern_cost():
    a=reno("Badrum",2022,150000,rot=30000)
    r=assess(a,2026,[a],home="Villa")
    assert r.deductible_amount==120000

def test_future_cost_blocked():
    a=reno("Kök",2027,100000)
    r=assess(a,2026,[a],home="Villa")
    assert r.deductible_amount==0

def test_self_labor_blocked():
    a=reno("Eget arbete",2024,50000,self_labor=True)
    r=assess(a,2026,[a],home="Villa")
    assert r.deductible_amount==0

def test_insurance_compensation_reduces_cost():
    a=reno("Vattenskada",2024,100000,insurance_compensation=60000)
    r=assess(a,2026,[a],home="Villa")
    assert r.deductible_amount==40000

def test_missing_better_condition_blocks_repair_amount():
    a=reno("Kök",2024,100000,improved=None)
    r=assess(a,2026,[a],home="Villa")
    assert r.deductible_amount==0
    assert r.confidence=="medium"

def test_better_material_split_is_not_auto_counted_as_all_basic():
    a=reno("Golv",2020,20000,existed_before=True,better_material_split_needed=True,changed_layout=True)
    r=assess(a,2026,[a],home="Villa")
    assert r.deductible_amount==0
    assert r.status=="Behöver delas upp"

def test_sale_cost_counted():
    a=sale_cost("Mäklare",75000)
    r=assess(a,2026,[a],home="Villa")
    assert r.deductible_amount==75000

def test_private_moving_cost_not_counted_as_sale_cost():
    a=sale_cost("Flytt",20000,sale_private_cost=True)
    r=assess(a,2026,[a],home="Villa")
    assert r.deductible_amount==0

def test_declaration_summary_excludes_uncertain_repair():
    good=sale_cost("Mäklare",50000)
    uncertain=reno("Kök",2024,100000,improved=None)
    case={"sell":5000000,"buy":3000000,"sellyear":2026,"home":"Villa"}
    s=declaration_summary(case,[good,uncertain])
    assert s["sale_costs"]==50000
    assert s["improvements"]==0
    assert s["preliminary_gain"]==1950000


def test_exact_cost_without_receipt_is_kept_as_possible():
    a=reno("Badrum",2024,120000,evidence=False,evidence_level="Inget underlag just nu",amount_quality="exact")
    r=assess(a,2026,[a],home="Villa")
    assert r.deductible_amount==120000
    assert r.confidence=="medium"

def test_approx_memory_only_amount_not_counted_yet():
    a=reno("Kök",2024,100000,evidence=False,evidence_level="Inget underlag just nu",amount_quality="approx")
    r=assess(a,2026,[a],home="Villa")
    assert r.deductible_amount==0
    assert r.confidence=="low"

def test_approx_with_alternative_evidence_not_falsely_exact():
    a=reno("Tak",2024,90000,evidence=False,evidence_level="Foton/ritningar/bygglov eller annat",amount_quality="approx")
    r=assess(a,2026,[a],home="Villa")
    assert r.deductible_amount==0
    assert r.confidence=="medium"
    assert "skäligt belopp" in r.plain_summary.lower()

def test_unknown_cost_project_is_preserved_but_not_counted():
    a=reno("Dränering",2024,0,evidence=False,evidence_level="Foton/ritningar/bygglov eller annat",amount_quality="unknown")
    r=assess(a,2026,[a],home="Villa")
    assert r.deductible_amount==0
    assert "sparad" in r.status.lower()


def test_vet_ej_evidence_is_treated_as_unknown_not_as_document():
    a=reno("Badrum",2024,100000,evidence=False,evidence_level="Vet ej",amount_quality="exact")
    r=assess(a,2026,[a],home="Villa")
    assert r.deductible_amount==100000
    assert r.confidence=="medium"

def test_unknown_rot_creates_missing_check_instead_of_guessing():
    a=reno("Kök",2024,100000,evidence=True,evidence_level="Kvitto eller faktura",amount_quality="exact",rot_known=False)
    r=assess(a,2026,[a],home="Villa")
    assert any("ROT" in x for x in r.missing)


def test_uncertainty_tasks_prioritize_unknown_year_and_rot():
    from rules import uncertainty_tasks
    case={"sellyear":2026,"hunt_answers":{"kitchen":"Ja"},"hunt_followups":{"kitchen":{"when":"Vet ej","paid":"Ja, ungefär","docs":"Vet ej"}}}
    c=reno("Kök",2024,100000,evidence=False,evidence_level="Vet ej",amount_quality="approx",rot_known=False)
    tasks=uncertainty_tasks(case,[c])
    assert tasks
    assert min(t["priority"] for t in tasks)==1
    titles=" ".join(t["title"] for t in tasks)
    assert "ROT" in titles
    assert "tidsbestämma" in titles.lower()

def test_unknown_discovery_area_becomes_task_not_no():
    from rules import uncertainty_tasks
    case={"sellyear":2026,"hunt_answers":{"bathroom":"Vet ej"},"hunt_followups":{}}
    tasks=uncertainty_tasks(case,[])
    assert len(tasks)==1
    assert tasks[0]["kind"]=="discovery"

def test_known_complete_cost_can_have_no_uncertainty_tasks():
    from rules import uncertainty_tasks
    case={"sellyear":2026,"hunt_answers":{},"hunt_followups":{}}
    c=reno("Badrum",2024,120000,evidence=True,evidence_level="Kvitto/faktura och betalning",amount_quality="exact",rot_known=True,existed_before=True,improved=True)
    tasks=uncertainty_tasks(case,[c])
    assert tasks==[]


def test_project_from_hunt_creates_unknown_draft():
    from rules import project_from_hunt
    p=project_from_hunt(
        "bathroom",
        "Jag gjorde något i badrum eller toalett",
        {"when":"Vet ej","year_hint":None,"period_hint":None,"paid":"Vet ej","amount_hint":0,"docs":"Vet ej"},
        2026
    )
    assert p["hunt_generated"] is True
    assert p["draft"] is True
    assert p["amount_quality"]=="unknown"
    assert p["amount"]==0
    assert p["existed_before"] is None

def test_project_from_hunt_uses_known_year_and_approx_amount():
    from rules import project_from_hunt
    p=project_from_hunt(
        "kitchen",
        "Jag gjorde något i köket",
        {"when":"Jag vet årtalet","year_hint":2022,"period_hint":None,"paid":"Ja, ungefär","amount_hint":130000,"docs":"Nej"},
        2026
    )
    assert p["year"]==2022
    assert p["amount"]==130000
    assert p["amount_quality"]=="approx"

def test_find_hunt_project_prevents_duplicate_same_area():
    from rules import find_hunt_project
    costs=[
        {"name":"Kök","hunt_source":"kitchen","hunt_generated":True},
        {"name":"Annat"}
    ]
    assert find_hunt_project(costs,"kitchen")==0
    assert find_hunt_project(costs,"bathroom") is None


def test_discovery_areas_differ_between_bostadsratt_and_villa():
    from rules import discovery_areas_for_home
    br_keys={x[0] for x in discovery_areas_for_home("Bostadsrätt")}
    villa_keys={x[0] for x in discovery_areas_for_home("Villa")}
    assert "brf" in br_keys
    assert "purchase_costs" not in br_keys
    assert "drainage" not in br_keys
    assert "drainage" in villa_keys
    assert "purchase_costs" in villa_keys

def test_coverage_summary_counts_reviewed_answers():
    from rules import coverage_summary, discovery_areas_for_home
    keys=[x[0] for x in discovery_areas_for_home("Bostadsrätt")]
    case={"home":"Bostadsrätt","hunt_answers":{keys[0]:"Ja",keys[1]:"Nej",keys[2]:"Vet ej"}}
    c=coverage_summary(case)
    assert c["reviewed"]==3
    assert c["yes"]==1
    assert c["unknown"]==1

def test_unknown_answers_are_reviewed_but_not_resolved():
    from rules import coverage_summary, discovery_areas_for_home
    areas=discovery_areas_for_home("Villa")
    answers={key:"Vet ej" for key,_,_ in areas}
    c=coverage_summary({"home":"Villa","hunt_answers":answers})
    assert c["reviewed"]==c["total"]
    assert c["unknown"]==c["total"]
    assert c["remaining"]==0

def test_drainage_can_create_hunt_project():
    from rules import project_from_hunt
    p=project_from_hunt(
        "drainage","Dränering och grund",
        {"when":"Vet ej","year_hint":None,"period_hint":None,"paid":"Vet ej","amount_hint":0,"docs":"Vet ej"},
        2026
    )
    assert "Dränering" in p["name"]
    assert p["draft"] is True


def test_timeline_periods_short_ownership_year_by_year():
    from rules import timeline_periods
    p=timeline_periods({"buyyear":2023,"sellyear":2026})
    assert p==[(2023,2023),(2024,2024),(2025,2025),(2026,2026)]

def test_timeline_periods_long_ownership_chunks_time():
    from rules import timeline_periods
    p=timeline_periods({"buyyear":1998,"sellyear":2026})
    assert p[0]==(1998,2007)
    assert p[-1][1]==2026
    assert len(p)>=3

def test_timeline_summary_preserves_vet_ej_as_unresolved():
    from rules import timeline_summary
    case={
        "buyyear":2021,"sellyear":2026,
        "timeline_answers":{"2021_2021":"Ja","2022_2022":"Vet ej","2023_2023":"Nej"}
    }
    s=timeline_summary(case)
    assert s["reviewed"]==3
    assert s["yes"]==1
    assert s["unknown"]==1

def test_duplicate_candidates_flags_same_hunt_project():
    from rules import duplicate_candidates
    costs=[
        {"name":"Renoverade badrum","year":2022,"amount":120000,"hunt_source":"bathroom","hunt_generated":True},
        {"name":"Renoverade badrum","year":2022,"amount":125000,"hunt_source":"bathroom","hunt_generated":False},
    ]
    d=duplicate_candidates(costs)
    assert len(d)==1
    assert d[0]["score"]>=5

def test_duplicate_candidates_does_not_flag_different_projects():
    from rules import duplicate_candidates
    costs=[
        {"name":"Renoverade kök","year":2022,"amount":120000,"hunt_source":"kitchen"},
        {"name":"Bytte tak","year":2022,"amount":120000,"hunt_source":"windows_roof"},
    ]
    assert duplicate_candidates(costs)==[]


def test_smart_checks_include_brf_specific_item():
    from rules import smart_deduction_checks
    checks=smart_deduction_checks({"home":"Bostadsrätt"},[])
    text=" ".join(a+" "+b for a,b in checks)
    assert "kapitaltillskott" in text.lower()
    assert "inre reparationsfond" in text.lower()

def test_smart_checks_include_house_purchase_costs():
    from rules import smart_deduction_checks
    checks=smart_deduction_checks({"home":"Villa"},[])
    text=" ".join(a+" "+b for a,b in checks)
    assert "lagfart" in text.lower()
    assert "pantbrev" in text.lower()

def test_eligible_year_total_excludes_old_repair():
    from rules import eligible_year_total
    costs=[
        {"name":"Gammal målning","year":2018,"amount":4000,"work_type":"Reparation","improved":True},
        {"name":"Ny målning","year":2026,"amount":3000,"work_type":"Reparation","improved":True},
    ]
    totals=eligible_year_total(costs,2026,"Villa")
    assert totals.get(2018,0)==0
    assert totals.get(2026,0)==3000

def test_eligible_year_total_excludes_future_and_self_labor():
    from rules import eligible_year_total
    costs=[
        {"name":"Framtid","year":2027,"amount":6000,"work_type":"Renovering"},
        {"name":"Eget arbete","year":2026,"amount":6000,"work_type":"Renovering","self_labor":True},
    ]
    assert eligible_year_total(costs,2026,"Villa")=={}


def test_normalize_home_type_groups_house_types():
    from rules import normalize_home_type
    assert normalize_home_type("Villa")=="Småhus"
    assert normalize_home_type("radhus")=="Småhus"
    assert normalize_home_type("fritidshus")=="Småhus"

def test_housing_route_bostadsratt_uses_k6_when_clear():
    from rules import housing_route
    case={"home":"Bostadsrätt","used_as_private_home":"Ja","brf_genuine":"Ja"}
    r=housing_route(case)
    assert r["form"]=="K6"
    assert r["status"]=="ok"

def test_housing_route_house_uses_k5_when_clear():
    from rules import housing_route
    case={"home":"Villa","used_as_private_home":"Ja"}
    r=housing_route(case)
    assert r["form"]=="K5"
    assert r["status"]=="ok"

def test_housing_route_unknown_blocks():
    from rules import housing_route
    r=housing_route({"home":"Vet ej"})
    assert r["status"]=="block"
    assert r["route"]=="unknown"

def test_housing_route_special_brf_does_not_silently_use_k6():
    from rules import housing_route
    case={"home":"Bostadsrätt","used_as_private_home":"Ja","brf_genuine":"Nej"}
    r=housing_route(case)
    assert r["status"]=="block"
    assert r["route"]=="special"

def test_housing_questions_only_asks_brf_question_for_bostadsratt():
    from rules import housing_questions
    br=[k for k,_ in housing_questions({"home":"Bostadsrätt"})]
    villa=[k for k,_ in housing_questions({"home":"Villa"})]
    assert "brf_genuine" in br
    assert "brf_genuine" not in villa


def test_money_miss_checks_house_flags_purchase_costs():
    from rules import money_miss_checks
    case={"home":"Villa","sellyear":2026,"hunt_answers":{"sale_costs":"Ja"}}
    tasks=money_miss_checks(case,[])
    keys={t["key"] for t in tasks}
    assert "purchase_costs" in keys

def test_money_miss_checks_brf_flags_brf_data_not_house_purchase():
    from rules import money_miss_checks
    case={"home":"Bostadsrätt","sellyear":2026,"hunt_answers":{"sale_costs":"Ja"}}
    tasks=money_miss_checks(case,[])
    keys={t["key"] for t in tasks}
    assert "brf" in keys
    assert "purchase_costs" not in keys

def test_money_miss_checks_flags_duplicate_as_high_priority():
    from rules import money_miss_checks
    costs=[
        {"name":"Badrum","year":2024,"amount":100000,"hunt_source":"bathroom"},
        {"name":"Badrum","year":2024,"amount":102000,"hunt_source":"bathroom"},
    ]
    case={"home":"Villa","sellyear":2026,"hunt_answers":{"purchase_costs":"Ja","sale_costs":"Ja"}}
    tasks=money_miss_checks(case,costs)
    dup=[t for t in tasks if t["key"]=="duplicates"]
    assert dup and dup[0]["priority"]==1

def test_money_miss_score_not_clear_when_high_priority_exists():
    from rules import money_miss_score
    case={"home":"Villa","sellyear":2026,"hunt_answers":{}}
    score=money_miss_score(case,[])
    assert score["status"]=="Inte klar"
    assert score["high"]>0

def test_money_miss_checks_old_project_creates_review_task():
    from rules import money_miss_checks
    case={"home":"Villa","sellyear":2026,"hunt_answers":{"purchase_costs":"Ja","sale_costs":"Ja"}}
    costs=[{"name":"Tillbyggnad","year":2010,"amount":200000,"evidence_level":"document","amount_quality":"exact"}]
    tasks=money_miss_checks(case,costs)
    assert any(t["key"]=="old_projects" for t in tasks)


def test_unknown_year_placeholder_is_never_ready():
    from rules import project_readiness
    case={"home":"Villa","sellyear":2026}
    cost={
        "name":"Kök","year":2026,"year_quality":"unknown",
        "amount":120000,"amount_quality":"exact",
        "evidence_level":"document","existed_before":False,
        "rot_known":True,"rot":0
    }
    r=project_readiness(case,cost,[cost])
    assert r["ready"] is False
    assert r["level"]=="needs_info"

def test_unknown_amount_is_never_ready():
    from rules import project_readiness
    case={"home":"Villa","sellyear":2026}
    cost={
        "name":"Badrum","year":2024,"year_quality":"exact",
        "amount":0,"amount_quality":"unknown","evidence_level":"alternative",
        "existed_before":False,"rot_known":True,"rot":0
    }
    r=project_readiness(case,cost,[cost])
    assert not r["ready"]
    assert r["level"]=="needs_info"

def test_exact_basic_project_with_document_can_be_ready():
    from rules import project_readiness
    case={"home":"Villa","sellyear":2026}
    cost={
        "name":"Tillbyggnad","year":2020,"year_quality":"exact",
        "amount":100000,"amount_quality":"exact","evidence_level":"document",
        "existed_before":False,"improved":True,"rot_known":True,"rot":0,
        "work_type":"Renovering eller arbete på bostaden"
    }
    r=project_readiness(case,cost,[cost])
    assert r["ready"] is True
    assert r["level"]=="ready"

def test_approx_repair_with_alt_evidence_needs_evidence():
    from rules import project_readiness
    case={"home":"Villa","sellyear":2026}
    cost={
        "name":"Tak","year":2024,"year_quality":"exact",
        "amount":80000,"amount_quality":"approx","evidence_level":"alternative",
        "existed_before":True,"improved":True,"rot_known":True,"rot":0,
        "work_type":"Renovering eller arbete på bostaden"
    }
    r=project_readiness(case,cost,[cost])
    assert r["ready"] is False
    assert r["level"]=="needs_evidence"

def test_recovery_plan_is_individual():
    from rules import project_recovery_plan
    case={"home":"Villa","sellyear":2026}
    cost={
        "name":"Värmepump","year":2026,"year_quality":"unknown",
        "amount":0,"amount_quality":"unknown","evidence_level":"none",
        "existed_before":None,"rot_known":False
    }
    p=project_recovery_plan(case,cost,[cost])
    titles=[x[0] for x in p["steps"]]
    assert "När gjordes det?" in titles
    assert "Vad kostade det?" in titles
    assert "Vilket stöd finns?" in titles

def test_readiness_summary_counts_inactive_separately():
    from rules import readiness_summary
    case={"home":"Villa","sellyear":2026}
    costs=[{"name":"Gammal post","inactive":True}]
    s=readiness_summary(case,costs)
    assert s["inactive"]==1
    assert s["ready"]==0


def test_annual_threshold_ignores_self_labor():
    from rules import annual_improvement_total
    costs=[
        {"name":"Material","year":2026,"amount":4000,"amount_quality":"exact",
         "work_type":"Renovering eller arbete på bostaden","existed_before":False},
        {"name":"Eget arbete","year":2026,"amount":2000,"amount_quality":"exact",
         "work_type":"Renovering eller arbete på bostaden","existed_before":False,"self_labor":True},
    ]
    assert annual_improvement_total(costs,2026,2026,"Villa")==4000

def test_annual_threshold_two_eligible_projects_cross_5000():
    from rules import annual_improvement_total
    costs=[
        {"name":"A","year":2026,"amount":3000,"amount_quality":"exact",
         "work_type":"Renovering eller arbete på bostaden","existed_before":False},
        {"name":"B","year":2026,"amount":3000,"amount_quality":"exact",
         "work_type":"Renovering eller arbete på bostaden","existed_before":False},
    ]
    assert annual_improvement_total(costs,2026,2026,"Villa")==6000

def test_annual_threshold_ignores_old_repair():
    from rules import annual_improvement_total
    costs=[{"name":"Målning","year":2018,"amount":9000,"amount_quality":"exact",
            "work_type":"Renovering eller arbete på bostaden","existed_before":True,"improved":True}]
    assert annual_improvement_total(costs,2018,2026,"Villa")==0

def test_annual_threshold_ignores_approx_amount():
    from rules import annual_improvement_total
    costs=[{"name":"Osäker","year":2026,"amount":10000,"amount_quality":"approx",
            "work_type":"Renovering eller arbete på bostaden","existed_before":False}]
    assert annual_improvement_total(costs,2026,2026,"Villa")==0

def test_project_can_be_threshold_pending():
    from rules import project_readiness
    case={"home":"Villa","sellyear":2026}
    cost={"name":"Litet projekt","year":2025,"year_quality":"exact","amount":4000,"amount_quality":"exact",
          "evidence_level":"document","existed_before":False,"rot_known":True,"rot":0,
          "work_type":"Renovering eller arbete på bostaden"}
    r=project_readiness(case,cost,[cost])
    assert r["level"]=="threshold_pending"
    assert not r["ready"]

def test_declaration_ready_summary_excludes_unknown_year():
    from rules import declaration_ready_summary
    case={"home":"Villa","sellyear":2026}
    costs=[
        {"name":"Tillbyggnad","year":2025,"year_quality":"exact","amount":10000,"amount_quality":"exact",
         "evidence_level":"document","existed_before":False,"rot_known":True,"rot":0,
         "work_type":"Renovering eller arbete på bostaden"},
        {"name":"Osäkert badrum","year":2025,"year_quality":"unknown","amount":50000,"amount_quality":"exact",
         "evidence_level":"document","existed_before":False,"rot_known":True,"rot":0,
         "work_type":"Renovering eller arbete på bostaden"},
    ]
    s=declaration_ready_summary(case,costs)
    assert s["ready_count"]==1
    assert s["basic"]==10000

def test_declaration_ready_summary_lists_threshold_pending():
    from rules import declaration_ready_summary
    case={"home":"Villa","sellyear":2026}
    costs=[{"name":"Litet projekt","year":2025,"year_quality":"exact","amount":4000,"amount_quality":"exact",
            "evidence_level":"document","existed_before":False,"rot_known":True,"rot":0,
            "work_type":"Renovering eller arbete på bostaden"}]
    s=declaration_ready_summary(case,costs)
    assert s["basic"]==0
    assert len(s["threshold_pending"])==1

def test_sale_expense_not_subject_to_5000():
    from rules import declaration_ready_summary
    case={"home":"Villa","sellyear":2026}
    costs=[{"name":"Besiktning","year":2026,"year_quality":"exact","amount":3000,"amount_quality":"exact",
            "evidence_level":"document","rot_known":True,"rot":0,"work_type":"Försäljningskostnad"}]
    s=declaration_ready_summary(case,costs)
    assert s["sale_expenses"]==3000
    assert s["total"]==3000


def test_k5_rows_use_only_declaration_ready_projects():
    from rules import k5_rows
    case={"home":"Villa","sell":3000000,"buy":2000000,"sellyear":2026,"purchase_extra":0}
    costs=[
        {"name":"Tillbyggnad","year":2025,"year_quality":"exact","amount":10000,"amount_quality":"exact",
         "evidence_level":"document","existed_before":False,"rot_known":True,"rot":0,
         "work_type":"Renovering eller arbete på bostaden"},
        {"name":"Osäkert kök","year":2025,"year_quality":"unknown","amount":100000,"amount_quality":"exact",
         "evidence_level":"document","existed_before":False,"rot_known":True,"rot":0,
         "work_type":"Renovering eller arbete på bostaden"},
    ]
    rows=k5_rows(case,costs)
    values={p:v for p,_,v in rows}
    assert values["K5 punkt 4"]==10000

def test_k6_rows_use_ready_sale_costs_and_improvements():
    from rules import k6_rows
    case={"home":"Bostadsrätt","sell":3000000,"buy":2000000,"sellyear":2026,
          "capital_contribution":10000,"fund_sale":5000,"fund_buy":2000}
    costs=[
        {"name":"Mäklare","year":2026,"year_quality":"exact","amount":50000,"amount_quality":"exact",
         "evidence_level":"document","rot_known":True,"rot":0,"work_type":"Försäljningskostnad"},
        {"name":"Kök","year":2025,"year_quality":"exact","amount":80000,"amount_quality":"exact",
         "evidence_level":"document","existed_before":False,"rot_known":True,"rot":0,
         "work_type":"Renovering eller arbete på bostaden"},
    ]
    rows=k6_rows(case,costs)
    values={p:v for p,_,v in rows}
    assert values["K6 punkt 2"]==50000
    assert values["K6 punkt 4"]==80000
    assert values["K6 punkt 6"]==10000

def test_declaration_delivery_blocks_unknown_home():
    from rules import declaration_delivery
    d=declaration_delivery({"home":"Vet ej","sellyear":2026},[])
    assert d["status"]=="Inte klar"
    assert d["blockers"]

def test_declaration_delivery_owner_share():
    from rules import declaration_delivery
    case={"home":"Villa","used_as_private_home":"Ja","sell":3000000,"buy":2000000,
          "sellyear":2026,"share":50,"hunt_answers":{}}
    d=declaration_delivery(case,[])
    assert d["owner_share"]==0.5
    assert d["owner_gain"]==d["gain_before_share"]*0.5

def test_declaration_delivery_text_contains_form_and_rows():
    from rules import declaration_delivery_text
    case={"home":"Villa","used_as_private_home":"Ja","sell":3000000,"buy":2000000,
          "sellyear":2026,"share":100}
    txt=declaration_delivery_text(case,[])
    assert "BOVINST – DEKLARATIONSUNDERLAG" in txt
    assert "K5 punkt 1" in txt
    assert "Bilaga: K5" in txt

def test_special_route_has_no_k5_k6_rows():
    from rules import declaration_delivery
    case={"home":"Bostadsrätt","brf_genuine":"Nej","used_as_private_home":"Ja","sellyear":2026}
    d=declaration_delivery(case,[])
    assert d["rows"]==[]
    assert d["status"]=="Inte klar"

def test_declaration_delivery_status_not_ready_with_threshold_pending():
    from rules import declaration_delivery
    case={"home":"Villa","used_as_private_home":"Ja","sell":3000000,"buy":2000000,
          "sellyear":2026,"share":100}
    costs=[{"name":"Litet projekt","year":2025,"year_quality":"exact","amount":4000,"amount_quality":"exact",
            "evidence_level":"document","existed_before":False,"rot_known":True,"rot":0,
            "work_type":"Renovering eller arbete på bostaden"}]
    d=declaration_delivery(case,costs)
    assert d["status"]!="Klar att föra över"
    assert any("5 000" in w for w in d["warnings"])


def test_explicit_answer_only_accepts_real_choices():
    from rules import explicit_answer
    assert explicit_answer("Ja")
    assert explicit_answer("Nej")
    assert explicit_answer("Vet ej")
    assert not explicit_answer(None)
    assert not explicit_answer("")
    assert not explicit_answer("Välj ett svar")

def test_coverage_untouched_is_not_reviewed():
    from rules import coverage_summary
    case={"home":"Villa","hunt_answers":{}}
    s=coverage_summary(case)
    assert s["reviewed"]==0
    assert s["remaining"]==s["total"]

def test_coverage_explicit_vet_ej_counts_as_reviewed_unknown():
    from rules import coverage_summary, discovery_areas_for_home
    areas=discovery_areas_for_home("Villa")
    key=areas[0][0]
    s=coverage_summary({"home":"Villa","hunt_answers":{key:"Vet ej"}})
    assert s["reviewed"]==1
    assert s["unknown"]==1

def test_timeline_untouched_is_not_reviewed():
    from rules import timeline_summary
    case={"buyyear":2015,"sellyear":2026,"timeline_answers":{}}
    s=timeline_summary(case)
    assert s["reviewed"]==0
    assert s["remaining"]==s["total"]

def test_timeline_explicit_vet_ej_counts_as_reviewed():
    from rules import timeline_summary, timeline_periods
    case={"buyyear":2015,"sellyear":2026,"timeline_answers":{}}
    p=timeline_periods(case)[0]
    key=f"{p[0]}_{p[1]}"
    case["timeline_answers"][key]="Vet ej"
    s=timeline_summary(case)
    assert s["reviewed"]==1
    assert s["unknown"]==1

def test_housing_route_missing_private_home_is_not_ok():
    from rules import housing_route
    r=housing_route({"home":"Villa"})
    assert r["status"]=="needs_check"

def test_housing_route_missing_brf_genuine_is_not_ok():
    from rules import housing_route
    r=housing_route({"home":"Bostadsrätt","used_as_private_home":"Ja"})
    assert r["status"]=="needs_check"

def test_housing_route_explicit_yes_is_ok():
    from rules import housing_route
    r=housing_route({"home":"Villa","used_as_private_home":"Ja"})
    assert r["status"]=="ok"
