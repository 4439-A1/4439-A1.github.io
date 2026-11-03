import gzip
import json
import random
import re
from collections import defaultdict
from pathlib import Path
from urllib import request

CACHE_DIR = Path(__file__).parent / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

def download(url, path):
    path = Path(path)
    
    if path.exists() and path.stat().st_size > 0:
        print(f"Using cached {path.name}")
        return path
    
    tmp = path.with_suffix(path.suffix + ".part")
    print(f"Downloading {url}")
    req = request.Request(url, headers={"User-Agent": "lingua-lab-build/0.1"})
    with request.urlopen(req) as resp, open(tmp, "wb") as out:
        while chunk := resp.read(1024 * 1024):
            out.write(chunk)
            
    tmp.rename(path)
    return path


BASE = "https://downloads.tatoeba.org/exports"
LANGS = {"en": "eng", "it": "ita", "fr": "fra"}

def fetch_sentence_files():
    paths = {}
    for code, tatoeba in LANGS.items():
        url = f"{BASE}/per_language/{tatoeba}/{tatoeba}_sentences.tsv.bz2"
        paths[code] = download(url, CACHE_DIR / f"{tatoeba}_sentences.tsv.bz2")
    return paths

import bz2
import csv

def load_sentences(path, max_words=10):
    sentences = {}
    with bz2.open(path, "rt", encoding="utf-8", newline="") as f:
        for sid, _lang, text in csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE):
            if len(text.split()) <= max_words:
                sentences[int(sid)] = text
    return sentences

import tarfile

def iter_links(path):
    with tarfile.open(path, "r:bz2") as tar:
        member = tar.getmember("links.csv")
        f = tar.extractfile(member)
        for line in f:
            a, b = line.decode().split("\t")
            yield int(a), int(b)

def build_triples():
    files = fetch_sentence_files()
    data = {code: load_sentences(path) for code, path in files.items()}
    en, it, fr = data["en"], data["it"], data["fr"]
    links_path = download(f"{BASE}/links.tar.bz2", CACHE_DIR / "links.tar.bz2")

    en_to_it = defaultdict(list)
    en_to_fr = defaultdict(list)
    for a, b in iter_links(links_path):
        if a in en:
            if b in it:
                en_to_it[a].append(b)
            elif b in fr:
                en_to_fr[a].append(b)

    triples = []
    for en_id in en_to_it.keys() & en_to_fr.keys():   # English ids that have both
        it_id = min(en_to_it[en_id], key=lambda i: len(it[i]))
        fr_id = min(en_to_fr[en_id], key=lambda i: len(fr[i]))
        triples.append({"en": en[en_id], "it": it[it_id], "fr": fr[fr_id]})
    return triples


TRIPLES_CACHE = CACHE_DIR / "triples.json"

def get_triples():
    if TRIPLES_CACHE.exists() and TRIPLES_CACHE.stat().st_size > 0:
        print(f"Using cached {TRIPLES_CACHE.name}")
        return json.loads(TRIPLES_CACHE.read_text(encoding="utf-8"))
    triples = build_triples()
    tmp = TRIPLES_CACHE.with_suffix(".json.part")
    tmp.write_text(json.dumps(triples, ensure_ascii=False), encoding="utf-8")
    tmp.rename(TRIPLES_CACHE)
    return triples


TOKEN = re.compile(r"[^\W\d_'’]+(?:['’][^\W\d_'’]+)*['’]?")

def vocab_keys(w):
    # Mirror lookup() in js/common.js: whole token, last part, first part + "'"
    keys = {w}
    if "'" in w:
        after = w.rpartition("'")[2]
        if after:
            keys.add(after)
        keys.add(w.split("'")[0] + "'")
    return keys

def build_vocab(triples):
    vocab = {"it": set(), "fr": set()}
    for t in triples:
        for lang in ("it", "fr"):
            for tok in TOKEN.findall(t[lang]):
                w = tok.lower().replace("’", "'")
                vocab[lang] |= vocab_keys(w)
    return vocab


