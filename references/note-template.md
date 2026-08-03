# Concise Study Note Template

Read this file only after the user approves the books and the manifest passes validation.

Write a reader-facing note, not a research report. Keep detailed evidence and workflow metadata in `sources.json` and `evidence.md`.

```markdown
# <学习主题>

## <核心概念>

直接解释问题、关键定义和必要公式。

## <关键原理或组成>

按概念关系综合多本书；需要时使用一个简洁表格。

## <如何应用>

给出可执行的步骤、判断方法或推理过程。

## <完整例子>

给出可复算或可执行的例子，不跳关键步骤。

## <常见问题>

- 问题 → 原因 → 处理方式。

## 来源

本笔记综合以下本地全文中的指定章节；自编内容应在一句话内说明。

- B01 — *Original Book Title*，<已核验章节或页段>，[本地文件](materials/B01-original-title.pdf)。
- B02 — *Original Book Title*，<已核验章节或页段>，[本地文件](materials/B02-original-title.pdf)。
```

## Writing rules

- Write clear Chinese and retain the original technical term in parentheses on first use.
- Use one `#` title and 4–6 `##` content sections followed by `## 来源`; avoid deeper headings unless the topic truly requires them.
- Keep only learning content in the body. Integrate prerequisites, scope limits, and summaries where they are needed instead of creating separate sections.
- Do not add learning profiles, evidence declarations, time plans, concept maps, exercises, self-tests, quick summaries, next steps, extended reading lists, or footnote sections by default.
- Draft only after every `selected_sections` entry has a matching card in `evidence.md`. Reopen exact PDF pages for critical checks.
- List only books with `used_in_notes: true` under `## 来源`. Each `- Bxx — ...` line must name the original title, give an honest section/page locator, and link the local file.
- Add a short inline locator such as `(B01, §3.2)` only for direct quotations, source disagreement, or a claim where paragraph-level traceability is materially useful.
- Include formulas, derivations, code, chronology, tables, or comparisons only when they help explain the topic.
- Prefer paraphrase; do not include long quotations or reconstruct substantial portions of a book.
