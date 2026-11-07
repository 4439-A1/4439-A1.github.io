// The grammar panel beside each page's content. Needs common.js and <aside id="cheatsheet">.
const CHEATSHEET_LANG_KEY = "linguaLabCheatsheetLang";
let cheatsheetData = null, cheatsheetLang = "it";

try {
  const saved = localStorage.getItem(CHEATSHEET_LANG_KEY);
  if (saved === "it" || saved === "fr") cheatsheetLang = saved;
} catch {}

function cheatElement(tag, text) {
  const el = document.createElement(tag);
  if (text) el.textContent = text;
  return el;
}

function renderCheatTable(table) {
  const wrap = cheatElement("div");
  wrap.className = "cheat-table";
  const el = cheatElement("table");
  if (table.caption) el.appendChild(cheatElement("caption", table.caption));

  const headRow = cheatElement("tr");
  for (const h of table.headers) {
    const th = cheatElement("th", h);
    th.scope = "col";
    headRow.appendChild(th);
  }
  const head = cheatElement("thead");
  head.appendChild(headRow);
  el.appendChild(head);

  const body = cheatElement("tbody");
  for (const row of table.rows) {
    const tr = cheatElement("tr");
    row.forEach((cell, i) => {
      const td = cheatElement(i === 0 ? "th" : "td", cell);
      if (i === 0) td.scope = "row";
      tr.appendChild(td);
    });
    body.appendChild(tr);
  }
  el.appendChild(body);
  wrap.appendChild(el);
  return wrap;
}

function renderCheatSection(section, open) {
  const details = cheatElement("details");
  details.open = open;
  details.appendChild(cheatElement("summary", section.title));
  if (section.intro) details.appendChild(cheatElement("p", section.intro));
  for (const table of section.tables || []) details.appendChild(renderCheatTable(table));
  if (section.notes) {
    const list = cheatElement("ul");
    for (const note of section.notes) list.appendChild(cheatElement("li", note));
    details.appendChild(list);
  }
  return details;
}

function renderCheatsheet() {
  const panel = document.getElementById("cheatsheet");
  if (!cheatsheetData) return;
  panel.innerHTML = "";

  const header = cheatElement("div");
  header.className = "cheat-header";
  header.appendChild(cheatElement("h2", "Grammar cheatsheet"));
  const tabs = cheatElement("div");
  tabs.className = "cheat-tabs";
  for (const lang of ["it", "fr"]) {
    const tab = cheatElement("button", cheatsheetData[lang].name);
    tab.type = "button";
    tab.className = lang === cheatsheetLang ? "" : "secondary";
    tab.setAttribute("aria-pressed", lang === cheatsheetLang);
    tab.onclick = () => {
      setCheatsheetLang(lang);
      document.querySelector(`.cheat-tabs button[aria-pressed="true"]`)?.focus();
    };
    tabs.appendChild(tab);
  }
  header.appendChild(tabs);
  panel.appendChild(header);

  cheatsheetData[cheatsheetLang].sections.forEach((section, i) => {
    panel.appendChild(renderCheatSection(section, i === 0));
  });
}

function setCheatsheetLang(lang) {
  if (lang === cheatsheetLang && document.querySelector(".cheat-tabs")) return;
  cheatsheetLang = lang;
  try { localStorage.setItem(CHEATSHEET_LANG_KEY, lang); } catch {}
  renderCheatsheet();
  document.getElementById("cheatsheet").scrollTop = 0;
}

// The quiz shows the language being practised, or the other one when answering in English
function followQuizLanguages(from, to) {
  const lang = to !== "en" ? to : from;
  if (lang !== "en") setCheatsheetLang(lang);
}

loadJSON("data/cheatsheet.json")
  .then(data => { cheatsheetData = data; renderCheatsheet(); })
  .catch(err => { document.getElementById("cheatsheet").textContent = err.message; });
