"""RAG cluster-based configuration."""

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))
import paths  # noqa: E402

OUTPUT_DIR = BASE_DIR / "output"
ENV_PATH = BASE_DIR / ".env"

# FAISS index over individual negative clause embeddings (384-dim, IndexFlatIP).
FAISS_INDEX = paths.FAISS_INDEX

# JSONL with clause metadata, aligned row-by-row with the FAISS index.
CLAUSE_META = paths.EMBEDDED_NEG

# Local MiniLM multilingual embedding model (384-dim), shared with the
# embedding pipeline. Falls back to the HF name if the local dir is absent.
DEFAULT_MODEL = paths.embedding_model()
MAX_REVIEWS = 15

# Canonical issue taxonomy (LLM classifies clauses into these).
# The 20 topical categories are snake_case keys; display_title() maps each
# key to its human-readable label (the form shown to the LLM in prompts and
# in any UI/report). "other" is the fallback for anything that fits none.
TAXONOMY = [
    "overpriced_poor_value",
    "animal_captivity_welfare",
    "tides_weather_water",
    "hidden_charges_payments_tipping",
    "safety_health_hazards",
    "overcrowding",
    "staff_behaviour_customer_service",
    "maintenance_disrepair_heritage_decay",
    "cleanliness_litter_pollution",
    "access_location_infrastructure",
    "aggressive_vendors_touts_harassment",
    "tour_organisation_duration_logistics",
    "scams_fraud_misleading_claims",
    "tourist_wildlife_interaction",
    "limited_content_underwhelming",
    "closures_restricted_access",
    "guide_quality_knowledge",
    "coral_ecosystem_damage_overcommercialisation",
    "noise_atmosphere",
    "cultural_sensitivity_authenticity",
    "other",
]

TAXONOMY_DISPLAY = {
    "overpriced_poor_value": "Overpriced / Poor Value for Money",
    "animal_captivity_welfare": "Animal Captivity & Welfare",
    "tides_weather_water": "Tides, Weather & Water Conditions",
    "hidden_charges_payments_tipping": "Hidden Charges, Payments & Tipping",
    "safety_health_hazards": "Safety & Health Hazards",
    "overcrowding": "Overcrowding",
    "staff_behaviour_customer_service": "Staff Behaviour & Customer Service",
    "maintenance_disrepair_heritage_decay": "Maintenance, Disrepair & Heritage Decay",
    "cleanliness_litter_pollution": "Cleanliness, Litter & Pollution",
    "access_location_infrastructure": "Access, Location & Infrastructure",
    "aggressive_vendors_touts_harassment": "Aggressive Vendors, Touts & Harassment",
    "tour_organisation_duration_logistics": "Tour Organisation, Duration & Logistics",
    "scams_fraud_misleading_claims": "Scams, Fraud & Misleading Claims",
    "tourist_wildlife_interaction": "Tourist–Wildlife Interaction",
    "limited_content_underwhelming": "Limited Content / Underwhelming Experience",
    "closures_restricted_access": "Closures & Restricted Access",
    "guide_quality_knowledge": "Guide Quality & Knowledge",
    "coral_ecosystem_damage_overcommercialisation": "Coral, Ecosystem Damage & Over-commercialisation",
    "noise_atmosphere": "Noise & Atmosphere",
    "cultural_sensitivity_authenticity": "Cultural Sensitivity & Authenticity",
    "other": "Other",
}


def display_title(key: str) -> str:
    """Human-readable label for a taxonomy key (falls back to the key itself)."""
    return TAXONOMY_DISPLAY.get(key, key)


def _load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


_load_env(ENV_PATH)

LLM_URL = os.getenv("LLM_URL", "")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "")

MAX_RETRIES = 3
LLM_TIMEOUT = 120
