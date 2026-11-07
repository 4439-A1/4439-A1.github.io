let sentences = [], dict = {}, current = null, score = 0, total = 0, answered = false;
let blank = "", alternatives = [], lastTyped = "";
const ACCEPTED_KEY = "linguaLabAccepted";
const $ = id => document.getElementById(id);

// Answers this browser's learner marked as right. Only a convenience, so it can fail quietly.
function loadAccepted() {
  try { return new Set(JSON.parse(localStorage.getItem(ACCEPTED_KEY)) || []); }
  catch { return new Set(); }
}
const accepted = loadAccepted();
const acceptedKey = typed => [current[$("toLang").value], blank.toLowerCase(), typed].join("|");

async function init() {
  [sentences, dict] = await Promise.all([
    loadJSON("data/sentences.json"),
    loadJSON("data/dictionary.json"),
  ]);
  $("fromLang").onchange = $("toLang").onchange = languagesChanged;
  $("swap").onclick = () => {
    [$("fromLang").value, $("toLang").value] = [$("toLang").value, $("fromLang").value];
    languagesChanged();
  };
  $("check").onclick = check;
  $("reveal").onclick = reveal;
  $("next").onclick = nextQuestion;
  $("markRight").onclick = markRight;
  document.addEventListener("keydown", e => {
    if (e.key !== "Enter" || e.target.id === "markRight" || e.target.closest?.("#cheatsheet")) return;
    answered ? nextQuestion() : check();
  });
  languagesChanged();
}

function languagesChanged() {
  followQuizLanguages($("fromLang").value, $("toLang").value);
  nextQuestion();
}

function nextQuestion() {
  const from = $("fromLang").value, to = $("toLang").value;
  if (from === to) { $("feedback").textContent = "Pick two different languages."; return; }
  const pool = sentences.filter(s => s[from] && s[to] && s.blanks?.[to]?.length);
  if (!pool.length) { $("feedback").textContent = "No questions found. Try reloading the page."; return; }
  current = pool[Math.floor(Math.random() * pool.length)];
  answered = false;

  $("sourceLabel").textContent = LANG_NAMES[from];
  $("targetLabel").textContent = LANG_NAMES[to];
  renderWords($("source"), current[from], from, dict);
  const blanks = current.blanks[to];
  blank = blanks[Math.floor(Math.random() * blanks.length)];
  alternatives = current.also?.[to]?.[blank.toLowerCase()] || [];
  renderWords($("target"), current[to], to, dict, blank);
  $("feedback").textContent = ""; $("feedback").className = "";
  $("definition").textContent = "";
  $("markRight").hidden = true;
  $("answer")?.focus();
}

function showDefinition() {
  const lang = $("toLang").value;
  const entry = lang !== "en" ? lookup(dict, lang, blank) : null;
  $("definition").textContent = entry ? definitionText(entry, lang) : "";
}

function check() {
  const input = $("answer");
  if (!input || answered) return;
  total++; answered = true;
  lastTyped = normalize(input.value);
  const answers = [input.dataset.answer, ...alternatives];
  const others = answers.filter(a => normalize(a) !== lastTyped);
  if (others.length < answers.length || accepted.has(acceptedKey(lastTyped))) {
    score++;
    $("feedback").textContent = "✓ Correct!" + (others.length ? ` Also correct: ${others.join(", ")}` : "");
    $("feedback").className = "ok";
  } else {
    const also = alternatives.length ? ` (also correct: ${alternatives.join(", ")})` : "";
    $("feedback").textContent = `✗ The answer was "${input.dataset.answer}"${also}`;
    $("feedback").className = "bad";
    $("markRight").hidden = !lastTyped;
  }
  showDefinition();
  $("score").textContent = score; $("total").textContent = total;
}

function markRight() {
  accepted.add(acceptedKey(lastTyped));
  try { localStorage.setItem(ACCEPTED_KEY, JSON.stringify([...accepted])); } catch {}
  score++;
  $("score").textContent = score;
  $("feedback").textContent = "✓ Counted as correct. This browser will accept it here from now on.";
  $("feedback").className = "ok";
  $("markRight").hidden = true;
}

function reveal() {
  const input = $("answer");
  if (input) input.value = input.dataset.answer;
  $("markRight").hidden = true;
  showDefinition();
  if (!answered) {
    total++; answered = true; $("total").textContent = total;
    if (alternatives.length) $("feedback").textContent = `Also correct: ${alternatives.join(", ")}`;
  }
}

init().catch(err => { $("feedback").textContent = err.message; });
