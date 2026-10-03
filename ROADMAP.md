# Lingua Lab roadmap

## Phase 1: Real data (biggest gap right now)
The site works but only has 3 sentences and about 28 dictionary entries.

1. Write `tools/build_data.py`:
   - Download Tatoeba sentence and link files for English, Italian and French.
   - Keep sentence triples that exist in all three languages, ideally under about 10 words.
   - Choose a blank word for each language, such as the longest word that has a dictionary entry.
2. Add dictionary data:
   - Get English glosses from the kaikki.org Wiktionary extract.
   - Get native Italian and French definitions from the Italian and French Wiktionary extracts.
   - Keep only the words that appear in the sentences, so the JSON files stay small.
3. Handle inflections. Map conjugated and plural forms (`mangio`, `jours`) to their base word, since the hover lookup is exact-match today.
4. Credit Tatoeba (CC-BY) and Wiktionary (CC-BY-SA) in a footer or `about.html`, and generate the data files from the script rather than hand-editing them.
5. Check the size of the JSON files. If they grow past a few MB, split them into chunks or load them per language.

## Phase 2: Quiz quality
1. Pick better blanks, skipping articles and prepositions unless the learner wants them.
2. Accept answers more leniently, for example a missing accent or a variant like `l'` forms.
3. Add a hint (first letter, or the English word) and a difficulty setting based on sentence length or word frequency.
4. Avoid repeating sentences until the pool is used up, and show the correct answer in context after each question.
5. Keep the score and the list of missed words in `localStorage`.
6. Make hover work on touch devices (tap to show the definition), since `:hover` alone doesn't work on phones.
7. Add links to Collins and Reverso in the tooltip. Linking out avoids scraping them.

## Phase 3: Polish and quality
1. Make the layout work on mobile, add basic accessibility (keyboard focus, ARIA labels, contrast), and add a dark mode.
2. Add a footer and nav shared across pages.
3. Add a basic test script for `normalize` and `lookup`, and a GitHub Action to rebuild the data on demand.
4. Add a `README.md` covering how to run the site locally, how to rebuild the data, and the data licences.

## Phase 4: New features (each gets its own page)
Roughly in order of effort:

1. `flashcards.html`: spaced repetition built on the same dictionary.
2. `words.html`: a searchable word browser.
3. Verb conjugation tables, using Wiktionary conjugation data.
4. Listening practice, using the browser's text-to-speech or Tatoeba audio where it exists.
5. A progress page showing streaks and weak words.
6. More languages. If the data model keys everything by language code, adding Spanish or German is mostly a data job.

## Decisions to make along the way
- Whether the data stays as static JSON (simple, free hosting) or moves to a backend later. A backend is only needed for accounts or syncing progress across devices.
- Whether to add a build tool or framework. Stay with plain HTML/JS until a third or fourth page makes the shared code painful.
