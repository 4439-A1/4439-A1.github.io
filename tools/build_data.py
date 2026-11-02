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


if __name__ == "__main__":
    triples = get_triples()
    print(f"{len(triples)} triples")
    for t in random.sample(triples, 5):
        print(t)

    vocab = build_vocab(triples)
    print({k: len(v) for k, v in vocab.items()})
    print(sorted(vocab["it"])[:20], sorted(vocab["fr"])[:20])
