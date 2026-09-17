#!/usr/bin/env python3
"""
split.py - split review clauses using regex.

No command-line arguments. Edit split_config.py (paths + column names), then:
    python split.py

Output (JSON Lines, one review per line):
  {"review_id": ..., "place_name": ..., "content": "...",
   "clauses": [{"clause_id": "<review_id>_c1", "sentence_no": 1, "text": "..."}, ...]}

Every clause is an exact substring of source_review, so it can be highlighted
in the original text for validation.
"""
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

import split_config as config

_HERE = Path(__file__).resolve().parent

# =============================================================================
# 1. LOADING THE RAW CSV (column names supplied on the command line)
# =============================================================================


def clean_text(text):
    text = text.replace("''", "'")                   # SQL-style escaping: wasn''t -> wasn't
    text = re.sub(r"(?:[ \t]*,){3,}[ \t]*", "", text)  # junk comma runs: "crowded.,,,,,,,"
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t\u00a0]+", " ", text)        # collapse spaces, keep line breaks
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def detect_lang(text):
    """Pick a language key from the first few words, or None to use English rules."""
    words = re.findall(r"[A-Za-z\u00c0-\u00ff]+", (text or "").lower())[:30]
    for lang, markers in (
        ("fr", {"mais", "bien", "très", "tres", "le", "la", "les", "c'est", "était"}),
        ("de", {"aber", "und", "der", "die", "das", "sehr", "nicht", "war", "für"}),
        ("es", {"pero", "pero", "que", "el", "la", "los", "las", "muy", "fue"}),
        ("it", {"ma", "che", "il", "la", "i", "le", "molto", "era"}),
        ("pt", {"mas", "que", "o", "a", "os", "as", "muito", "foi"}),
        ("nl", {"maar", "en", "het", "de", "een", "zeer", "was", "niet"}),
    ):
        if any(w in markers for w in words):
            return lang
    return None


# config.COLUMNS key -> normalized key used downstream (and in the output record).
OUTPUT_KEYS = {
    "text": "text",
    "review_id": "review_id",
    "place_id": "attraction_id",
    "place_name": "place_name",
    #"rating": "rating",
    #"lang": "lang",
    #"date": "date",
}


def load_reviews(path, stats, columns):
    """Yield one normalized row dict per data row.

    `columns` maps OUTPUT_KEYS names to the CSV header name, or None to omit.
    """
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        available = reader.fieldnames or []
        missing = [v for v in columns.values() if v is not None and v not in available]
        if missing:
            sys.exit(f"error: column(s) not found in {path}: {', '.join(missing)}\n"
                     f"available columns: {', '.join(available)}")
        # (csv_header, output_key) for every enabled field.
        pairs = [(columns[k], OUTPUT_KEYS[k]) for k in OUTPUT_KEYS if k in columns and columns[k]]
        for raw in reader:
            stats["rows_read"] += 1
            row = {ok: (raw.get(col) or "").strip() for col, ok in pairs}
            row["text"] = clean_text(row["text"])
            if not row["text"]:
                stats["skipped_no_text"] += 1
                continue
            # Auto-detect language only when a lang column was not supplied.
            if columns.get("lang") is None:
                row["lang"] = detect_lang(row["text"]) or "en"
            else:
                row["lang"] = (row["lang"] or "").lower() or "en"
            yield row


# =============================================================================
# 2. SENTENCE SPLITTING
# =============================================================================

# Protect common abbreviations so "Mr. Ali" or "e.g. spices" don't end a sentence.
ABBREVIATIONS = re.compile(r"\b(Mr|Mrs|Ms|Dr|St|Mt|Jr|Sr|vs|approx|e\.g|i\.e|a\.m|p\.m)\.", re.IGNORECASE)
PLACEHOLDER = "\u2024"  # one-dot leader, same length as "." so offsets stay intact

SENTENCE_BOUNDARY = re.compile(
    r"(?:(?<=[.!?\u2026])|(?<=[.!?\u2026][\"'\u201d\u2019)\]])(?<!\([!?]\)))\s+"  # end punct + space, not "(!)"
    r"|\n+"                                                          # line breaks
    r"|(?<=[a-z\u00e0-\u00ff]{2}[.!?])(?=[A-Z\u00c0-\u00dd])"        # missing space: "tour.The"
)

# =============================================================================
# 3. CLAUSE SPLITTING (per language)
# =============================================================================
# Tier A: conjunctions that open a new clause even without a comma.
# Tier B: words that only mark a clause boundary after a comma or semicolon,
#         because mid-clause they are adverbs ("the boat was unfortunately late").
# Lookaheads stop "not only X but also Y" style pairs from splitting.
CONNECTORS = {
    "en": {"A": [r"but(?!\s+also)", r"although", r"even though", r"whereas", r"except"],
           "B": [r"however", r"though", r"unfortunately", r"sadly", r"apart from",
                 r"other than", r"yet", r"nevertheless", r"nonetheless", r"on the other hand"]},
    "fr": {"A": [r"mais(?!\s+aussi)", r"bien que", r"sauf"],
           "B": [r"cependant", r"toutefois", r"pourtant", r"malheureusement",
                 r"par contre", r"en revanche"]},
    "de": {"A": [r"obwohl", r"außer"],
           "B": [r"aber", r"jedoch", r"leider", r"allerdings", r"trotzdem", r"sondern"]},
    "es": {"A": [r"pero", r"aunque", r"excepto", r"salvo"],
           "B": [r"sin embargo", r"lamentablemente", r"desafortunadamente", r"no obstante"]},
    "it": {"A": [r"ma(?!\s+anche)", r"però", r"anche se", r"tranne", r"eccetto"],
           "B": [r"tuttavia", r"purtroppo"]},
    "pt": {"A": [r"mas(?!\s+também)", r"porém", r"embora", r"exceto"],
           "B": [r"contudo", r"entretanto", r"infelizmente", r"no entanto"]},
    "nl": {"A": [r"hoewel", r"behalve"],
           "B": [r"maar(?!\s+ook)", r"echter", r"helaas"]},
}


