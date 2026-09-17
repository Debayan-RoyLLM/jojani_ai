"""
Settings for join_csvs.py. Edit the values below, then run:  python join_csvs.py
"""

# --- Paths (relative to project root, or absolute) ---------------------------

LEFT_CSV  = "data/apify_reviews.csv"
RIGHT_CSV = "data/apify_places.csv"
OUTPUT_CSV = "output/apify_reviews_joined.csv"

# --- Join key (must exist in both CSVs) --------------------------------------

KEY = "google_place_id"

# --- Columns to keep (optional) -----------------------------------------------
#
# None  = keep only the key (left) / all non-key columns (right)
# list  = exactly these columns (key is always included implicitly)

LEFT_COLS  = ["review_id", "content", "translated_content"]   # from LEFT_CSV
RIGHT_COLS = ["place_name"]                    # from RIGHT_CSV
