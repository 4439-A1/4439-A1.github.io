const LANG_NAMES = { en: "English", it: "Italian", fr: "French" };

async function loadJSON(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`Could not load ${path}`);
  return res.json();
}

// Lowercase + strip accents, for lenient answer checking
function normalize(s) {
  return s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "")
          .replace(/[’]/g, "'").trim();
}

// Look up a word, handling elisions like l'eau, dell'acqua, j'ai
function lookup(dict, lang, raw) {
  const table = dict[lang] || {};
  const w = raw.toLowerCase().replace(/’/g, "'");
  if (table[w]) return { word: w, ...table[w] };
  const parts = w.split("'");
  for (const p of [parts[parts.length - 1], parts[0] + "'"]) {
    if (table[p]) return { word: p, ...table[p] };
  }
  return null;
}

// Turn a sentence into hoverable spans (only for it/fr)
function renderWords(container, sentence, lang, dict, blankWord = null) {
  container.innerHTML = "";
  const tokens = sentence.match(/[\p{L}'’]+|[^\p{L}'’]+/gu) || [];
  let blankDone = false;
  for (const tok of tokens) {
    if (blankWord && !blankDone && tok.toLowerCase() === blankWord.toLowerCase()) {
      const input = document.createElement("input");
      input.className = "blank";
      input.id = "answer";
      input.autocomplete = "off";
      input.dataset.answer = tok;
      container.appendChild(input);
      blankDone = true;
      continue;
    }
    const entry = /\p{L}/u.test(tok) && lang !== "en" ? lookup(dict, lang, tok) : null;
    if (entry) {
      const span = document.createElement("span");
      span.className = "word";
      span.textContent = tok;
      span.dataset.tip =
        `${entry.word}\n🇬🇧 ${entry.en}` + (entry.native ? `\n${lang === "it" ? "🇮🇹" : "🇫🇷"} ${entry.native}` : "");
      container.appendChild(span);
    } else {
      container.appendChild(document.createTextNode(tok));
    }
  }
}