def build_clause_regex(rules):
    tier_a = "|".join(rules["A"])
    tier_b = "|".join(rules["B"])
    return re.compile(
        rf"(?:\s*[,;:]\s*|\s+)(?=(?:{tier_a})\b)"   # before tier-A conjunction ("x, but" / "x,but" / "x but")
        rf"|\s*[,;]\s*(?=(?:{tier_b})\b)"    # split before tier-B word only after , or ;
        r"|\s*;\s*"                           # semicolons
        r"\s+[\u2013\u2014-]\s+",            # spaced dashes
        re.IGNORECASE,
    )


CLAUSE_REGEX = {lang: build_clause_regex(rules) for lang, rules in CONNECTORS.items()}


def inside_parentheses(text, pos):
    return text.count("(", 0, pos) > text.count(")", 0, pos)


def pieces(text, separator, skip=None):
    """(start, end) spans of the text between separator matches."""
    spans, pos = [], 0
    for m in separator.finditer(text):
        if skip and skip(m.start()):
            continue
        if text[pos:m.start()].strip():
            spans.append((pos, m.start()))
        pos = m.end()
    if text[pos:].strip():
        spans.append((pos, len(text)))
    return spans


def merge_short(spans, text, min_words):
    """Glue fragments shorter than min_words onto a neighbouring clause."""
    merged, carry = [], None
    for start, end in spans:
        if carry is not None:
            start, carry = carry, None
        if len(text[start:end].split()) >= min_words:
            merged.append((start, end))
        elif merged:                      # short fragment -> attach to previous clause
            merged[-1] = (merged[-1][0], end)
        else:                             # short first fragment -> attach to next clause
            carry = start
    if carry is not None:                 # nothing to attach to: keep it on its own
        merged.append((carry, spans[-1][1]))
    return merged


def split_review(text, lang, min_words):
    """Return a list of (sentence_no, clause_text)."""
    clause_regex = CLAUSE_REGEX.get(lang.split("-")[0], CLAUSE_REGEX["en"])
    protected = ABBREVIATIONS.sub(lambda m: m.group(1) + PLACEHOLDER, text)

    results, sentence_no = [], 0
    for s_start, s_end in pieces(protected, SENTENCE_BOUNDARY):
        sentence = protected[s_start:s_end]
        spans = pieces(sentence, clause_regex, skip=lambda p: inside_parentheses(sentence, p))
        clauses = []
        for c_start, c_end in merge_short(spans, sentence, min_words):
            clause = sentence[c_start:c_end].strip(" ,;:\u2013\u2014-\n").replace(PLACEHOLDER, ".")
            if re.search(r"\w", clause):  # drop emoji-only or punctuation-only bits
                clauses.append(clause)
        if clauses:
            sentence_no += 1
            results.extend((sentence_no, c) for c in clauses)
    return results


# =============================================================================
# 4. MAIN
# =============================================================================

def resolve_path(p):
    path = Path(p)
    return path if path.is_absolute() else _HERE / path


def main():
    columns = config.COLUMNS
    if not columns.get("text"):
        sys.exit("error: COLUMNS['text'] must be set in split_config.py")

    input_csv = resolve_path(config.INPUT_CSV)
    output_jsonl = resolve_path(config.OUTPUT_JSONL)

    stats = Counter()
    with open(output_jsonl, "w", encoding="utf-8") as out:
        for row in load_reviews(input_csv, stats, columns):
            clauses = split_review(row["text"], row["lang"] or "en", config.MIN_WORDS)
            record = {}
            for key in ("review_id", "attraction_id", "place_name"):
                if key in row:
                    record[key] = row[key] or None
            if "rating" in row:
                try:
                    record["rating"] = int(float(row["rating"]))
                except (ValueError, TypeError):
                    record["rating"] = None
            record["content"] = row["text"]
            record["clauses"] = [
                {"clause_id": f"{row.get('review_id', '')}_c{i}", "sentence_no": n, "text": c}
                for i, (n, c) in enumerate(clauses, 1)
            ]
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
            stats["reviews_written"] += 1
            stats["clauses"] += len(clauses)
            stats["sentences"] += clauses[-1][0] if clauses else 0
            per_sentence = Counter(n for n, _ in clauses)
            stats["reviews_with_split_sentence"] += any(v > 1 for v in per_sentence.values())

    print(f"Rows read:              {stats['rows_read']}")
    print(f"Skipped (no text):      {stats['skipped_no_text']}")
    print(f"Reviews written:        {stats['reviews_written']}")
    print(f"Sentences:              {stats['sentences']}")
    print(f"Clauses:                {stats['clauses']}")
    print(f"Reviews where a sentence was split into 2+ clauses: "
          f"{stats['reviews_with_split_sentence']}")
    print(f"Output: {output_jsonl}")


if __name__ == "__main__":
    main()