KAIKKI = {
    "it": "https://kaikki.org/dictionary/Italian/kaikki.org-dictionary-Italian.jsonl",
    "fr": "https://kaikki.org/dictionary/French/kaikki.org-dictionary-French.jsonl",
}

def base_words(sense):
    words = []
    for base in sense["form_of"]:
        # Kaikki stores this one as {"word": "avere and", "extra": "(obsolete) havere"}
        word = base["word"].lower().replace("’", "'")
        words.append(word.removesuffix(" and"))
    return words

def load_entries(path, wanted):
    # Scan the whole file a line at a time, keeping only the words we need
    entries = defaultdict(list)
    with open(path, encoding="utf-8") as f:
        for line in f:
            e = json.loads(line)
            w = e["word"].lower().replace("’", "'")
            if w in wanted and e.get("senses"):
                senses = [
                    {k: sense[k] for k in ("glosses", "form_of", "alt_of", "tags") if k in sense}
                    for sense in e["senses"]
                ]
                entries[w].append({"pos": e.get("pos"), "senses": senses})
    return entries

def get_entries(lang, wanted):
    cache = CACHE_DIR / f"entries_{lang}.json"
    if cache.exists() and cache.stat().st_size > 0:
        print(f"Using cached {cache.name}")
        return json.loads(cache.read_text(encoding="utf-8"))
    path = download(KAIKKI[lang], CACHE_DIR / f"kaikki_{lang}.jsonl")
    print(f"Scanning {path.name}")
    entries = load_entries(path, wanted)
    # Inflections point at base words that may not be in the vocabulary
    bases = {
        base
        for word_entries in entries.values()
        for entry in word_entries
        for sense in entry["senses"]
        if sense.get("form_of")
        for base in base_words(sense)
    } - entries.keys()
    print(f"Scanning {path.name} again for {len(bases)} base words")
    entries.update(load_entries(path, bases))
    tmp = cache.with_suffix(".json.part")
    tmp.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
    tmp.rename(cache)
    return entries


MAX_GLOSS = 80
MAX_MEANINGS = 2
# Common uses first: function words, then nouns, verbs, adjectives and the rest
POS_ORDER = {
    "article": 0, "det": 1, "prep": 2, "conj": 3, "particle": 4, "pron": 5, "contraction": 6,
    "noun": 7, "verb": 8, "adj": 9, "adv": 10,
}
UNCOMMON_TAGS = {
    "abbreviation", "alt-of", "archaic", "dated", "dialectal", "familiar", "Latinism", "literary",
    "misspelling", "noun-from-verb", "obsolete", "pejorative", "poetic", "proscribed", "Quebec",
    "rare", "regional", "slang", "vulgar",
}
LETTER_NAME = re.compile(r"\bletter\b.*\b(latin|alphabet)|\b(latin|alphabet).*\bletter\b", re.I)

# Wording from the Italian and French editions, which don't tag these senses
NOT_A_DEFINITION = re.compile(
    r"\( ?(approfondimento|citazioni)\)|definizione mancante"   # "casa ( approfondimento) f sing"
    r"|\blettera\b.*\balfabeto\b|\blettre\b.*\balphabet\b",
    re.I,
)
UNCOMMON_NATIVE = re.compile(r"(variante|abbreviazione|abréviation|symbole|simbolo)\b", re.I)

def is_usable(pos, sense):
    tags = sense.get("tags") or []
    if not sense.get("glosses") or pos == "character" or {"letter", "acronym", "no-gloss"} & set(tags):
        return False
    gloss = " ".join(sense["glosses"])
    return not (LETTER_NAME.search(gloss) or NOT_A_DEFINITION.search(gloss))

