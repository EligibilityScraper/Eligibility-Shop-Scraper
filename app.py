import streamlit as st
import re
import csv
import io
from datetime import datetime
import urllib.parse

st.set_page_config(
    page_title="Pizza Shop Eligibility Checker",
    page_icon="🍕",
    layout="centered"
)

st.markdown("""
<style>
.eligible { background:#e8f5e9; color:#1b5e20; padding:8px 16px; border-radius:8px; font-weight:700; display:inline-block; font-size:1.1em; }
.ineligible { background:#ffebee; color:#b71c1c; padding:8px 16px; border-radius:8px; font-weight:700; display:inline-block; font-size:1.1em; }
.flag { background:#fff8e1; color:#e65100; padding:8px 16px; border-radius:8px; font-weight:700; display:inline-block; font-size:1.1em; }
.reason-box { background:#fff3e0; border-left:4px solid #e65100; padding:10px 14px; border-radius:4px; margin:8px 0; font-size:1em; }
.ineligible-box { background:#ffebee; border-left:4px solid #b71c1c; padding:10px 14px; border-radius:4px; margin:8px 0; font-size:1em; }
.conf-high { color:#2e7d32; font-weight:600; }
.conf-med { color:#e65100; font-weight:600; }
.conf-low { color:#b71c1c; font-weight:600; }
.verify-item { background:#e3f2fd; border-left:4px solid #1565c0; padding:8px 14px; border-radius:4px; margin:4px 0; font-size:0.95em; }
</style>
""", unsafe_allow_html=True)

# ── CHAIN / INSTANT DISQUALIFIER DATABASE ─────────────────────────────────

INSTANT_CHAINS = [
    (r"corner\s+shoppe", "Ledo Pizza Corner Shoppe", "major franchise chain with 100+ locations"),
    (r"cravin'?s\s+to\s+order", "Cravin's To Order", "a convenience store proprietary pizza program, not a standalone restaurant"),
    (r"epsi,?\s+inc\.?", "EPSI Inc.", "a Domino's franchise operator running 28+ locations"),
    (r"slice\s+house\s+by\s+tony", "Slice House by Tony Gemignani", "a franchise chain with 120+ locations"),
    (r"wing\s+street", "Wing Street", "a Pizza Hut sub-brand and major chain"),
    (r"noble\s+roman'?s?", "Noble Roman's", "a major chain with 200+ locations"),
    (r"hunt\s+brothers\s+pizza", "Hunt Brothers Pizza", "a convenience store pizza program in 10,000+ locations — not a standalone restaurant"),
    (r"little\s+caesars", "Little Caesars", "a major national franchise chain"),
    (r"papa\s+john'?s", "Papa John's", "a major national franchise chain"),
    (r"\bdomino'?s\b", "Domino's", "a major national franchise chain"),
    (r"pizza\s+hut", "Pizza Hut", "a major national franchise chain"),
    (r"american\s+flatbread", "American Flatbread", "a franchise chain with 11+ locations"),
    (r"original\s+buscemi'?s?|buscemi'?s\s+of", "Buscemi's", "a franchise chain with 55+ locations"),
    (r"slice\s+factory", "Slice Factory", "a franchise chain with 12+ locations"),
    (r"palio'?s\s+pizza", "Palio's Pizza Cafe", "a franchise chain with 10+ locations"),
    (r"mazzio'?s\s+go", "Mazzio's Go!!", "a chain/convenience store program"),
    (r"buddy\s+v'?s\s+cake", "Buddy V's Cake Slice", "a dessert concept (684 locations) — not a pizza restaurant"),
]

