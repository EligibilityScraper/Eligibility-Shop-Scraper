import streamlit as st
import re
import csv
import io
from datetime import datetime

st.set_page_config(
    page_title="Pizza Shop Eligibility Checker",
    page_icon="🍕",
    layout="centered"
)

st.markdown("""
<style>
.eligible { background:#e8f5e9; color:#1b5e20; padding:6px 14px; border-radius:8px; font-weight:600; display:inline-block; }
.ineligible { background:#ffebee; color:#b71c1c; padding:6px 14px; border-radius:8px; font-weight:600; display:inline-block; }
.flag { background:#fff8e1; color:#e65100; padding:6px 14px; border-radius:8px; font-weight:600; display:inline-block; }
.rule-tag { background:#f0f0f0; color:#333; padding:2px 8px; border-radius:4px; font-size:0.8em; margin:2px; display:inline-block; }
.conf-high { color:#2e7d32; font-weight:600; }
.conf-med { color:#e65100; font-weight:600; }
.conf-low { color:#b71c1c; font-weight:600; }
</style>
""", unsafe_allow_html=True)

# ── CHAIN / INSTANT DISQUALIFIER DATABASE ──────────────────────────────────

INSTANT_CHAINS = [
    # (regex pattern, display name, reason, rule)
    (r"corner\s+shoppe", "Corner Shoppe", "Ledo Pizza Corner Shoppe — major chain (100+ locations)", "Rule 4"),
    (r"cravin'?s\s+to\s+order", "Cravin's To Order", "C-store proprietary pizza program", "Rule 4"),
    (r"epsi,?\s+inc\.?", "EPSI Inc.", "Domino's franchise operator (28+ locations)", "Rule 4"),
    (r"slice\s+house\s+by\s+tony", "Slice House by Tony Gemignani", "Franchise (120+ locations)", "Rule 4"),
    (r"wing\s+street", "Wing Street", "Pizza Hut sub-brand, major chain", "Rule 4"),
    (r"noble\s+roman'?s?", "Noble Roman's", "Major chain (200+ locations)", "Rule 4"),
    (r"hunt\s+brothers\s+pizza", "Hunt Brothers Pizza", "C-store program (10,000+ locations)", "Rule 4"),
    (r"little\s+caesars", "Little Caesars", "Major chain", "Rule 4"),
    (r"papa\s+john'?s", "Papa John's", "Major chain", "Rule 4"),
    (r"\bdomino'?s\b", "Domino's", "Major chain", "Rule 4"),
    (r"pizza\s+hut", "Pizza Hut", "Major chain", "Rule 4"),
    (r"american\s+flatbread", "American Flatbread", "Franchise (11+ locations)", "Rule 4"),
    (r"original\s+buscemi'?s?|buscemi'?s\s+of", "Buscemi's", "Franchise (55+ locations)", "Rule 4"),
    (r"slice\s+factory", "Slice Factory", "Franchise (12+ locations)", "Rule 4"),
    (r"palio'?s\s+pizza", "Palio's Pizza Cafe", "Franchise (10+ locations)", "Rule 4"),
    (r"mazzio'?s\s+go", "Mazzio's Go!!", "Chain/c-store program", "Rule 4"),
    (r"buddy\s+v'?s\s+cake", "Buddy V's Cake Slice", "Not a pizza concept (684 locations)", "Rule 1"),
]

INSTANT_NAME_INELIGIBLE = [
    (r"food\s+truck", "Food truck in name", "Mobile food unit", "Rule 3"),
    (r"on\s+wheels$", "'On wheels' in name", "Mobile food unit", "Rule 3"),
    (r"pizza\s+truck", "Pizza truck in name", "Mobile food unit", "Rule 3"),
    (r"\bcatering$", "Catering company name", "Not a public restaurant", "Rule 5"),
    (r"\b(inc\.|llc|enterprises|management\s+inc|group\s+llc|holdings)\s*$",
     "Corporate entity name", "Not a consumer-facing restaurant name", "Rule 6"),
]

