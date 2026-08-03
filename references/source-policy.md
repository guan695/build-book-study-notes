# Source and Manifest Policy

Read this file before researching books or editing `sources.json`.

## Source priority

Prefer evidence in this order:

1. Publisher, author, or hosting institution page.
2. National, university, or consortium library catalog.
3. DOI registry or established bibliographic database.
4. Lawfully hosted full text, publisher preview, table of contents, or chapter excerpt.
5. Professional-body catalog or award record.

Retail pages, affiliate lists, blogs, social posts, search snippets, and reader reviews may help discover a title but cannot count toward the two-source verification rule.

Use at least two evidence URLs on distinct hostnames for every book. At least one must establish identity through a publisher, author/institution, library catalog, DOI registry, bibliographic database, or professional body.

## Access tiers

- `full_text`: the relevant book text was lawfully accessible. Detailed claims are allowed only with a page, chapter, or section locator.
- `preview`: only visible preview pages, chapters, excerpts, or a detailed table of contents were accessible. Support only what those visible portions establish.
- `metadata_only`: title, authorship, edition, identifiers, or reputation could be checked, but substantive book content could not. Use only for selection and further reading.

Do not promote a source to a stronger tier because a search result describes it. Record access as observed on `checked_at`.

## Local acquisition and content use

Discovery and identity checks happen online; note writing is local-first. After approval, download every book that will support note prose into the run's `materials/` directory from the exact lawful URL recorded in `local_file.source_url`.

- Set `used_in_notes: true` only for an approved `full_text` book whose local file exists and passes the manifest hash check.
- Set `used_in_notes: false` for previews, metadata-only books, rejected books, and approved further reading not used as evidence.
- Keep `local_file: null` when no lawful downloadable copy exists. Do not capture paywalled pages, automate preview extraction, use borrowed files outside their terms, or use pirate/shadow-library sources.
- Preserve the downloaded file unchanged. Record a relative path, exact download URL, date, MIME type, SHA-256, and a concise license/permission basis.
- Read the local files before drafting. Online pages may recheck identity, currency, and license, but cannot substitute for a missing local content file.
- Every `Bxx` entry in the final `## 来源` section of `notes.md` must belong to a `used_in_notes: true` book and link its local file. Keep detailed provenance in `sources.json` and `evidence.md`.

## Page selection and context control

Keep the complete book on disk, but never send the complete extracted text to model context. Build a temporary local text/page index, search the table of contents and topic terms, and record only the necessary ranges in `selected_sections`.

- Prefer coherent sections over isolated keyword hits. Include prerequisites needed to interpret formulas or claims.
- Read selected ranges in 6–12 page chunks; use smaller chunks for dense mathematics or diagrams.
- After each chunk, add a concise paraphrased card to `evidence.md` with the section ID, local file link, PDF pages, printed pages, supported claims, formulas/definitions, and limitations.
- Render pages containing important formulas, diagrams, tables, or ambiguous extraction and inspect them visually.
- Draft `notes.md` from the completed evidence cards, reopening exact PDF pages for critical checks. Do not draft from the temporary whole-book extraction.
- Delete temporary full-text indexes and page renders after validation. Keep the original files, `selected_sections`, and `evidence.md` for audit.
- If selected ranges exceed roughly 120 pages, narrow the scope or split the topic into modules instead of creating one oversized note.

## Reliability and relevance

For each candidate, write concise, specific reasons:

- `reliability_reason`: author expertise, publisher or institution, edition, adoption, award, or other checkable authority signal.
- `relevance_reason`: visible contents or excerpts that match the agreed scope and learner profile.
- `limitations`: access gaps, age, advanced prerequisites, narrow domain, edition mismatch, or other constraints.

Do not reduce reliability to a fabricated numeric score. Older canonical books are acceptable for stable foundations; time-sensitive topics require current editions or clearly labeled authoritative supplements.

## Manifest schema

Save UTF-8 JSON with this shape. Keep arrays even when empty and use JSON `null` for unknown edition or year values.