def rank_senses(entries, wanted=None):
    senses = [
        (entry["pos"], sense)
        for entry in entries
        for sense in entry["senses"]
        if is_usable(entry["pos"], sense)
    ]
    def key(item):
        pos, sense = item
        return (is_uncommon(pos, sense, wanted), POS_ORDER.get(pos, 11), bool(sense.get("form_of")))
    return sorted(senses, key=key)

def is_uncommon(pos, sense, wanted):
    if pos in ("name", "abbrev", "symbol") or UNCOMMON_TAGS & set(sense.get("tags") or []):
        return True
    if UNCOMMON_NATIVE.match(sense["glosses"][-1]):
        return True
    # Usage notes rather than meanings, e.g. "Denotes absolute time."
    if last_sentence(sense["glosses"][-1]).startswith(("Only used", "Used", "Denotes")):
        return True
    # An inflection of a word our sentences never use is probably the wrong reading
    return bool(wanted and sense.get("form_of") and not set(base_words(sense)) & wanted)

def shorten(gloss, limit=MAX_GLOSS):
    # Drop parenthetical notes from long glosses, then cut at a word boundary
    if len(gloss) > 40:
        gloss = re.sub(r"\s*\([^)]*\)", "", gloss).strip() or gloss
    if len(gloss) > limit:
        gloss = gloss[:limit - 1].rsplit(" ", 1)[0].rstrip(",;:") + "…"
    return gloss

def last_sentence(gloss):
    # "Used as a copula. to be" -> "to be"
    return re.split(r"(?<!e\.g)(?<!i\.e)\. ", gloss)[-1]

def base_meaning(base, pos, all_entries):
    # A few words saying what the base word means, e.g. "to have" for avoir.
    # Same part of speech only: a verb form should not borrow a noun's meaning.
    for sense_pos, sense in rank_senses(all_entries.get(base, [])):
        if sense_pos == pos and not sense.get("form_of") and not sense.get("alt_of"):
            gloss = re.sub(r"\([^)]*\)?|\)", "", last_sentence(sense["glosses"][-1]))
            return re.split(r"[,;]", gloss)[0].strip()
    return None

def describe(pos, sense, all_entries):
    if not sense.get("form_of"):
        return shorten(last_sentence(sense["glosses"][-1]))
    # Shorten first: the added meaning is a parenthetical shorten() would remove
    gloss = shorten(" ".join(sense["glosses"]))
    for base in base_words(sense):
        meaning = base_meaning(base, pos, all_entries)
        if not meaning:
            continue
        if gloss.lower().startswith(f"inflection of {base}:"):
            return gloss.replace(f"{base}:", f"{base} ({meaning}):", 1)
        # Glosses like "feminine of le: the" already give the meaning
        if ": " not in gloss and "; " not in gloss:
            return f"{gloss} ({meaning})"
    return gloss

def choose_gloss(word, all_entries, wanted=None, describe=describe):
    # One meaning, plus a second when the word has another distinct use
    ranked = rank_senses(all_entries[word], wanted)
    if not ranked:
        return None
    first_pos, first = ranked[0]
    meanings = [describe(first_pos, first, all_entries)]
    for pos, sense in ranked[1:]:
        if len(meanings) == MAX_MEANINGS:
            break
        if is_uncommon(pos, sense, wanted):
            continue
        if sense.get("form_of") and first.get("form_of"):
            # Same base: only worth repeating when the gloss states a meaning, as in sono
            if base_words(sense) == base_words(first) and (
                ": " not in sense["glosses"][-1] or sense["glosses"][0].startswith("inflection of")
            ):
                continue
        elif pos == first_pos:
            continue
        meaning = describe(pos, sense, all_entries)
        if meaning not in meanings:
            meanings.append(meaning)
    # Glosses can themselves contain ";", so drop repeats across the joined parts
    parts = "; ".join(meanings).split("; ")
    return "; ".join(dict.fromkeys(parts))