NON_PIZZA_KEYWORDS = [
    (r"\b(sushi|ramen|pho|thai|chinese|korean|japanese)\b", "Asian cuisine concept"),
    (r"\b(taqueria|tacos?\b|burritos?|mexican\s+food|cubano|cuban\s+food)\b", "Mexican/Cuban concept"),
    (r"\b(bbq|barbecue|smokehouse)\b", "BBQ concept"),
    (r"\b(burger|burgers?|hamburger)\b", "Burger concept"),
    (r"\b(wings?\s+and|wing\s+stop|wingstop|hot\s+chicken)\b", "Wings/chicken concept"),
    (r"\b(seafood|oyster\s+bar|clamcakes?|shrimp\s+house)\b", "Seafood concept"),
    (r"\b(ethiopian|peruvian|indian\s+cuisine|curry\s+kitchen)\b", "Non-pizza ethnic cuisine"),
    (r"\b(boba|bubble\s+tea|smoothie\s+bar)\b", "Beverage concept"),
    (r"\b(coffee\s+roaster|coffee\s+bistro|cafe\s+coffee)\b", "Coffee concept"),
    (r"\bslider\s+bar\b", "Slider concept"),
    (r"\bliquor\s+store\b|\bbottle\s+shop\b|\bbeverage\s+store\b", "Alcohol retail"),
    (r"\bbait\s+(&|and)\s+sport\b|\btackle\s+shop\b", "Bait/tackle shop"),
    (r"\bantique\b|\bfurniture\b|\bplumbing\b|\belectric\b", "Non-food business"),
    (r"\bplasma\s+center\b|\bmedical\b|\bdental\b", "Medical/service business"),
    (r"\bdog\s+walk\b|\bpet\s+service\b", "Pet service"),
    (r"\brestaurant\s+equipment\b", "Equipment supplier"),
]

ADDRESS_FLAGS = [
    (r"airport|terminal\s+[a-z0-9]|airside|o'hare|laguardia|\bsfo\b|\bewr\b|\bfll\b|\btpa\b|\bphl\b|\biah\b|\bdfw\b|\bord\b|\bjfk\b|\blax\b",
     "Airport address — boarding pass required", "Rule 5"),
    (r"disney\s+world|disneyland|universal\s+(studios|orlando)|six\s+flags|busch\s+gardens|seaworld|dollywood|dreammore|osceola\s+pkwy.*lake\s+buena|seven\s+seas\s+drive|carowinds",
     "Theme park — paid admission required", "Rule 5"),
    (r"student\s+(union|center|dining)|campus\s+dining|residence\s+hall|unthank\s+hall|sharwan\s+smith|vera\s+king\s+farris|ave\s+of\s+champions|lomb\s+memorial",
     "University campus dining — not publicly accessible", "Rule 5"),
    (r"seneca\s+allegany|kalahari|mohegan\s+sun|allegiant\s+stadium|levi'?s?\s+stadium|fisher\s+island",
     "Casino/stadium/private island venue", "Rule 5"),
    (r"military\s+base|\bafb\b|air\s+force\s+base|fort\s+sill|fort\s+bragg",
     "Military base — not publicly accessible", "Rule 5"),
    (r"sam'?s\s+club|costco|walmart\s+supercenter",
     "Members-only warehouse store", "Rule 5"),
    (r"\brv\s+resort\b|\bcampground\b",
     "RV resort/campground — not a public restaurant", "Rule 5"),
]

INCOMPLETE_ADDRESS_FLAGS = [
    r"^\d+\s+(st|ave|blvd|rd|dr|ln|way|hwy)\s*$",
    r"^[a-z\s]+(st|ave|blvd|rd|dr|ln|way|hwy)\s*$",
]

