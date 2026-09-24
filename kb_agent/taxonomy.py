"""Fine-grained issue taxonomy (11 groups, 74 subcategories).

Groups:
1. Safety & Security
2. Cleanliness & Sanitation
3. Environment & Conservation
4. Wildlife & Animal Welfare
5. Overcrowding & Visitor Management
6. Pricing & Commercial Practices
7. Service Quality & Professionalism
8. Infrastructure & Accessibility
9. Attraction & Experience Quality
10. Beach & Water Conditions
11. Visitor Information & Booking

The subcategory key is the canonical snake_case identifier.
"""

from __future__ import annotations

FINE_TAXONOMY: list[dict] = [
    {
        "group_id": "safety_and_security",
        "label": "Safety & Security",
        "subcategories": [
            ("unsafe_activity_or_operation", "Unsafe activity or operation"),
            ("water_boating_safety", "Water/boating safety"),
            ("theft", "Theft"),
            ("scams_fraud", "Scams/fraud"),
            ("harassment", "Harassment"),
            ("inadequate_safety_measures", "Inadequate safety measures"),
            ("emergency_response", "Emergency response"),
            ("personal_security", "Personal security"),
        ],
    },
    {
        "group_id": "cleanliness_and_sanitation",
        "label": "Cleanliness & Sanitation",
        "subcategories": [
            ("litter_garbage", "Litter/garbage"),
            ("beach_cleanliness", "Beach cleanliness"),
            ("marine_litter", "Marine litter"),
            ("dirty_premises", "Dirty premises"),
            ("toilet_cleanliness", "Toilet cleanliness"),
            ("poor_sanitation", "Poor sanitation"),
            ("waste_collection_disposal", "Waste collection/disposal"),
        ],
    },
    {
        "group_id": "environment_and_conservation",
        "label": "Environment & Conservation",
        "subcategories": [
            ("coral_reef_damage", "Coral/reef damage"),
            ("habitat_degradation", "Habitat degradation"),
            ("pollution", "Pollution"),
            ("environmental_damage", "Environmental damage"),
            ("conservation_concerns", "Conservation concerns"),
            ("unsustainable_tourism_practices", "Unsustainable tourism practices"),
        ],
    },
    {
        "group_id": "wildlife_and_animal_welfare",
        "label": "Wildlife & Animal Welfare",
        "subcategories": [
            ("animal_welfare", "Animal welfare"),
            ("wildlife_harassment", "Wildlife harassment"),
            ("inappropriate_animal_interaction", "Inappropriate animal interaction"),
            ("poor_animal_conditions", "Poor animal conditions"),
            ("disturbance_of_marine_life", "Disturbance of marine life"),
            ("wildlife_management_concerns", "Wildlife management concerns"),
        ],
    },
    {
        "group_id": "overcrowding_and_visitor_management",
        "label": "Overcrowding & Visitor Management",
        "subcategories": [
            ("attraction_overcrowding", "Attraction overcrowding"),
            ("beach_overcrowding", "Beach overcrowding"),
            ("excessive_boats_vehicles", "Excessive boats/vehicles"),
            ("congestion", "Congestion"),
            ("uncontrolled_visitor_numbers", "Uncontrolled visitor numbers"),
            ("queue_crowd_management", "Queue/crowd management"),
        ],
    },
    {
        "group_id": "pricing_and_commercial_practices",
        "label": "Pricing & Commercial Practices",
        "subcategories": [
            ("overpricing", "Overpricing"),
            ("poor_value_for_money", "Poor value for money"),
            ("tourist_specific_pricing", "Tourist-specific pricing"),
            ("hidden_unclear_charges", "Hidden/unclear charges"),
            ("payment_disputes", "Payment disputes"),
            ("aggressive_selling", "Aggressive selling"),
            ("misleading_commercial_claims", "Misleading commercial claims"),
        ],
    },
    {
        "group_id": "service_quality_and_professionalism",
        "label": "Service Quality & Professionalism",
        "subcategories": [
            ("rude_unprofessional_behaviour", "Rude/unprofessional behaviour"),
            ("poor_guide_quality", "Poor guide quality"),
            ("poor_customer_service", "Poor customer service"),
            ("poor_communication", "Poor communication"),
            ("unreliable_service", "Unreliable service"),
            ("delays", "Delays"),
            ("poor_tour_service_execution", "Poor tour/service execution"),
        ],
    },
    {
        "group_id": "infrastructure_and_accessibility",
        "label": "Infrastructure & Accessibility",
        "subcategories": [
            ("poor_roads_access", "Poor roads/access"),
            ("transport_availability", "Transport availability"),
            ("parking", "Parking"),
            ("toilets_changing_facilities", "Toilets/changing facilities"),
            ("signage", "Signage"),
            ("physical_accessibility", "Physical accessibility"),
            ("poorly_maintained_infrastructure", "Poorly maintained infrastructure"),
            ("lack_of_basic_facilities", "Lack of basic facilities"),
        ],
    },
    {
        "group_id": "attraction_and_experience_quality",
        "label": "Attraction & Experience Quality",
        "subcategories": [
            ("experience_below_expectations", "Experience below expectations"),
            ("attraction_poorly_maintained", "Attraction poorly maintained"),
            ("limited_activities", "Limited activities"),
            ("poor_organisation", "Poor organisation"),
            ("insufficient_interpretation_information", "Insufficient interpretation/information"),
            ("closure_unavailability", "Closure/unavailability"),
            ("experience_not_matching_description", "Experience not matching description"),
        ],
    },
    {
        "group_id": "beach_and_water_conditions",
        "label": "Beach & Water Conditions",
        "subcategories": [
            ("water_quality", "Water quality"),
            ("seaweed", "Seaweed"),
            ("beach_condition", "Beach condition"),
            ("swimming_conditions", "Swimming conditions"),
            ("snorkelling_diving_conditions", "Snorkelling/diving conditions"),
            ("seasonal_natural_conditions", "Seasonal/natural conditions"),
        ],
    },
    {
        "group_id": "visitor_information_and_booking",
        "label": "Visitor Information & Booking",
        "subcategories": [
            ("incorrect_online_information", "Incorrect online information"),
            ("incorrect_opening_hours", "Incorrect opening hours"),
            ("location_map_issues", "Location/map issues"),
            ("booking_problems", "Booking problems"),
            ("reservation_issues", "Reservation issues"),
            ("insufficient_visitor_information", "Insufficient visitor information"),
        ],
    },
]

RESIDUALS: list[dict] = [
    {
        "group_id": "residual",
        "label": "Other",
        "subcategories": [
            ("other", "Does not fit any specific subcategory"),
        ],
    },
]

_SUBCAT: dict[str, tuple[str, str]] = {}
for group in FINE_TAXONOMY:
    for key, label in group["subcategories"]:
        _SUBCAT[key] = (group["group_id"], label)

KEY_TO_GROUP: dict[str, str] = {
    key: group_id for key, (group_id, _label) in _SUBCAT.items()
}

GROUP_LABELS: dict[str, str] = {
    group["group_id"]: group["label"] for group in FINE_TAXONOMY
}

def subcategory_label(key: str) -> str:
    """Return the human-readable label for a subcategory key."""
    return _SUBCAT.get(key, ("", f"Unknown: {key}"))[1]

def group_label(group_id: str) -> str:
    """Return the human-readable label for a group id."""
    return GROUP_LABELS.get(group_id, group_id)

def all_groups() -> list[dict]:
    """Return all 11 primary groups plus the residual group."""
    return FINE_TAXONOMY + RESIDUALS

def all_subcategory_keys() -> set[str]:
    """Return every valid subcategory key, including the residual."""
    return set(_SUBCAT) | {"other"}
