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
    "abbreviation", "alt-of", "archaic", "dated", "dialectal", "Latinism", "literary",
    "misspelling", "noun-from-verb", "obsolete", "poetic", "proscribed", "Quebec", "rare", "regional",
}
LETTER_NAME = re.compile(r"\bletter\b.*\b(latin|alphabet)|\b(latin|alphabet).*\bletter\b", re.I)

def is_usable(pos, sense):
    tags = sense.get("tags") or []
    if not sense.get("glosses") or pos == "character" or "letter" in tags or "acronym" in tags:
        return False
    return not LETTER_NAME.search(" ".join(sense["glosses"]))

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
    if pos == "name" or UNCOMMON_TAGS & set(sense.get("tags") or []):
        return True
    # Usage notes rather than meanings, e.g. "Denotes absolute time."
    if last_sentence(sense["glosses"][-1]).startswith(("Only used", "Used", "Denotes")):
        return True
    # An inflection of a word our sentences never use is probably the wrong reading
    return bool(wanted and sense.get("form_of") and not set(base_words(sense)) & wanted)

def shorten(gloss):
    # Drop parenthetical notes from long glosses, then cut at a word boundary
    if len(gloss) > 40:
        gloss = re.sub(r"\s*\([^)]*\)", "", gloss).strip() or gloss
    if len(gloss) > MAX_GLOSS:
        gloss = gloss[:MAX_GLOSS - 1].rsplit(" ", 1)[0].rstrip(",;:") + "…"
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

def choose_gloss(word, all_entries, wanted=None):
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

def report_coverage(vocab, glosses):
    for lang, wanted in vocab.items():
        hits = [w for w in wanted if w in glosses[lang]]
        # Tokens like l'acqua are looked up by their pieces, so they aren't expected to match
        plain = [w for w in wanted if "'" not in w]
        plain_misses = [w for w in plain if w not in glosses[lang]]
        print(f"{lang}: {len(hits)} of {len(wanted)} keys have a gloss; "
              f"{len(plain) - len(plain_misses)} of {len(plain)} plain words")
        for w in random.sample(hits, 20):
            print(f"  {w}: {glosses[lang][w]['en']}")
        print("  misses:", random.sample(plain_misses, 20))


if __name__ == "__main__":
    triples = get_triples()
    print(f"{len(triples)} triples")

    vocab = build_vocab(triples)
    print({k: len(v) for k, v in vocab.items()})

    glosses = build_english_glosses(vocab)
    report_coverage(vocab, glosses)