PIZZA_POSITIVE = [
    r"\bpizza\b", r"\bpizzeria\b", r"\bpizz?a\b", r"\bapizza\b", r"\bpitsa\b",
    r"\bpixxa\b", r"\bpizxa\b", r"\bslice\b", r"\bslices\b", r"\bcalzone\b",
    r"\bcalzones\b", r"\bpanzerotti\b", r"\bpinsa\b", r"\bfocacceria\b",
    r"\bstromboli\b", r"\bneapolitan\b", r"\bsicilian\b", r"\bwood.?fired\b",
    r"\bwoodfired\b", r"\bcrust\b", r"\bdough\b", r"\bdoughs\b", r"\bovenworks\b",
    r"\bpie\s+shop\b", r"\bpizzabar\b", r"\bnew\s+haven\s+style\b",
    r"\bny.?style\b", r"\bdetroit.?style\b",
]

PIZZA_LIKELY_ITALIAN = [
    r"\bitalian\b", r"\btrattoria\b", r"\bosteria\b", r"\bristorante\b",
    r"\bpuglia\b", r"\bsicilia\b", r"\btoscana\b", r"\babruzzo\b",
    r"\bnapol\b", r"\bnonna\b", r"\bnonne\b", r"\bmama\b|\bmamma\b",
    r"\bbottega\b", r"\balimentari\b", r"\bmercato\b",
]

PIZZA_NEGATIVE_CONTEXT = [
    r"\bseafood\b", r"\boycster\b", r"\bsushi\b", r"\bbbq\b", r"\bburger\b",
    r"\bwings\b", r"\bchinese\b", r"\bthai\b", r"\bkorean\b",
    r"\bbreakfast\b|\bpancake\b", r"\bsteakhouse\b|\bsteak\s+house\b",
]

# ── CORE EVALUATION LOGIC ─────────────────────────────────────────────────

