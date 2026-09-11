#!/usr/bin/env python3
"""
split_clauses.py - split Booking.com attraction reviews into clauses using regex.

Output (JSON Lines, one review per line):
  {"review_id": ..., "attraction_id": ..., "rating": ..., "lang": ..., "date": ...,
   "source_review": "...",
   "clauses": [{"clause_id": "<review_id>_c1", "sentence_no": 1, "text": "..."}, ...]}

Every clause is an exact substring of source_review, so it can be highlighted
in the original text for validation.

Usage:
  python split_clauses.py Review_Booking_com.csv -o review_clauses.jsonl
  python split_clauses.py Review_Booking_com.csv -o review_clauses.jsonl --flat-csv review_clauses.csv
"""
import argparse
import csv
import io
import json
import re
from collections import Counter

# =============================================================================
# 1. LOADING THE RAW CSV (handles the rows whose quoting is broken)
# =============================================================================

# Every record starts with attraction_id, review_id, date, e.g. "PR0iMwj9mmvd,RSVcm0OCaIdq,2026-..."
RECORD_START = re.compile(r"\r?\n(?=PR[0-9A-Za-z]{6,20},RS[0-9A-Za-z]{6,20},\d{4}-\d{2}-\d{2})")

# Fallback for broken rows: the review text is always followed by
#   ,<lang>,<rating 1-5>,<count>,<t|f>,
REPAIR = re.compile(
    r"^(?P<attraction_id>PR[0-9A-Za-z]+),(?P<review_id>RS[0-9A-Za-z]+),(?P<date>[^,]*),"
    r"(?P<text>.*?)"
    r",(?P<lang>[a-z]{2,3}(?:-[a-z]{2,4})?)?,(?P<rating>[1-5])(?:\.0+)?,[^,]*,[tf],",
    re.DOTALL,
)
SEQUENCE_NO = re.compile(r",(\d+),APPLICATION,")

N_COLUMNS = 21
COLUMNS = {"attraction_id": 0, "review_id": 1, "date": 2, "text": 3, "lang": 4, "rating": 5}
VALID_RATING = re.compile(r"^[1-5](?:\.0+)?$")   # some rows store 4 as "4.00"


def repair_quotes(text):
    """Undo the quote mangling seen in broken rows."""
    text = text.strip()
    if text.startswith('"'):
        text = text[1:]
    if text.endswith('"'):
        text = text[:-1]
    text = text.replace('""', '"')
    text = re.sub(r'"\s*,\s*"', ", ", text)      # spicefarm"," een   -> spicefarm, een
    text = re.sub(r"'\"+|\"+'", "'", text)       # '"modelboerderij'"  -> 'modelboerderij'
    text = re.sub(r'"\s*,\s*', ", ", text)        # specerijen",was    -> specerijen, was
    text = re.sub(r',\s*"\s*', ", ", text)        # slaan," maar       -> slaan, maar
    return text.strip().rstrip('"')


def clean_text(text):
    text = text.replace("''", "'")                   # SQL-style escaping: wasn''t -> wasn't
    text = re.sub(r"(?:[ \t]*,){3,}[ \t]*", "", text)  # junk comma runs: "crowded.,,,,,,,"
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t\u00a0]+", " ", text)        # collapse spaces, keep line breaks
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def parse_record(record):
    """Return (row, method). method is 'clean', 'repaired' or 'unparseable'."""
    try:
        fields = next(csv.reader(io.StringIO(record)))
    except (csv.Error, StopIteration):
        fields = []
    if (len(fields) == N_COLUMNS and VALID_RATING.match(fields[5])
            and fields[16] == "APPLICATION"):
        return {k: fields[i] for k, i in COLUMNS.items()}, "clean"

    match = REPAIR.match(record)
    if match:
        row = match.groupdict()
        row["text"] = repair_quotes(row["text"])
        return row, "repaired"
    return None, "unparseable"