INSTANT_NAME_INELIGIBLE = [
    (r"food\s+truck", "food truck", "Food trucks and mobile units are not eligible — must be a permanent brick-and-mortar location."),
    (r"on\s+wheels$", "mobile unit", "Mobile food units are not eligible — must be a permanent brick-and-mortar location."),
    (r"pizza\s+truck", "pizza truck", "Food trucks are not eligible — must be a permanent brick-and-mortar location."),
    (r"\bcatering$", "catering company", "Catering companies are not eligible — must be a public-facing restaurant."),
    (r"\b(inc\.|llc|enterprises|management\s+inc|group\s+llc|holdings)\s*$",
     "corporate entity", "This looks like a corporate/legal entity name, not a consumer-facing restaurant. Please submit the actual restaurant name."),
]

NON_PIZZA_KEYWORDS = [
    (r"\b(sushi|ramen|pho|thai|chinese|korean|japanese)\b", "Asian cuisine restaurant"),
    (r"\b(taqueria|tacos?\b|burritos?|mexican\s+food|cubano|cuban\s+food)\b", "Mexican or Cuban restaurant"),
    (r"\b(bbq|barbecue|smokehouse)\b", "BBQ or smokehouse"),
    (r"\b(burger|burgers?|hamburger)\b", "burger restaurant"),
    (r"\b(wings?\s+and|wing\s+stop|wingstop|hot\s+chicken)\b", "wings or chicken concept"),
    (r"\b(seafood|oyster\s+bar|clamcakes?|shrimp\s+house)\b", "seafood restaurant"),
    (r"\b(ethiopian|peruvian|indian\s+cuisine|curry\s+kitchen)\b", "non-pizza ethnic cuisine restaurant"),
    (r"\b(boba|bubble\s+tea|smoothie\s+bar)\b", "beverage concept"),
    (r"\b(coffee\s+roaster|coffee\s+bistro|cafe\s+coffee)\b", "coffee concept"),
    (r"\bslider\s+bar\b", "slider restaurant"),
    (r"\bliquor\s+store\b|\bbottle\s+shop\b|\bbeverage\s+store\b", "alcohol retail store"),
    (r"\bbait\s+(&|and)\s+sport\b|\btackle\s+shop\b", "bait and tackle shop — not a food business"),
    (r"\bantique\b|\bfurniture\b|\bplumbing\b|\belectric\b", "non-food business"),
    (r"\bplasma\s+center\b|\bmedical\b|\bdental\b", "medical or service business — not a restaurant"),
    (r"\bdog\s+walk\b|\bpet\s+service\b", "pet service business — not a restaurant"),
    (r"\brestaurant\s+equipment\b", "restaurant equipment supplier — not a restaurant"),
]

