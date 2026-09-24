"""Fine-grained issue taxonomy (20 groups, 90 subcategories).

This is a SEPARATE, more detailed taxonomy from the 20-topical-category one in
`rag_clusters/config.py`. It is kept here (self-contained under kb_agent) so the
two coexist without coupling; `rag_clusters` is not touched.

Structure: `FINE_TAXONOMY` is a list of 20 group dicts, in display order. Each
group has:
    group_id       stable snake_case key (used as the "group" field in output)
    label          human-readable group name shown to the LLM
    subcategories  list of (key, label) — key is the snake_case subcategory id

The subcategory key is the canonical identifier (snake_case, matching the
group's keys). One unnumbered residual bucket ("other") is appended at the end
for blocks that fit nothing.

`KEY_TO_GROUP` maps a subcategory key -> its group_id.
`GROUP_LABELS` maps group_id -> label.
"""
from __future__ import annotations

FINE_TAXONOMY: list[dict] = [
    {
        "group_id": "pricing",
        "label": "Pricing",
        "subcategories": [
            ("high_entry_fee", "High entry / admission fee"),
            ("poor_value", "Poor value for money"),
            ("value_vs_duration", "Poor value relative to the duration"),
            ("overpriced_goods", "Overpriced food, drinks & souvenirs"),
        ],
    },
    {
        "group_id": "billing_and_payment",
        "label": "Billing & payment",
        "subcategories": [
            ("hidden_charges", "Hidden or unexpected extra charges"),
            ("price_mismatch", "Final price higher than quoted or advertised"),
            ("inconsistent_pricing", "Inconsistent, arbitrary or negotiable prices"),
            ("dual_pricing", "Tourists charged more than locals"),
            ("forced_guide_fee", "Mandatory or forced guide fees"),
            ("tipping_pressure", "Aggressive tipping demands"),
            ("payment_methods", "Payment problems: cash, card, ATM & currency"),
            ("refund_disputes", "Refund & cancellation disputes"),
        ],
    },
    {
        "group_id": "animal_welfare",
        "label": "Animal welfare",
        "subcategories": [
            ("captivity_conditions", "Animal captivity & confinement conditions"),
            ("poor_husbandry", "Poor husbandry, enclosure hygiene & animal health"),
            ("animal_stress", "Animal stress from crowds & tourist pressure"),
            ("general_cruelty", "General animal welfare & cruelty concerns"),
        ],
    },
    {
        "group_id": "wildlife_interaction",
        "label": "Wildlife interaction",
        "subcategories": [
            ("tourist_handling", "Tourists touching, handling or riding animals"),
            ("improper_feeding", "Feeding & overfeeding of animals"),
            ("dolphin_chasing", "Dolphin chasing & harassment by boats"),
            ("creature_removal", "Starfish & marine creatures removed from the water"),
            ("commercial_exploitation", "Commercial exploitation of animals for photos & entertainment"),
            ("false_sanctuary_claims", "False sanctuary & conservation claims"),
        ],
    },
    {
        "group_id": "scam",
        "label": "Scam",
        "subcategories": [
            ("outright_fraud", "Outright scam, fraud or tourist trap"),
            ("false_advertising", "Reality does not match photos or advertising"),
            ("fake_guides", "Fake, unlicensed or self-appointed guides"),
            ("agency_markup", "Hotel & agency mark-ups on excursions"),
        ],
    },
    {
        "group_id": "harassment",
        "label": "Harassment",
        "subcategories": [
            ("aggressive_vendors", "Aggressive vendors, touts & beach boys"),
            ("sales_pressure", "Persistent hard-selling & sales pressure"),
            ("street_harassment", "Harassment of tourists by locals & strangers"),
        ],
    },
    {
        "group_id": "crowding",
        "label": "Crowding",
        "subcategories": [
            ("visitor_overcrowding", "Overcrowding with tourists"),
            ("boat_congestion", "Too many boats in the area"),
            ("over_capacity_loading", "Boats & vehicles loaded beyond safe capacity"),
            ("oversized_groups", "Tour groups too large"),
            ("queues_and_waiting", "Queues & long waiting times"),
        ],
    },
    {
        "group_id": "staff_service",
        "label": "Staff & service",
        "subcategories": [
            ("rude_staff", "Rude, aggressive or unprofessional staff"),
            ("unhelpful_staff", "Unhelpful, absent or disorganised staff"),
            ("driver_conduct", "Reckless or unreliable drivers"),
        ],
    },
    {
        "group_id": "guide_quality",
        "label": "Guide quality",
        "subcategories": [
            ("guide_knowledge", "Guide lacks knowledge or gives little information"),
            ("language_barrier", "Guide language barrier"),
            ("disengaged_guides", "Disengaged guides who rush or abandon the group"),
        ],
    },
    {
        "group_id": "logistics",
        "label": "Logistics",
        "subcategories": [
            ("rushed_tour", "Tour too short or rushed"),
            ("duration_mismatch", "Duration differs from what was advertised"),
            ("delays_and_noshows", "Delays, no-shows & missed pickups"),
            ("poor_organisation", "Disorganised operations & poor crowd management"),
            ("transport_gaps", "Transport gaps, transfers & wrong drop-offs"),
            ("booking_failures", "Booking & communication failures"),
        ],
    },
    {
        "group_id": "access_and_wayfinding",
        "label": "Access & wayfinding",
        "subcategories": [
            ("road_quality", "Poor road conditions"),
            ("wayfinding", "Hard to find, wrong map location or poor signage"),
            ("parking", "Parking problems"),
            ("remoteness", "Remote, isolated or hard-to-reach location"),
            ("accessibility", "Accessibility & mobility barriers"),
        ],
    },
    {
        "group_id": "facilities",
        "label": "Facilities",
        "subcategories": [
            ("toilets", "Dirty, insufficient or paid toilets"),
            ("missing_amenities", "Missing basic amenities & facilities"),
            ("equipment_quality", "Poor, unhygienic or unavailable equipment"),
            ("interpretation_signage", "Lack of information & interpretation"),
        ],
    },
    {
        "group_id": "site_condition",
        "label": "Site condition",
        "subcategories": [
            ("structural_disrepair", "Structural disrepair & collapse of heritage sites"),
            ("low_maintenance", "Poor maintenance & general neglect"),
            ("renovation_closure", "Closed for renovation or construction"),
            ("restricted_access", "Closed, locked or off-limits to visitors"),
        ],
    },
    {
        "group_id": "experience_quality",
        "label": "Experience quality",
        "subcategories": [
            ("thin_content", "Small site with very limited exhibits or content"),
            ("unimpressive_site", "Unimpressive scenery or attraction"),
            ("unmet_expectations", "Experience did not meet expectations"),
            ("few_activities", "Limited activities available on site"),
            ("no_sightings", "Few or no animals / wildlife seen"),
            ("unspecified_dissatisfaction", "General dissatisfaction, no specific reason"),
        ],
    },
    {
        "group_id": "natural_conditions",
        "label": "Natural conditions",
        "subcategories": [
            ("tidal_restrictions", "Tides restricting swimming & beach access"),
            ("seaweed", "Seaweed, algae & sea grass on the beach"),
            ("water_visibility", "Poor underwater visibility & murky water"),
            ("weather_disruption", "Rough seas, wind & weather disruption"),
            ("heat_and_shade", "Heat, humidity & lack of shade"),
            ("pests", "Insects, bats & other nuisance creatures"),
            ("unsuitable_shoreline", "Unsuitable beach surface & water for swimming"),
        ],
    },
    {
        "group_id": "environmental_damage",
        "label": "Environmental damage",
        "subcategories": [
            ("reef_degradation", "Coral reef damaged, bleached or dead"),
            ("water_pollution", "Water pollution, sewage & fuel contamination"),
            ("over_commercialisation", "Over-commercialisation & loss of local authenticity"),
        ],
    },
    {
        "group_id": "cleanliness",
        "label": "Cleanliness",
        "subcategories": [
            ("litter", "Litter & plastic waste"),
            ("unhygienic_premises", "Dirty, unhygienic premises"),
            ("bad_odours", "Bad smells & odours"),
        ],
    },
    {
        "group_id": "safety",
        "label": "Safety",
        "subcategories": [
            ("animal_injuries", "Animal bites & injuries to visitors"),
            ("water_hazards", "Water hazards: urchins, sharp coral, currents"),
            ("boat_safety", "Boat safety incidents & unsafe vessels"),
            ("traffic_safety", "Road & traffic safety"),
            ("crime_and_theft", "Crime, theft & personal safety fears"),
            ("unmarked_hazards", "General safety hazards & lack of warnings"),
        ],
    },
    {
        "group_id": "food_and_drink",
        "label": "Food & drink",
        "subcategories": [
            ("food_quality", "Poor quality food & drink"),
            ("foodborne_illness", "Food hygiene & illness"),
        ],
    },
    {
        "group_id": "culture_and_atmosphere",
        "label": "Culture & atmosphere",
        "subcategories": [
            ("noise", "Excessive noise"),
            ("poor_atmosphere", "Stressful or unpleasant atmosphere"),
            ("sacred_site_disrespect", "Disrespect for sacred & cultural sites"),
            ("representation_disputes", "Exhibit content & representation disputes"),
        ],
    },
]