```json
{
  "schema_version": 2,
  "topic": "学习主题",
  "scope": "本次覆盖和不覆盖的范围",
  "learner_profile": {
    "level": "初学者",
    "goal": "学习目标",
    "time_budget": "约 2 小时",
    "example_style": "语言无关"
  },
  "phase": "candidate",
  "generated_at": "YYYY-MM-DD",
  "recommended_book_ids": ["B01", "B02", "B03"],
  "books": [
    {
      "id": "B01",
      "title": "Original Book Title",
      "authors": ["Author One"],
      "edition": "2nd edition",
      "year": 2024,
      "publisher": "Publisher",
      "languages": ["en"],
      "identifiers": {
        "isbn13": "9780000000000",
        "doi": "optional"
      },
      "role": "core",
      "access_tier": "preview",
      "decision": "pending",
      "used_in_notes": false,
      "local_file": null,
      "selected_sections": [],
      "reliability_reason": "可核验的可靠性理由",
      "relevance_reason": "与本次范围匹配的理由",
      "limitations": "访问和内容边界",
      "evidence": [
        {
          "kind": "publisher",
          "url": "https://example.org/book",
          "checked_at": "YYYY-MM-DD",
          "locator": "书目页",
          "supports": "identity"
        },
        {
          "kind": "preview",
          "url": "https://example.edu/preview",
          "checked_at": "YYYY-MM-DD",
          "locator": "第 1 章可见页面",
          "supports": "content"
        }
      ]
    }
  ],
  "supplements": []
}
```

After approval, a book used in note prose must instead contain:

```json
{
  "access_tier": "full_text",
  "decision": "approved",
  "used_in_notes": true,
  "local_file": {
    "path": "materials/B01-original-title.pdf",
    "source_url": "https://example.edu/lawful-full-text.pdf",
    "downloaded_at": "YYYY-MM-DD",
    "mime_type": "application/pdf",
    "sha256": "64 lowercase hexadecimal characters",
    "license": "Author-hosted open copy; terms checked on source page"
  },
  "selected_sections": [
    {
      "id": "B01-S01",
      "title": "Chapter 3 — Relevant topic",
      "pdf_start": 42,
      "pdf_end": 51,
      "printed_pages": "31–40",
      "reason": "Directly supports the agreed learning scope"
    }
  ]
}
```

Allowed values:

- `phase`: `candidate`, `approved`, `complete`.
- `role`: `core`, `supplementary`, `further_reading`.
- `access_tier`: `full_text`, `preview`, `metadata_only`.
- `decision`: `pending`, `approved`, `rejected`.
- Evidence `kind`: `publisher`, `author_site`, `institution`, `library_catalog`, `bibliographic_database`, `doi_registry`, `professional_body`, `full_text`, `preview`.
- Evidence `supports`: `identity`, `content`, `both`.
- `local_file.mime_type`: `application/pdf`, `application/epub+zip`, `text/html`, or `text/plain`.

Identifiers may contain `isbn10`, `isbn13`, `doi`, `oclc`, `lccn`, or `other`. Use at least one stable identifier when one exists; otherwise use `other` to state why none is available. Never guess an identifier.

## Supplement schema

Use supplements only when they verify, update, or fill a genuine gap:

```json
{
  "id": "S01",
  "type": "official_document",
  "title": "Source title",
  "organization": "Responsible organization",
  "url": "https://example.org/source",
  "checked_at": "YYYY-MM-DD",
  "role": "verification",
  "locator": "Relevant section",
  "limitations": "Why this is supplementary"
}
```

Allowed `type` values are `paper`, `official_document`, `university_course`, `standard`, and `other_authoritative`. Allowed `role` values are `verification`, `gap_fill`, and `currency_update`.

## Approval and failure rules

- In `candidate`, keep every decision `pending`.
- In `approved` or `complete`, require 3–5 approved books and at least two approved `full_text` books downloaded and marked `used_in_notes: true`.
- Every `used_in_notes: true` book must have non-overlapping `selected_sections`. In `complete`, every selected section must have a matching `evidence.md` card.
- A preview or metadata-only book may remain as approved further reading, but it cannot support note prose.
- If fewer than five trustworthy candidates exist, keep the smaller honest list and explain the warning; never pad it.
- If fewer than two lawful full-text books can be downloaded, stop after the approved book list and invite the user to narrow the scope or provide lawfully obtained copies.
- Keep edition-specific page locators separate. Never transfer page numbers between editions.
