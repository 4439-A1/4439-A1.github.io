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

if __name__ == "__main__":
    files = fetch_sentence_files()
    data = {code: load_sentences(path) for code, path in files.items()}
    for code, d in data.items():
        print(code, len(d), next(iter(d.values())))
    download("https://downloads.tatoeba.org/exports/links.tar.bz2", CACHE_DIR / "links.tar.bz2")