def check_eligibility(name, street, suite, city, state, zip_code, phone, extra):
    results = {
        "status": None,
        "fail_rules": [],
        "notes": [],
        "confidence": 50,
        "flags": [],
    }

    name_lower = name.lower().strip()
    full_address = " ".join(filter(None, [street, suite, city, state, zip_code])).lower()

    # ── Rule 7: USA check ──
    intl_patterns = [
        r"\b(via|viale|corso|piazza)\s+\w+",
        r"\b(milano|roma|napoli|torino|garbagnate|saronno|parabiago)\b",
    ]
    for pat in intl_patterns:
        if re.search(pat, full_address, re.I) or re.search(pat, name_lower, re.I):
            results["status"] = "INELIGIBLE"
            results["fail_rules"].append("Rule 7")
            results["notes"].append("International address detected (Italy) — USA only.")
            results["confidence"] = 99
            return results

    # ── Rule 4: Known major chains ──
    for pattern, chain_name, reason, rule in INSTANT_CHAINS:
        if re.search(pattern, name_lower, re.I):
            results["status"] = "INELIGIBLE"
            results["fail_rules"].append(rule)
            results["notes"].append(f"{chain_name}: {reason}")
            results["confidence"] = 99
            return results

    # ── Rule 3 / Rule 6: Instant name disqualifiers ──
    for pattern, label, reason, rule in INSTANT_NAME_INELIGIBLE:
        if re.search(pattern, name_lower, re.I):
            results["status"] = "INELIGIBLE"
            results["fail_rules"].append(rule)
            results["notes"].append(f"{label} — {reason}.")
            results["confidence"] = 95
            return results

    # ── Rule 5: Address-based disqualifiers ──
    for pattern, reason, rule in ADDRESS_FLAGS:
        if re.search(pattern, full_address, re.I) or re.search(pattern, name_lower, re.I):
            results["status"] = "INELIGIBLE"
            results["fail_rules"].append(rule)
            results["notes"].append(reason)
            results["confidence"] = 97
            return results

    # ── Rule 6: No building number ──
    if street and not zip_code and not city:
        for pat in INCOMPLETE_ADDRESS_FLAGS:
            if re.match(pat, street.strip(), re.I):
                results["status"] = "INELIGIBLE"
                results["fail_rules"].append("Rule 6")
                results["notes"].append("Incomplete address — no building number or city provided.")
                results["confidence"] = 90
                return results

    if not street and not city and not zip_code and not phone:
        results["flags"].append("No address or phone provided — cannot verify location.")

    # ── Rule 1: Non-pizza concept check ──
    for pattern, label in NON_PIZZA_KEYWORDS:
        if re.search(pattern, name_lower, re.I):
            results["status"] = "INELIGIBLE"
            results["fail_rules"].append("Rule 1")
            results["notes"].append(f"{label} — pizza not primary focus.")
            results["confidence"] = 90
            return results

    # ── Rule 1: Pizza positive signals ──
    pizza_confirmed = any(re.search(p, name_lower, re.I) for p in PIZZA_POSITIVE)
    pizza_likely = any(re.search(p, name_lower, re.I) for p in PIZZA_LIKELY_ITALIAN)
    negative_context = any(re.search(p, name_lower, re.I) for p in PIZZA_NEGATIVE_CONTEXT)
    extra_lower = extra.lower() if extra else ""
    if re.search(r"gas\s+station|c.?store|convenience\s+store|inside\s+a", extra_lower, re.I):
        results["status"] = "INELIGIBLE"
        results["fail_rules"].append("Rule 1")
        results["notes"].append("C-store / gas station context noted — pizza not primary establishment.")
        results["confidence"] = 88
        return results

    # ── Build FLAG result for unknowns ──
    if pizza_confirmed:
        results["status"] = "FLAG"
        results["confidence"] = 65
        results["notes"].append("Pizza confirmed in name — verify open status and location count via GBP.")
    elif pizza_likely and not negative_context:
        results["status"] = "FLAG"
        results["confidence"] = 50
        results["notes"].append("Italian-themed name — pizza likely but needs GBP confirmation.")
    else:
        results["status"] = "FLAG"
        results["confidence"] = 30
        results["notes"].append("Cannot confirm pizza focus from name alone — requires manual GBP research.")

    # ── Additional flags ──
    if re.search(r"\bbrewing\b|\bbrewery\b|\bbrew\s+house\b", name_lower, re.I):
        results["flags"].append("Brewery concept — confirm pizza is on menu.")
    if re.search(r"\bsaloon\b|\blounge\b|\btavern\b|\bpub\b|\bbar\b", name_lower, re.I):
        results["flags"].append("Bar/pub concept — confirm pizza is primary, not incidental.")
    if re.search(r"\bmarket\b|\bstore\b|\bdeli\b", name_lower, re.I):
        results["flags"].append("Market/deli concept — confirm pizza is primary offering.")
    if re.search(r"\bgolf\b|\bski\b|\bresort\b|\blodge\b|\binn\b", name_lower, re.I):
        results["flags"].append("Resort/seasonal venue — confirm year-round hours (4+ days/week).")
    if zip_code and len(zip_code) < 5:
        results["flags"].append(f"ZIP code '{zip_code}' may be missing leading zero (e.g. NJ, MA, CT).")
    if state.upper() in ["NJ","MA","CT","VT","RI","ME","NH"] and zip_code and not zip_code.startswith("0"):
        results["flags"].append(f"ZIP likely needs leading zero for {state.upper()} addresses.")

    return results


def render_status_badge(status):
    if status == "ELIGIBLE":
        return '<span class="eligible">✅ Eligible</span>'
    elif status == "INELIGIBLE":
        return '<span class="ineligible">❌ Ineligible</span>'
    else:
        return '<span class="flag">⚠️ Flag — manual review needed</span>'


def conf_color_class(c):
    if c >= 70: return "conf-high"
    if c >= 45: return "conf-med"
    return "conf-low"


# ── STREAMLIT UI ──────────────────────────────────────────────────────────

st.title("🍕 Pizza Shop Eligibility Checker")
st.caption("Enter what you have — all fields except name are optional. Instant checks against 7 eligibility rules.")