def build_english_glosses(vocab):
    glosses = {}
    for lang, wanted in vocab.items():
        entries = get_entries(lang, wanted)
        chosen = {w: choose_gloss(w, entries, wanted) for w in wanted if w in entries}
        glosses[lang] = {w: {"en": g} for w, g in chosen.items() if g}
    return glosses

# Everything each Wiktionary edition defines, in all languages, so filter by language.
# The compressed exports are far smaller than the single-language files (780 MB vs 3.7 GB).
NATIVE = {
    "it": "https://kaikki.org/itwiktionary/raw-wiktextract-data.jsonl.gz",
    "fr": "https://kaikki.org/frwiktionary/raw-wiktextract-data.jsonl.gz",
}
MAX_NATIVE_GLOSS = 80

def load_native_entries(path, lang, wanted):
    entries = defaultdict(list)
    marker = f'"lang_code": "{lang}"'
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            if marker not in line:   # Much cheaper than parsing every language's entries
                continue
            e = json.loads(line)
            w = e.get("word", "").lower().replace("’", "'")
            if e.get("lang_code") == lang and w in wanted and e.get("senses"):
                senses = [
                    {k: sense[k] for k in ("glosses", "form_of", "tags") if k in sense}
                    for sense in e["senses"]
                ]
                entries[w].append({"pos": e.get("pos"), "senses": senses})
    return entries

def get_native_entries(lang, wanted):
    cache = CACHE_DIR / f"native_entries_{lang}.json"
    if cache.exists() and cache.stat().st_size > 0:
        print(f"Using cached {cache.name}")
        return json.loads(cache.read_text(encoding="utf-8"))
    path = download(NATIVE[lang], CACHE_DIR / f"wiktionary_{lang}.jsonl.gz")
    print(f"Scanning {path.name}")
    entries = load_native_entries(path, lang, wanted)
    tmp = cache.with_suffix(".json.part")
    tmp.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
    tmp.rename(cache)
    return entries

def describe_native(pos, sense, all_entries):
    # Some glosses carry footnote markers like "^([1])" or end in a stray semicolon
    gloss = re.sub(r"\s*\^\(\[[^\]]*\]\)", "", sense["glosses"][-1])
    return shorten(gloss.rstrip(" .;"), MAX_NATIVE_GLOSS)

def add_native_glosses(vocab, glosses):
    # Only words with an English gloss: the tooltip in common.js always shows that line
    for lang, wanted in vocab.items():
        entries = get_native_entries(lang, wanted)
        for w, entry in glosses[lang].items():
            if w in entries:
                native = choose_gloss(w, entries, wanted, describe_native)
                if native:
                    entry["native"] = native

def report_coverage(vocab, glosses):
    for lang, wanted in vocab.items():
        hits = [w for w in wanted if w in glosses[lang]]
        # Tokens like l'acqua are looked up by their pieces, so they aren't expected to match
        plain = [w for w in wanted if "'" not in w]
        plain_misses = [w for w in plain if w not in glosses[lang]]
        print(f"{lang}: {len(hits)} of {len(wanted)} keys have a gloss; "
              f"{len(plain) - len(plain_misses)} of {len(plain)} plain words")
        native = [w for w in hits if "native" in glosses[lang][w]]
        print(f"{lang}: {len(native)} of {len(hits)} glossed words have a native definition")
        for w in random.sample(hits, 20):
            print(f"  {w}: {glosses[lang][w]}")
        print("  misses:", random.sample(plain_misses, 20))


MAX_SENTENCES = 5000
MIN_WORDS = 3
SEED = 4439   # Keeps the chosen sentences the same between runs

