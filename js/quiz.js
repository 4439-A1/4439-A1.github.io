let sentences = [], dict = {}, current = null, score = 0, total = 0, answered = false;
const $ = id => document.getElementById(id);

async function init() {
  [sentences, dict] = await Promise.all([
    loadJSON("data/sentences.json"),
    loadJSON("data/dictionary.json"),
  ]);
  $("fromLang").onchange = $("toLang").onchange = nextQuestion;
  $("swap").onclick = () => {
    [$("fromLang").value, $("toLang").value] = [$("toLang").value, $("fromLang").value];
    nextQuestion();
  };
  $("check").onclick = check;
  $("reveal").onclick = reveal;
  $("next").onclick = nextQuestion;
  document.addEventListener("keydown", e => {
    if (e.key === "Enter") answered ? nextQuestion() : check();
  });
  nextQuestion();
}

function nextQuestion() {
  const from = $("fromLang").value, to = $("toLang").value;
  if (from === to) { $("feedback").textContent = "Pick two different languages."; return; }
  const pool = sentences.filter(s => s[from] && s[to] && s.blank?.[to]);
  current = pool[Math.floor(Math.random() * pool.length)];
  answered = false;

  $("sourceLabel").textContent = LANG_NAMES[from];
  $("targetLabel").textContent = LANG_NAMES[to];
  renderWords($("source"), current[from], from, dict);
  renderWords($("target"), current[to], to, dict, current.blank[to]);
  $("feedback").textContent = ""; $("feedback").className = "";
  $("answer")?.focus();
}

function check() {
  const input = $("answer");
  if (!input || answered) return;
  total++; answered = true;
  if (normalize(input.value) === normalize(input.dataset.answer)) {
    score++;
    $("feedback").textContent = "✓ Correct!";
    $("feedback").className = "ok";
  } else {
    $("feedback").textContent = `✗ The answer was "${input.dataset.answer}"`;
    $("feedback").className = "bad";
  }
  $("score").textContent = score; $("total").textContent = total;
}

function reveal() {
  const input = $("answer");
  if (input) input.value = input.dataset.answer;
  if (!answered) { total++; answered = true; $("total").textContent = total; }
}

init().catch(err => { $("feedback").textContent = err.message; });