def load_reviews(path, stats):
    with open(path, encoding="utf-8-sig", newline="") as f:
        raw = f.read()
    _header, _, body = raw.partition("\n")
    records = [r.strip("\r\n") for r in RECORD_START.split(body) if r.strip()]

    seq_numbers = set()
    for record in records:
        seq = SEQUENCE_NO.search(record)
        if seq:
            seq_numbers.add(int(seq.group(1)))
        row, method = parse_record(record)
        stats[method] += 1
        if row:
            row["text"] = clean_text(row["text"] or "")
            row["lang"] = (row["lang"] or "").strip().lower()
            yield row

    stats["records_found"] = len(records)
    stats["max_sequence_no"] = max(seq_numbers) if seq_numbers else 0


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
    "de": {"A": [r"obwohl", r"au\u00dfer"],
           "B": [r"aber", r"jedoch", r"leider", r"allerdings", r"trotzdem", r"sondern"]},
    "es": {"A": [r"pero", r"aunque", r"excepto", r"salvo"],
           "B": [r"sin embargo", r"lamentablemente", r"desafortunadamente", r"no obstante"]},
    "it": {"A": [r"ma(?!\s+anche)", r"per\u00f2", r"anche se", r"tranne", r"eccetto"],
           "B": [r"tuttavia", r"purtroppo"]},
    "pt": {"A": [r"mas(?!\s+tamb\u00e9m)", r"por\u00e9m", r"embora", r"exceto"],
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
        r"|\s+[\u2013\u2014-]\s+",            # spaced dashes
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

def main():
    parser = argparse.ArgumentParser(description="Split reviews into clauses.")
    parser.add_argument("input_csv")
    parser.add_argument("-o", "--output", default="review_clauses.jsonl")
    parser.add_argument("--flat-csv", help="also write one row per clause to this CSV")
    parser.add_argument("--min-words", type=int, default=3,
                        help="fragments shorter than this are merged into a neighbour (default 3)")
    args = parser.parse_args()

    stats = Counter()
    flat_rows = []
    with open(args.output, "w", encoding="utf-8") as out:
        for row in load_reviews(args.input_csv, stats):
            if not row["text"]:
                stats["skipped_no_text"] += 1
                continue
            clauses = split_review(row["text"], row["lang"] or "en", args.min_words)
            record = {
                "review_id": row["review_id"],
                "attraction_id": row["attraction_id"],
                "rating": int(float(row["rating"])),
                "lang": row["lang"] or None,
                "date": row["date"],
                "source_review": row["text"],
                "clauses": [
                    {"clause_id": f"{row['review_id']}_c{i}", "sentence_no": n, "text": c}
                    for i, (n, c) in enumerate(clauses, 1)
                ],
            }
            out.write(json.dumps(record, ensure_ascii=False) + "\n")

            stats["reviews_written"] += 1
            stats["clauses"] += len(clauses)
            stats["sentences"] += clauses[-1][0] if clauses else 0
            per_sentence = Counter(n for n, _ in clauses)
            stats["reviews_with_split_sentence"] += any(v > 1 for v in per_sentence.values())
            for c in record["clauses"]:
                flat_rows.append({"clause_id": c["clause_id"], "review_id": row["review_id"],
                                  "attraction_id": row["attraction_id"], "rating": record["rating"],
                                  "lang": record["lang"], "sentence_no": c["sentence_no"],
                                  "clause_text": c["text"]})

    if args.flat_csv:
        with open(args.flat_csv, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(flat_rows[0].keys()))
            writer.writeheader()
            writer.writerows(flat_rows)

    print(f"Records found:          {stats['records_found']} "
          f"(highest sequence no. in file: {stats['max_sequence_no']})")
    print(f"  parsed normally:      {stats['clean']}")
    print(f"  repaired:             {stats['repaired']}")
    print(f"  unparseable:          {stats['unparseable']}")
    print(f"Skipped (no text):      {stats['skipped_no_text']}")
    print(f"Reviews written:        {stats['reviews_written']}")
    print(f"Sentences:              {stats['sentences']}")
    print(f"Clauses:                {stats['clauses']}")
    print(f"Reviews where a sentence was split into 2+ clauses: "
          f"{stats['reviews_with_split_sentence']}")
    print(f"Output: {args.output}" + (f" and {args.flat_csv}" if args.flat_csv else ""))


if __name__ == "__main__":
    main()
