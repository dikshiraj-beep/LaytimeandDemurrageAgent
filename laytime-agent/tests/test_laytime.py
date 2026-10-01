"""Fast unit tests for the deterministic parts (no LLM, no network)."""
from laytime_agent.tools import documents as D
from laytime_agent.tools import evidence as E
from laytime_agent.tools import laytime as L
from laytime_agent.tools import terms as T


def test_simple_demurrage():
    c = L.calculate("2026-01-01 00:00", "2026-01-03 00:00", 24, [], 10000)
    assert c["result"] == "DEMURRAGE" and c["time_on_demurrage_hours"] == 24 and c["amount_usd"] == 10000


def test_once_on_demurrage_and_verifier_agree():
    ex = [{"start": "2026-01-01 06:00", "end": "2026-01-01 08:00", "reason": "rain", "applies_on_demurrage": False,
           "clause_ref": "Cl. 6", "evidence": "SOF"},
          {"start": "2026-01-02 06:00", "end": "2026-01-02 09:00", "reason": "rain", "applies_on_demurrage": False,
           "clause_ref": "Cl. 6", "evidence": "SOF"},
          {"start": "2026-01-02 10:00", "end": "2026-01-02 11:00", "reason": "shift", "applies_on_demurrage": True,
           "clause_ref": "Cl. 7", "evidence": "SOF"}]
    c = L.calculate("2026-01-01 00:00", "2026-01-03 00:00", 24, ex, 24000)
    # 2 h rain before expiry counted out; rain on day 2 is on demurrage -> counts; shifting excluded on demurrage
    assert c["laytime_expired"] == "2026-01-02 02:00"
    assert c["time_on_demurrage_hours"] == 21
    assert L.verify(c, ex) == []


def test_despatch():
    c = L.calculate("2026-01-01 00:00", "2026-01-01 12:00", 24, [], 20000, 0.5)
    assert c["result"] == "DESPATCH" and c["amount_usd"] == 5000


def test_rules_extract_recap_overrides():
    v = T.extract_rules("nor", 'NOR to be tendered only upon arrival at the customary anchorage within the port '
                               'limits. The words "whether in port or not" are deleted. Laytime to commence 6 '
                               'running hours after tender of valid NOR.', {"operation": "discharge"})
    assert v["place_required"] == "within_port_limits" and v["trigger"]["hours"] == 6


def test_grader_rejects_wrong_operation_and_negotiation():
    ctx = {"operation": "discharge"}
    load = {"title": "5. Laytime - Loading", "text": "Cargo to be loaded at the average rate of 10,000 metric tonnes "
            "per weather working day", "doc_type": "charter_party"}
    neg = {"title": "Email 1", "text": "Demurrage: USD 15,000 per day", "doc_type": "negotiation"}
    assert T.grade_rules("laytime_rate", load, ctx)[0] is False
    assert T.grade_rules("demurrage", neg, ctx)[0] is False


def test_event_classification_and_pairing():
    ev = [{"line": 1, "ts": "2026-06-14 22:00", "text": "Rain - discharging suspended"},
          {"line": 2, "ts": "2026-06-14 02:00", "text": "Rain stopped - discharging resumed"},
          {"line": 3, "ts": "2026-06-15 09:00", "text": "Shore crane No. 2 breakdown - discharging suspended"},
          {"line": 4, "ts": "2026-06-15 13:00", "text": "Shore crane repaired - discharging resumed"}]
    for e in ev:
        e.update(D.classify_event(e["text"]))
    p = D.pair_stoppages(ev)
    assert p[0]["cause"] == "rain" and p[0]["end"] < p[0]["start"]          # the typo is preserved for validation
    assert p[1]["cause"] == "breakdown" and p[1]["equipment"] == "shore"


def test_geo():
    ll = E.parse_latlon("16°05.2'N 060°51.3'E")
    d = E.haversine_nm(ll[0], ll[1], 16 + 10 / 60, 61 + 5 / 60)
    assert 13.5 < d < 14.5