ADDRESS_FLAGS = [
    (r"airport|terminal\s+[a-z0-9]|airside|o'hare|laguardia|\bsfo\b|\bewr\b|\bfll\b|\btpa\b|\bphl\b|\biah\b|\bdfw\b|\bord\b|\bjfk\b|\blax\b",
     "located inside an airport, which requires a boarding pass to access — not open to the general public"),
    (r"disney\s+world|disneyland|universal\s+(studios|orlando)|six\s+flags|busch\s+gardens|seaworld|dollywood|dreammore|osceola\s+pkwy.*lake\s+buena|seven\s+seas\s+drive|carowinds",
     "located inside a theme park, which requires paid admission — not open to the general public"),
    (r"student\s+(union|center|dining)|campus\s+dining|residence\s+hall|unthank\s+hall|sharwan\s+smith|vera\s+king\s+farris|ave\s+of\s+champions|lomb\s+memorial",
     "located on a university campus in a restricted dining area — not open to the general public"),
    (r"seneca\s+allegany|kalahari|mohegan\s+sun|allegiant\s+stadium|levi'?s?\s+stadium|fisher\s+island",
     "located inside a casino, stadium, or private venue — not open to the general public"),
    (r"military\s+base|\bafb\b|air\s+force\s+base|fort\s+sill|fort\s+bragg",
     "located on a military base — not open to the general public"),
    (r"sam'?s\s+club|costco|walmart\s+supercenter",
     "located inside a members-only warehouse store — not open to the general public"),
    (r"\brv\s+resort\b|\bcampground\b",
     "located at an RV resort or campground — not a standalone public restaurant"),
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

# ── CORE EVALUATION LOGIC ──────────────────────────────────────────────────

def check_eligibility(name, street, suite, city, state, zip_code, phone, extra):
    results = {
        "status": None,
        "reason": "",
        "notes": [],
        "confidence": 50,
        "flags": [],
        "verify": [],
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
            results["reason"] = "This location appears to be outside the USA. Only US-based restaurants are eligible."
            results["confidence"] = 99
            return results

    # ── Rule 4: Known major chains ──
    for pattern, chain_name, reason in INSTANT_CHAINS:
        if re.search(pattern, name_lower, re.I):
            results["status"] = "INELIGIBLE"
            results["reason"] = f"This shop is not eligible because {chain_name} is {reason}."
            results["confidence"] = 99
            return results

    # ── Rule 3 / Rule 6: Instant name disqualifiers ──
    for pattern, label, reason in INSTANT_NAME_INELIGIBLE:
        if re.search(pattern, name_lower, re.I):
            results["status"] = "INELIGIBLE"
            results["reason"] = reason
            results["confidence"] = 95
            return results

    # ── Rule 5: Address-based disqualifiers ──
    for pattern, reason in ADDRESS_FLAGS:
        if re.search(pattern, full_address, re.I) or re.search(pattern, name_lower, re.I):
            results["status"] = "INELIGIBLE"
            results["reason"] = f"This location is {reason}."
            results["confidence"] = 97
            return results

    # ── Rule 6: Incomplete address ──
    if street and not zip_code and not city:
        for pat in INCOMPLETE_ADDRESS_FLAGS:
            if re.match(pat, street.strip(), re.I):
                results["status"] = "INELIGIBLE"
                results["reason"] = "The address provided is incomplete — a full street address with city or ZIP is required to verify this location."
                results["confidence"] = 90
                return results

    if not street and not city and not zip_code and not phone:
        results["flags"].append("No address or phone provided — location cannot be verified.")

    # ── Rule 1: Non-pizza concept ──
    for pattern, label in NON_PIZZA_KEYWORDS:
        if re.search(pattern, name_lower, re.I):
            results["status"] = "INELIGIBLE"
            results["reason"] = f"This appears to be a {label}, not a pizza-focused restaurant. Only establishments where pizza is the primary offering are eligible."
            results["confidence"] = 90
            return results

    # ── Ghost kitchen / virtual brand ──
    extra_lower = extra.lower() if extra else ""
    if re.search(r"ghost\s+kitchen|virtual\s+brand|dark\s+kitchen|delivery\s+only", extra_lower, re.I):
        results["status"] = "INELIGIBLE"
        results["reason"] = "Ghost kitchens and virtual/delivery-only brands are not eligible — must be a brick-and-mortar location open to walk-in customers."
        results["confidence"] = 95
        return results

    # ── Rule 1: C-store / gas station context ──
    if re.search(r"gas\s+station|c.?store|convenience\s+store|inside\s+a", extra_lower, re.I):
        results["status"] = "INELIGIBLE"
        results["reason"] = "Pizza served inside a gas station or convenience store is not eligible — must be a standalone restaurant where pizza is the primary business."
        results["confidence"] = 88
        return results

    # ── Build FLAG result ──
    pizza_confirmed = any(re.search(p, name_lower, re.I) for p in PIZZA_POSITIVE)
    pizza_likely = any(re.search(p, name_lower, re.I) for p in PIZZA_LIKELY_ITALIAN)
    negative_context = any(re.search(p, name_lower, re.I) for p in PIZZA_NEGATIVE_CONTEXT)

    if pizza_confirmed:
        results["status"] = "FLAG"
        results["confidence"] = 65
        results["reason"] = "Pizza is confirmed in the name, but open status and location count still need to be verified."
        results["verify"] = [
            "Search Google Business Profile to confirm the shop is currently open",
            "Check hours — must be open at least 4 days per week",
            "Confirm pizza is the primary menu item, not just incidental",
            "Check if this is part of a chain (3+ locations may disqualify)",
        ]
    elif pizza_likely and not negative_context:
        results["status"] = "FLAG"
        results["confidence"] = 50
        results["reason"] = "This looks like an Italian restaurant that likely serves pizza, but it needs to be confirmed."
        results["verify"] = [
            "Search Google Business Profile to confirm pizza is on the menu",
            "Confirm the shop is currently open and operating",
            "Check hours — must be open at least 4 days per week",
        ]
    else:
        results["status"] = "FLAG"
        results["confidence"] = 30
        results["reason"] = "Cannot confirm this is a pizza-focused restaurant from the name alone — manual research required."
        results["verify"] = [
            "Search Google Business Profile to confirm pizza is the primary offering",
            "Confirm the shop is currently open and publicly accessible",
            "Check hours — must be open at least 4 days per week",
        ]

    # ── Additional flags ──
    if re.search(r"\bbrewing\b|\bbrewery\b|\bbrew\s+house\b", name_lower, re.I):
        results["flags"].append("Brewery — confirm pizza is a main menu item, not just a side offering.")
    if re.search(r"\bsaloon\b|\blounge\b|\btavern\b|\bpub\b|\bbar\b", name_lower, re.I):
        results["flags"].append("Bar or pub — confirm pizza is the primary food offering, not incidental.")
    if re.search(r"\bmarket\b|\bstore\b|\bdeli\b", name_lower, re.I):
        results["flags"].append("Market or deli — confirm pizza is the primary offering, not retail.")
    if re.search(r"\bgolf\b|\bski\b|\bresort\b|\blodge\b|\binn\b", name_lower, re.I):
        results["flags"].append("Resort or seasonal venue — confirm it is open year-round, at least 4 days per week.")
    if zip_code and len(zip_code) < 5:
        results["flags"].append(f"ZIP code '{zip_code}' may be missing a leading zero (common for NJ, MA, CT, VT, RI, ME, NH).")
    if state.upper() in ["NJ","MA","CT","VT","RI","ME","NH"] and zip_code and not zip_code.startswith("0"):
        results["flags"].append(f"ZIP code likely needs a leading zero for {state.upper()} addresses.")

    return results


def render_status_badge(status):
    if status == "ELIGIBLE":
        return '<span class="eligible">✅ Eligible</span>'
    elif status == "INELIGIBLE":
        return '<span class="ineligible">❌ Not Eligible</span>'
    else:
        return '<span class="flag">⚠️ Needs Manual Review</span>'


def conf_color_class(c):
    if c >= 70: return "conf-high"
    if c >= 45: return "conf-med"
    return "conf-low"


def google_search_url(name, city, state):
    query = " ".join(filter(None, [name, city, state]))
    return f"https://www.google.com/search?q={urllib.parse.quote(query)}"


def google_maps_url(name, street, city, state, zip_code):
    query = " ".join(filter(None, [name, street, city, state, zip_code]))
    return f"https://www.google.com/maps/search/{urllib.parse.quote(query)}"


# ── STREAMLIT UI ───────────────────────────────────────────────────────────

import anthropic

st.title("🍕 Pizza Shop Eligibility Checker")
st.caption("Enter what you have — all fields except name are optional.")

tab1, tab2 = st.tabs(["📋 Form Checker", "💬 Chat Checker"])

with tab1:
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
            extra = st.text_input("Extra context (optional)", placeholder="e.g. ghost kitchen, inside a gas station")

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

            # Plain English reason
            if result["reason"]:
                box_class = "ineligible-box" if result["status"] == "INELIGIBLE" else "reason-box"
                st.markdown(f'<div class="{box_class}">{result["reason"]}</div>', unsafe_allow_html=True)

            # Additional flags
            if result["flags"]:
                for flag in result["flags"]:
                    st.warning(flag)

            # What to verify next
            if result["verify"]:
                st.markdown("**What to verify:**")
                for item in result["verify"]:
                    st.markdown(f'<div class="verify-item">🔎 {item}</div>', unsafe_allow_html=True)

            # Quick search links
            search_url = google_search_url(name.strip(), city.strip(), state.strip())
            maps_url = google_maps_url(name.strip(), street.strip(), city.strip(), state.strip(), zip_code.strip())
            st.markdown(f"🔗 [Search Google for this business]({search_url}) &nbsp;&nbsp; 📍 [View on Google Maps]({maps_url})", unsafe_allow_html=True)

            # Save to history
            if "history" not in st.session_state:
                st.session_state.history = []

            st.session_state.history.insert(0, {
                "Checked At": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "Name": name.strip(),
                "Address": " ".join(filter(None, [street, suite, city, state, zip_code])),
                "Phone": phone.strip(),
                "Status": result["status"],
                "Reason": result["reason"],
                "Confidence": result["confidence"],
            })


with tab2:
    st.markdown("### 💬 Ask me about a restaurant")
    st.caption("Type naturally — e.g. 'Check Oregon Coast Pizzeria at 2165 Winchester Ave, Reedsport OR' or just a name and city.")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_input = st.chat_input("Type a restaurant name, address, or question...")

    if user_input:
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            with st.spinner("Checking..."):
                try:
                    client = anthropic.Anthropic()

                    system_prompt = """You are a Pizza Shop Eligibility Checker assistant. Your job is to help qualify whether a restaurant is eligible based on these rules:

1. Must be a pizza-focused establishment. Not a burger joint, taqueria, sushi place, BBQ, wings-only, seafood, or non-food business.
2. Must be a brick-and-mortar location open to the public at least 4 days per week. No ghost kitchens or delivery-only brands.
3. No food trucks, mobile units, or pop-ups.
4. No major chains — Little Caesars, Domino's, Papa John's, Pizza Hut, Hunt Brothers, Noble Roman's, etc. are all disqualified.
5. Must be publicly accessible — no airports, theme parks, university campus dining, military bases, casinos, or members-only clubs.
6. Must have a valid physical US address.
7. Must be located in the USA.

When someone gives you a restaurant name and/or address, respond with:
- A clear verdict: ELIGIBLE ✅, NOT ELIGIBLE ❌, or NEEDS REVIEW ⚠️
- A plain English explanation of WHY — never say "Rule 1" or "Rule 4", always explain in plain language what the issue is
- What specifically needs to be checked if flagged

Be conversational and direct. Example of good response: "❌ Not eligible — Domino's is a major national franchise chain." Not: "Ineligible per Rule 4."
"""

                    messages = [{"role": m["role"], "content": m["content"]} for m in st.session_state.chat_history]

                    response = client.messages.create(
                        model="claude-sonnet-4-6",
                        max_tokens=1000,
                        system=system_prompt,
                        messages=messages
                    )

                    reply = response.content[0].text
                    st.markdown(reply)
                    st.session_state.chat_history.append({"role": "assistant", "content": reply})

                except Exception as e:
                    err_msg = f"⚠️ Could not reach AI service: {str(e)}"
                    st.error(err_msg)
                    st.session_state.chat_history.append({"role": "assistant", "content": err_msg})

    if st.session_state.chat_history:
        if st.button("🗑️ Clear chat", key="clear_chat"):
            st.session_state.chat_history = []
            st.rerun()


# ── HISTORY + EXPORT ──────────────────────────────────────────────────────

if "history" in st.session_state and st.session_state.history:
    st.divider()
    st.subheader("Recent checks")

    col_hist, col_export = st.columns([3, 1])
    with col_hist:
        st.caption(f"{len(st.session_state.history)} entries this session")
    with col_export:
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=[
            "Checked At", "Name", "Address", "Phone",
            "Status", "Reason", "Confidence"
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
            st.write(f"**Reason:** {entry['Reason'] or '—'}")
            st.write(f"**Confidence:** {entry['Confidence']}/100")

    if st.button("🗑️ Clear history"):
        st.session_state.history = []
        st.rerun()