with st.form("eligibility_form", clear_on_submit=False):
    st.subheader("Business info")
    name = st.text_input("Business name *", placeholder="e.g. Gemelli's Italian Market")

    col1, col2 = st.columns(2)
    with col1:
        street = st.text_input("Street address", placeholder="e.g. 12169 Darnestown Rd")
    with col2:
        suite = st.text_input("Suite / unit", placeholder="e.g. Suite B")

    col3, col4, col5 = st.columns(3)
    with col3:
        city = st.text_input("City", placeholder="e.g. Gaithersburg")
    with col4:
        state = st.text_input("State", placeholder="e.g. MD", max_chars=2)
    with col5:
        zip_code = st.text_input("ZIP", placeholder="e.g. 20878", max_chars=10)

    col6, col7 = st.columns(2)
    with col6:
        phone = st.text_input("Phone", placeholder="e.g. (240) 246-7674")
    with col7:
        extra = st.text_input("Extra context (optional)", placeholder="e.g. inside a gas station")

    submitted = st.form_submit_button("🔍 Check eligibility", use_container_width=True)

if submitted:
    if not name.strip():
        st.error("Please enter a business name.")
    else:
        result = check_eligibility(
            name.strip(), street.strip(), suite.strip(),
            city.strip(), state.strip().upper(),
            zip_code.strip(), phone.strip(), extra.strip()
        )

        st.divider()
        st.subheader("Result")

        col_status, col_conf = st.columns([2, 1])
        with col_status:
            st.markdown(render_status_badge(result["status"]), unsafe_allow_html=True)
            st.markdown(f"**{name.strip()}**")
            addr_parts = [p for p in [street, suite, city, state, zip_code] if p.strip()]
            if addr_parts:
                st.caption(" · ".join(addr_parts))
        with col_conf:
            c = result["confidence"]
            cls = conf_color_class(c)
            st.markdown(f'<span class="{cls}">Confidence: {c}/100</span>', unsafe_allow_html=True)
            st.progress(c / 100)

        if result["fail_rules"]:
            st.markdown("**Fail rules:** " + " ".join(
                f'<span class="rule-tag">{r}</span>' for r in result["fail_rules"]
            ), unsafe_allow_html=True)

        if result["notes"]:
            for note in result["notes"]:
                st.info(note)

        if result["flags"]:
            st.warning("**Additional checks needed:**")
            for flag in result["flags"]:
                st.markdown(f"- {flag}")

        if result["status"] == "FLAG":
            st.markdown("""
**Next steps for flagged entries:**
- Search Google Business Profile for current open/closed status
- Confirm pizza is on the menu (not just incidental)
- Check hours: must be open ≥4 days/week
- Verify location count if it looks like a chain
""")

        # ── Save to session history ──
        if "history" not in st.session_state:
            st.session_state.history = []

        st.session_state.history.insert(0, {
            "Checked At": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "Name": name.strip(),
            "Address": " ".join(filter(None, [street, suite, city, state, zip_code])),
            "Phone": phone.strip(),
            "Status": result["status"],
            "Fail Rules": ", ".join(result["fail_rules"]),
            "Notes": " | ".join(result["notes"]),
            "Confidence": result["confidence"],
        })

# ── HISTORY + EXPORT ─────────────────────────────────────────────────────

if "history" in st.session_state and st.session_state.history:
    st.divider()
    st.subheader("Recent checks")

    col_hist, col_export = st.columns([3, 1])
    with col_hist:
        st.caption(f"{len(st.session_state.history)} entries this session")
    with col_export:
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=[
            "Checked At","Name","Address","Phone",
            "Status","Fail Rules","Notes","Confidence"
        ])
        writer.writeheader()
        writer.writerows(st.session_state.history)
        st.download_button(
            "⬇️ Download CSV",
            data=buf.getvalue(),
            file_name=f"eligibility_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            use_container_width=True
        )

    for entry in st.session_state.history[:20]:
        with st.expander(f"{entry['Status']} — {entry['Name']} ({entry['Checked At']})"):
            st.write(f"**Address:** {entry['Address'] or '—'}")
            st.write(f"**Fail rules:** {entry['Fail Rules'] or 'None'}")
            st.write(f"**Notes:** {entry['Notes'] or '—'}")
            st.write(f"**Confidence:** {entry['Confidence']}/100")

    if st.button("🗑️ Clear history"):
        st.session_state.history = []
        st.rerun()
