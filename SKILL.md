---
name: build-book-study-notes
description: Search the open web for genuine, reliable books, verify bibliographic identity and lawful full-text access, download approved content sources locally, generate a reviewable sources.json and booklist.md, and only after user approval synthesize a structured Chinese Markdown study note from verified local files. Use when the user asks to learn a topic from trustworthy books, find textbooks or reading lists, or create source-grounded study notes; do not use for generic web summaries that do not require books.
---

# Build Book Study Notes

Create Chinese study notes grounded in books that were actually found and checked. Keep book discovery and note writing as two separate user-approved phases.

## Resolve paths

Treat the user's current writable working directory as the output root unless the user explicitly chooses another directory. Never write generated notes or downloaded books into the installed skill directory. Store each run in `notes/<YYYYMMDD>-<short-topic-slug>/` under the output root. If the current directory is not writable, ask for an output directory before creating artifacts.

Resolve bundled references and scripts relative to the directory containing this `SKILL.md`.

Use these fixed artifact names:

- `sources.json`: machine-readable research record and approval state.
- `booklist.md`: rendered candidate or approved book list.
- `evidence.md`: concise, page-located evidence cards produced from chunked local reading.
- `notes.md`: clean learning content with a short source section; create it only in Phase 2.
- `materials/`: unchanged lawful full-text files actually used by `notes.md`; create it only after approval.

## Phase 0: Confirm the learning brief

1. Collect the topic, current level, learning goal, available time, and preferred example style when they materially affect the result.
2. If information is unavailable or an automated run cannot wait, default to beginner level, a practical foundation, about two hours, and language-neutral examples.
3. If the topic is too broad for one coherent note, propose 3–7 narrower modules and stop for scope confirmation.
4. Record the agreed brief in `learner_profile` and `scope` rather than creating another request file.

## Phase 1: Research and request book approval

1. Read [references/source-policy.md](references/source-policy.md) completely before searching or writing `sources.json`.
2. Browse the live open web. Never produce a book list from model memory alone.
3. Target 5–8 candidates in any language, favoring the strongest sources over a language quota. Do not pad a scarce topic with weak books.
4. Verify every candidate with at least two independent hostnames. Include an authoritative identity record such as a publisher, author/institution site, library catalog, DOI registry, or professional body.
5. Assign `full_text`, `preview`, or `metadata_only` strictly from content actually accessible during this run.
6. Write `sources.json` with `phase: candidate`, `decision: pending` for all books, and 3–5 evidence-backed `recommended_book_ids` when possible.
7. Run the bundled script from the skill directory:

   ```powershell
   python -X utf8 scripts/book_manifest.py <sources.json> --check
   python -X utf8 scripts/book_manifest.py <sources.json> --output <booklist.md>
   ```

8. Report the artifact paths, summarize the recommended IDs, and ask the user to approve the recommendation or name 3–5 IDs.
9. Stop. Do not create `notes.md` before explicit approval.

## Phase 2: Synthesize the approved note

1. Read the existing manifest and the user's approval. Mark chosen books `approved`, other books `rejected`, and set `phase: approved`.
2. Select only approved `full_text` books for substantive use. Set those books `used_in_notes: true`; keep previews, metadata-only books, and unused further reading `false`.
3. Create `materials/` and download every `used_in_notes` book from a lawful official, author, institution, or publisher-provided URL. Never download a preview as if it were a complete book.
4. Verify each file is the expected type rather than an HTML/error response. Preserve it unchanged, compute SHA-256, and record `local_file.path`, `source_url`, `downloaded_at`, `mime_type`, `sha256`, and `license` in `sources.json`.
5. Require at least two approved, locally downloaded `full_text` books for the requested scope. If lawful downloads are insufficient, explain the gap and stop instead of substituting web snippets or model knowledge.
6. Build a temporary local page/text index under `tmp/pdfs/`. Inspect the table of contents and keyword hits without sending the whole extraction to model context. Record coherent, non-overlapping ranges in each used book's `selected_sections`.
7. Re-run `book_manifest.py --check` and regenerate `booklist.md`. Resolve every error before deep reading.
8. Read each selected range in 6–12 page chunks, using smaller chunks for dense mathematics. After every chunk, append a paraphrased card to `evidence.md` headed by its section ID, with the local link, PDF and printed page ranges, claims, formulas/definitions, and limitations. Do not copy long passages.
9. Render and visually inspect pages containing important formulas, figures, tables, or ambiguous extraction. Reopen exact pages when a card is uncertain.
10. Read [references/note-template.md](references/note-template.md) completely. Draft from the compact evidence cards, not from the whole-book extraction; reopen only critical source pages during synthesis.
11. Synthesize across books by concept; do not write disconnected per-book summaries unless requested. Create `notes.md` in Chinese with only a title, 4–6 content sections, and a final `## 来源` section. Use no more than two heading levels. Do not add separate learning-profile, evidence-declaration, time-plan, prerequisite, concept-map, exercise, self-test, quick-summary, or next-step sections unless the user asks for them.
12. In `## 来源`, list every `used_in_notes: true` book in one concise `- Bxx — ...` bullet containing its original title, verified chapter or page range, and local file link. Keep detailed provenance in `sources.json` and `evidence.md`, not in the reader-facing note. Add unobtrusive inline locators only when needed for a quotation, disagreement, or unusually important claim. Never list an approved preview or any book with `used_in_notes: false` as a substantive source.
13. Mark non-book sources with `Sxx` IDs and explicitly describe them as supplementary. Never make them appear to be book content.
14. Set `phase: complete`, re-run the manifest check, regenerate `booklist.md`, and delete temporary indexes/renders. Keep `materials/`, `selected_sections`, `evidence.md`, and `notes.md` for audit.

## Non-negotiable evidence rules

- Do not treat search snippets, retailer copy, user reviews, or unsourced book lists as evidence.
- Do not invent titles, authors, editions, identifiers, page numbers, quotations, or claims about unread chapters.
- Use `metadata_only` books for selection or further reading only, never for substantive note claims.
- Use book content in note prose only after a lawful full text or user-supplied copy has been saved locally and validated by the manifest script.
- Do not bypass paywalls or use pirate and shadow-library links.
- Prefer paraphrase. Keep any necessary quotation short and within applicable copyright limits.
- When sources disagree, show the disagreement and its edition/context instead of silently choosing a side.
- If browsing is unavailable, stop after explaining that live verification is required.
- If a lawful local copy cannot be obtained, keep the book as unused selection/further reading evidence or stop; never silently fall back to online snippets.
- Never load a complete large book or complete extracted text into model context. If the necessary ranges exceed roughly 120 pages, narrow or split the learning scope first.