# Residual bucket for blocks that fit none of the 90 subcategories.
RESIDUALS: list[dict] = [
    {"group_id": "residual", "label": "Residual",
     "subcategories": [("other", "Does not fit any specific subcategory")]},
]

# --- Flattened lookup tables -------------------------------------------------

# subcategory key -> (group_id, label)
_SUBCAT: dict[str, tuple[str, str]] = {}
for g in FINE_TAXONOMY:
    for key, label in g["subcategories"]:
        _SUBCAT[key] = (g["group_id"], label)

# subcategory key -> group_id
KEY_TO_GROUP: dict[str, str] = {key: gid for key, (gid, _label) in _SUBCAT.items()}

# group_id -> label
GROUP_LABELS: dict[str, str] = {g["group_id"]: g["label"] for g in FINE_TAXONOMY}


def subcategory_label(key: str) -> str:
    """Human label for a subcategory key (falls back to a placeholder)."""
    return _SUBCAT.get(key, ("", f"Unknown: {key}"))[1]


def group_label(group_id: str) -> str:
    """Human label for a group id (falls back to the id itself)."""
    return GROUP_LABELS.get(group_id, group_id)


def all_groups() -> list[dict]:
    """The 20 groups plus the residual group, in display order."""
    return FINE_TAXONOMY + RESIDUALS


def all_subcategory_keys() -> set[str]:
    """Every valid subcategory key the LLM may echo, including the residual."""
    return set(_SUBCAT)