STOPWORDS = {
    "en": set("""
        about after again also and are been before being but can could did does doing done down
        for from going had has have her here hers him his how into its just like more most much
        not now off one our out over she should some than that the their them then there these
        they this those through too two under very was were what when where which who whom why
        will with would you your yours
    """.split()),
    "it": set("""
        alla alle allo anche ancora che chi come con cosa così dal dalla dalle dallo degli dei
        del della delle dello dove due era erano essere gli hai hanno loro lui lei mai mio mia
        miei mie molto nei nel nella nelle nello non nostro nostra per perché più poi quale
        quando quanto quella quelle quelli quello questa queste questi questo qui sei sono
        stato sua sue suo suoi sul sulla tua tue tuo tuoi tutto tutta tutti tutte una uno
    """.split()),
    "fr": set("""
        aussi autre avec avez avoir avons ces cet cette comme dans des donc elle elles est
        était étaient être eux ils leur leurs mais mes mon même moi nos notre nous ont oui
        par pas plus pour quand que quel quelle qui sans ses son sont sur tes toi ton tous
        tout toute toutes très une vos votre vous
    """.split()),
}

# Same token rule as renderWords() in js/common.js, which can only blank a whole token
PAGE_TOKEN = re.compile(r"(?:[^\W\d_]|['’])+")

def find_key(table, token):
    # Mirror lookup() in js/common.js: whole token, last part, first part + "'"
    w = token.lower().replace("’", "'")
    parts = w.split("'")
    for key in (w, parts[-1], parts[0] + "'"):
        if key in table:
            return key
    return None

def choose_blank(sentence, lang, glosses):
    # The longest ordinary word. Names are capitalized, and capitals at the start
    # of a sentence are only accepted if the dictionary knows the word.
    best = None
    for i, token in enumerate(PAGE_TOKEN.findall(sentence)):
        w = token.lower()
        if not token.isalpha() or len(w) < 3 or w in STOPWORDS[lang]:
            continue
        if lang == "en":
            if not token.islower():
                continue
        elif w not in glosses[lang] or (i > 0 and not token.islower()):
            continue
        if best is None or len(w) > len(best):
            best = token
    return best

def is_fully_defined(sentence, table):
    # Every lowercase word needs a tooltip; capitalized ones may be names
    for token in PAGE_TOKEN.findall(sentence):
        if token[0].islower() and not find_key(table, token):
            return False
    return True

def build_sentences(triples, glosses):
    seen = set()
    pool = []
    for t in sorted(triples, key=lambda t: t["en"]):
        if t["en"] in seen or len(t["en"].split()) < MIN_WORDS:
            continue
        seen.add(t["en"])
        if not all(is_fully_defined(t[lang], glosses[lang]) for lang in ("it", "fr")):
            continue
        blank = {lang: choose_blank(t[lang], lang, glosses) for lang in ("en", "it", "fr")}
        if all(blank.values()):
            pool.append({**t, "blank": blank})
    print(f"{len(pool)} usable sentences")
    chosen = random.Random(SEED).sample(pool, min(MAX_SENTENCES, len(pool)))
    return sorted(chosen, key=lambda t: t["en"])

def build_dictionary(sentences, glosses):
    # Only the entries the page can actually reach
    dictionary = {"it": {}, "fr": {}}
    for t in sentences:
        for lang, table in dictionary.items():
            for token in PAGE_TOKEN.findall(t[lang]):
                key = find_key(glosses[lang], token)
                if key:
                    table[key] = glosses[lang][key]
    return dictionary

def write_json(name, data):
    path = Path(__file__).parent.parent / "data" / name
    text = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    path.write_text(text + "\n", encoding="utf-8")
    print(f"Wrote {path.name}: {path.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    triples = get_triples()
    print(f"{len(triples)} triples")

    vocab = build_vocab(triples)
    print({k: len(v) for k, v in vocab.items()})

    glosses = build_english_glosses(vocab)
    add_native_glosses(vocab, glosses)
    report_coverage(vocab, glosses)

    sentences = build_sentences(triples, glosses)
    dictionary = build_dictionary(sentences, glosses)
    print({lang: len(table) for lang, table in dictionary.items()})
    write_json("sentences.json", sentences)
    write_json("dictionary.json", dictionary)
