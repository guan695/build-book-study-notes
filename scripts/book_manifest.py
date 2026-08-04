#!/usr/bin/env python3
"""校验书籍来源清单，并按需生成可阅读的书目文件。"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


PHASES = {"candidate", "approved", "complete"}
ROLES = {"core", "supplementary", "further_reading"}
ACCESS_TIERS = {"full_text", "preview", "metadata_only"}
DECISIONS = {"pending", "approved", "rejected"}
EVIDENCE_KINDS = {
    "publisher",
    "author_site",
    "institution",
    "library_catalog",
    "bibliographic_database",
    "doi_registry",
    "professional_body",
    "full_text",
    "preview",
}
IDENTITY_KINDS = {
    "publisher",
    "author_site",
    "institution",
    "library_catalog",
    "bibliographic_database",
    "doi_registry",
    "professional_body",
}
SUPPORTS = {"identity", "content", "both"}
SUPPLEMENT_TYPES = {
    "paper",
    "official_document",
    "university_course",
    "standard",
    "other_authoritative",
}
SUPPLEMENT_ROLES = {"verification", "gap_fill", "currency_update"}
ID_KEYS = {"isbn10", "isbn13", "doi", "oclc", "lccn", "other"}
LOCAL_MIME_TYPES = {"application/pdf", "application/epub+zip", "text/html", "text/plain"}


def nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def valid_date(value: Any) -> bool:
    if not nonempty_string(value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def valid_url(value: Any) -> bool:
    if not nonempty_string(value):
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.hostname)


def hostname(value: str) -> str:
    host = (urlparse(value).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def compact_isbn(value: Any) -> str:
    return re.sub(r"[-\s]", "", str(value)).upper()


def valid_isbn10(value: Any) -> bool:
    isbn = compact_isbn(value)
    if not re.fullmatch(r"\d{9}[\dX]", isbn):
        return False
    digits = [10 if char == "X" else int(char) for char in isbn]
    return sum((10 - index) * digit for index, digit in enumerate(digits)) % 11 == 0


def valid_isbn13(value: Any) -> bool:
    isbn = compact_isbn(value)
    if not re.fullmatch(r"\d{13}", isbn):
        return False
    total = sum((1 if index % 2 == 0 else 3) * int(char) for index, char in enumerate(isbn[:12]))
    check = (10 - total % 10) % 10
    return check == int(isbn[-1])


def normalize_text(value: Any) -> str:
    return re.sub(r"[^\w]+", "", str(value).casefold())


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_string(mapping: dict[str, Any], key: str, path: str, errors: list[str]) -> None:
    if not nonempty_string(mapping.get(key)):
        errors.append(f"{path}.{key} 必须是非空字符串")


def validate_selected_sections(book: dict[str, Any], index: int, errors: list[str]) -> None:
    path = f"books[{index}].selected_sections"
    sections = book.get("selected_sections")
    if not isinstance(sections, list):
        errors.append(f"{path} 必须是数组")
        return
    if book.get("used_in_notes") is True and not sections:
        errors.append(f"{path} 用于正文的书籍必须记录至少一个精读页段")
    if book.get("used_in_notes") is not True and sections:
        errors.append(f"{path} 只有 used_in_notes=true 的书籍才能设置精读页段")

    section_ids: list[str] = []
    ranges_by_module: dict[str, list[tuple[int, int, str]]] = {}
    book_id = str(book.get("id", ""))
    for section_index, section in enumerate(sections):
        section_path = f"{path}[{section_index}]"
        if not isinstance(section, dict):
            errors.append(f"{section_path} 必须是对象")
            continue
        for key in ("id", "title", "printed_pages", "reason"):
            require_string(section, key, section_path, errors)
        section_id = str(section.get("id", ""))
        section_pattern = rf"(?:M\d{{2}}-)?{re.escape(book_id)}-S\d{{2,}}"
        if not re.fullmatch(section_pattern, section_id):
            errors.append(f"{section_path}.id 必须匹配 {book_id}-S01 或 M01-{book_id}-S01 形式")
        section_ids.append(section_id)
        start = section.get("pdf_start")
        end = section.get("pdf_end")
        if not isinstance(start, int) or isinstance(start, bool) or start < 1:
            errors.append(f"{section_path}.pdf_start 必须是正整数")
            continue
        if not isinstance(end, int) or isinstance(end, bool) or end < start:
            errors.append(f"{section_path}.pdf_end 必须是不小于 pdf_start 的整数")
            continue
        module_match = re.match(r"(M\d{2})-", section_id)
        module_id = module_match.group(1) if module_match else "__legacy__"
        ranges_by_module.setdefault(module_id, []).append((start, end, section_id))

    duplicates = sorted({item for item in section_ids if section_ids.count(item) > 1})
    if duplicates:
        errors.append(f"{path} ID 重复: {', '.join(duplicates)}")
    for module_ranges in ranges_by_module.values():
        ordered_ranges = sorted(module_ranges)
        for previous, current in zip(ordered_ranges, ordered_ranges[1:]):
            if current[0] <= previous[1]:
                errors.append(f"{path} 页段重叠: {previous[2]} 与 {current[2]}")


def validate_evidence(evidence: Any, path: str, errors: list[str]) -> set[str]:
    if not isinstance(evidence, list) or len(evidence) < 2:
        errors.append(f"{path} 至少需要两条独立证据")
        return set()

    hosts: set[str] = set()
    has_identity = False
    for index, item in enumerate(evidence):
        item_path = f"{path}[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{item_path} 必须是对象")
            continue
        kind = item.get("kind")
        supports = item.get("supports")
        if kind not in EVIDENCE_KINDS:
            errors.append(f"{item_path}.kind 不受支持: {kind!r}")
        if supports not in SUPPORTS:
            errors.append(f"{item_path}.supports 不受支持: {supports!r}")
        if kind in IDENTITY_KINDS and supports in {"identity", "both"}:
            has_identity = True
        url = item.get("url")
        if not valid_url(url):
            errors.append(f"{item_path}.url 必须是 http/https URL")
        else:
            hosts.add(hostname(url))
        if not valid_date(item.get("checked_at")):
            errors.append(f"{item_path}.checked_at 必须是 YYYY-MM-DD")
        require_string(item, "locator", item_path, errors)

    if len(hosts) < 2:
        errors.append(f"{path} 必须来自至少两个不同主机名")
    if not has_identity:
        errors.append(f"{path} 缺少权威身份核验来源")
    return hosts


def validate_local_file(
    book: dict[str, Any], index: int, manifest_path: Path | None, errors: list[str]
) -> None:
    path = f"books[{index}]"
    used_in_notes = book.get("used_in_notes")
    if not isinstance(used_in_notes, bool):
        errors.append(f"{path}.used_in_notes 必须是布尔值")
        used_in_notes = False
    if used_in_notes and book.get("decision") != "approved":
        errors.append(f"{path} 只有 approved 书籍才能用于正文")
    if used_in_notes and book.get("access_tier") != "full_text":
        errors.append(f"{path} 用于正文的本地书籍必须是 full_text")

    if "local_file" not in book:
        errors.append(f"{path}.local_file 必须显式设为对象或 null")
    local_file = book.get("local_file")
    if local_file is None:
        if used_in_notes:
            errors.append(f"{path} 用于正文时必须提供 local_file")
        return
    if not isinstance(local_file, dict):
        errors.append(f"{path}.local_file 必须是对象或 null")
        return

    for key in ("path", "source_url", "sha256", "license"):
        require_string(local_file, key, f"{path}.local_file", errors)
    if not valid_url(local_file.get("source_url")):
        errors.append(f"{path}.local_file.source_url 必须是 http/https URL")
    if not valid_date(local_file.get("downloaded_at")):
        errors.append(f"{path}.local_file.downloaded_at 必须是 YYYY-MM-DD")
    if local_file.get("mime_type") not in LOCAL_MIME_TYPES:
        errors.append(f"{path}.local_file.mime_type 不受支持: {local_file.get('mime_type')!r}")
    expected_hash = str(local_file.get("sha256", ""))
    if not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
        errors.append(f"{path}.local_file.sha256 必须是 64 位小写十六进制 SHA-256")

    relative_text = local_file.get("path")
    if not nonempty_string(relative_text):
        return
    relative_path = Path(relative_text)
    if relative_path.is_absolute() or ".." in relative_path.parts or not relative_path.parts or relative_path.parts[0] != "materials":
        errors.append(f"{path}.local_file.path 必须是 materials/ 下的安全相对路径")
        return
    if manifest_path is None:
        errors.append(f"{path}.local_file 无法在未提供清单路径时核验")
        return

    base = manifest_path.parent.resolve()
    resolved = (base / relative_path).resolve()
    try:
        resolved.relative_to(base)
    except ValueError:
        errors.append(f"{path}.local_file.path 越出本次学习目录")
        return
    if not resolved.is_file():
        errors.append(f"{path}.local_file.path 文件不存在: {relative_text}")
        return
    if resolved.stat().st_size == 0:
        errors.append(f"{path}.local_file.path 文件为空: {relative_text}")
        return
    if local_file.get("mime_type") == "application/pdf":
        with resolved.open("rb") as stream:
            if stream.read(5) != b"%PDF-":
                errors.append(f"{path}.local_file.path 不是有效 PDF 文件头: {relative_text}")
    if re.fullmatch(r"[0-9a-f]{64}", expected_hash) and file_sha256(resolved) != expected_hash:
        errors.append(f"{path}.local_file.sha256 与本地文件不一致")

def validate_book(book: Any, index: int, manifest_path: Path | None, errors: list[str]) -> None:
    path = f"books[{index}]"
    if not isinstance(book, dict):
        errors.append(f"{path} 必须是对象")
        return

    for key in ("id", "title", "publisher", "reliability_reason", "relevance_reason", "limitations"):
        require_string(book, key, path, errors)

    if not re.fullmatch(r"B\d{2,}", str(book.get("id", ""))):
        errors.append(f"{path}.id 必须匹配 B01 形式")
    authors = book.get("authors")
    if not isinstance(authors, list) or not authors or not all(nonempty_string(author) for author in authors):
        errors.append(f"{path}.authors 必须是非空字符串数组")
    languages = book.get("languages")
    if not isinstance(languages, list) or not languages or not all(nonempty_string(language) for language in languages):
        errors.append(f"{path}.languages 必须是非空字符串数组")
    if book.get("edition") is not None and not nonempty_string(book.get("edition")):
        errors.append(f"{path}.edition 必须是字符串或 null")
    year = book.get("year")
    if year is not None and (not isinstance(year, int) or isinstance(year, bool) or not 1400 <= year <= 2200):
        errors.append(f"{path}.year 必须是合理年份或 null")
    if book.get("role") not in ROLES:
        errors.append(f"{path}.role 不受支持: {book.get('role')!r}")
    if book.get("access_tier") not in ACCESS_TIERS:
        errors.append(f"{path}.access_tier 不受支持: {book.get('access_tier')!r}")
    if book.get("decision") not in DECISIONS:
        errors.append(f"{path}.decision 不受支持: {book.get('decision')!r}")

    identifiers = book.get("identifiers")
    if not isinstance(identifiers, dict) or not identifiers:
        errors.append(f"{path}.identifiers 必须至少包含一个标识或 other 说明")
    else:
        unknown = set(identifiers) - ID_KEYS
        if unknown:
            errors.append(f"{path}.identifiers 含未知键: {', '.join(sorted(unknown))}")
        for key, value in identifiers.items():
            if not nonempty_string(value):
                errors.append(f"{path}.identifiers.{key} 必须是非空字符串")
        if "isbn10" in identifiers and not valid_isbn10(identifiers["isbn10"]):
            errors.append(f"{path}.identifiers.isbn10 校验失败")
        if "isbn13" in identifiers and not valid_isbn13(identifiers["isbn13"]):
            errors.append(f"{path}.identifiers.isbn13 校验失败")

    evidence = book.get("evidence")
    validate_evidence(evidence, f"{path}.evidence", errors)
    if book.get("access_tier") in {"full_text", "preview"} and isinstance(evidence, list):
        has_content = any(
            isinstance(item, dict) and item.get("supports") in {"content", "both"}
            for item in evidence
        )
        if not has_content:
            errors.append(f"{path} 的访问等级需要至少一条 content/both 证据")
    validate_local_file(book, index, manifest_path, errors)
    validate_selected_sections(book, index, errors)


def validate_supplement(item: Any, index: int, errors: list[str]) -> None:
    path = f"supplements[{index}]"
    if not isinstance(item, dict):
        errors.append(f"{path} 必须是对象")
        return
    for key in ("id", "title", "organization", "locator", "limitations"):
        require_string(item, key, path, errors)
    if not re.fullmatch(r"S\d{2,}", str(item.get("id", ""))):
        errors.append(f"{path}.id 必须匹配 S01 形式")
    if item.get("type") not in SUPPLEMENT_TYPES:
        errors.append(f"{path}.type 不受支持: {item.get('type')!r}")
    if item.get("role") not in SUPPLEMENT_ROLES:
        errors.append(f"{path}.role 不受支持: {item.get('role')!r}")
    if not valid_url(item.get("url")):
        errors.append(f"{path}.url 必须是 http/https URL")
    if not valid_date(item.get("checked_at")):
        errors.append(f"{path}.checked_at 必须是 YYYY-MM-DD")


def validate_extracts(data: dict[str, Any], manifest_path: Path | None, errors: list[str]) -> None:
    if manifest_path is None:
        errors.append("complete 阶段需要清单路径以核验 extracts/")
        return
    extracts_dir = manifest_path.parent / "extracts"
    if not extracts_dir.is_dir():
        errors.append("complete 阶段必须存在 extracts/ 目录")
        return
    for book in data.get("books", []):
        if not isinstance(book, dict) or book.get("used_in_notes") is not True:
            continue
        for section in book.get("selected_sections", []):
            if not isinstance(section, dict):
                continue
            section_id = str(section.get("id", ""))
            extract_path = extracts_dir / f"{section_id}.pdf"
            if not extract_path.is_file():
                errors.append(f"缺少裁剪文件: extracts/{section_id}.pdf")
            elif extract_path.stat().st_size == 0:
                errors.append(f"裁剪文件为空: extracts/{section_id}.pdf")
            else:
                with extract_path.open("rb") as stream:
                    if stream.read(5) != b"%PDF-":
                        errors.append(f"裁剪文件不是有效 PDF: extracts/{section_id}.pdf")


def validate_note_sources(data: dict[str, Any], manifest_path: Path | None, errors: list[str]) -> None:
    if manifest_path is None:
        errors.append("complete 阶段需要清单路径以核验 notes.md 与本地来源")
        return
    notes_dir = manifest_path.parent / "notes"
    legacy_notes_path = manifest_path.parent / "notes.md"
    if notes_dir.is_dir():
        note_paths = sorted(notes_dir.glob("*.md"))
        if not note_paths:
            errors.append("complete 阶段必须存在 notes/*.md")
            return
        content = "\n".join(path.read_text(encoding="utf-8-sig") for path in note_paths)
    elif legacy_notes_path.is_file():
        content = legacy_notes_path.read_text(encoding="utf-8-sig")
    else:
        errors.append("complete 阶段必须存在 notes/*.md 或 notes.md")
        return
    mentioned_ids = set(re.findall(r"\bB\d{2,}\b", content))
    source_entries: dict[str, list[str]] = {}
    for match in re.finditer(
        r"(?m)^-\s+(?:\*\*|`)?(B\d{2,})(?:\*\*|`)?(?=[\s—–:：-])[^\r\n]*$",
        content,
    ):
        source_entries.setdefault(match.group(1), []).append(match.group(0))
    used_books = {
        str(book.get("id")): book
        for book in data.get("books", [])
        if isinstance(book, dict) and book.get("used_in_notes") is True
    }
    unexpected = sorted(mentioned_ids - set(used_books))
    if unexpected:
        errors.append(f"notes.md 引用了未下载或未标记用于正文的书籍: {', '.join(unexpected)}")
    missing = sorted(set(used_books) - set(source_entries))
    if missing:
        errors.append(f"标记用于正文的书籍未在 notes.md 来源列表中出现: {', '.join(missing)}")

    for book_id, book in used_books.items():
        local_file = book.get("local_file")
        if not isinstance(local_file, dict) or not nonempty_string(local_file.get("path")):
            continue
        relative_path = str(local_file["path"]).replace("\\", "/")
        if not any(f"]({relative_path})" in entry for entry in source_entries.get(book_id, [])):
            errors.append(f"notes.md 的 {book_id} 来源条目必须链接本地文件 {local_file['path']}")


def validate_manifest(data: Any, manifest_path: Path | None = None) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(data, dict):
        return ["清单根节点必须是对象"], warnings

    if data.get("schema_version") != 2:
        errors.append("schema_version 必须为 2")
    for key in ("topic", "scope"):
        require_string(data, key, "root", errors)
    if not valid_date(data.get("generated_at")):
        errors.append("generated_at 必须是 YYYY-MM-DD")
    phase = data.get("phase")
    if phase not in PHASES:
        errors.append(f"phase 不受支持: {phase!r}")

    profile = data.get("learner_profile")
    if not isinstance(profile, dict):
        errors.append("learner_profile 必须是对象")
    else:
        for key in ("level", "goal", "time_budget", "example_style"):
            require_string(profile, key, "learner_profile", errors)

    books = data.get("books")
    if not isinstance(books, list) or not books:
        errors.append("books 必须是非空数组")
        books = []
    for index, book in enumerate(books):
        validate_book(book, index, manifest_path, errors)

    book_ids = [book.get("id") for book in books if isinstance(book, dict)]
    duplicates = sorted({book_id for book_id in book_ids if book_ids.count(book_id) > 1})
    if duplicates:
        errors.append(f"书籍 ID 重复: {', '.join(map(str, duplicates))}")

    seen_titles: dict[tuple[str, str], str] = {}
    seen_identifiers: dict[tuple[str, str], str] = {}
    for book in books:
        if not isinstance(book, dict):
            continue
        authors = book.get("authors") or []
        key = (normalize_text(book.get("title", "")), normalize_text(authors[0] if authors else ""))
        if all(key):
            if key in seen_titles:
                errors.append(f"疑似重复书目: {seen_titles[key]} 与 {book.get('id')}")
            else:
                seen_titles[key] = str(book.get("id"))
        identifiers = book.get("identifiers")
        if isinstance(identifiers, dict):
            for id_kind, value in identifiers.items():
                if id_kind == "other" or not nonempty_string(value):
                    continue
                id_key = (id_kind, compact_isbn(value) if id_kind.startswith("isbn") else str(value).casefold())
                if id_key in seen_identifiers:
                    errors.append(f"标识重复: {seen_identifiers[id_key]} 与 {book.get('id')} 的 {id_kind}")
                else:
                    seen_identifiers[id_key] = str(book.get("id"))

    recommendations = data.get("recommended_book_ids")
    if not isinstance(recommendations, list) or not all(nonempty_string(item) for item in recommendations):
        errors.append("recommended_book_ids 必须是字符串数组")
        recommendations = []
    if len(set(recommendations)) != len(recommendations):
        errors.append("recommended_book_ids 不得重复")
    unknown_recommendations = sorted(set(recommendations) - set(book_ids))
    if unknown_recommendations:
        errors.append(f"推荐 ID 不存在: {', '.join(unknown_recommendations)}")

    if phase == "candidate":
        non_pending = [book.get("id") for book in books if isinstance(book, dict) and book.get("decision") != "pending"]
        if non_pending:
            errors.append(f"candidate 阶段所有书籍必须 pending: {', '.join(map(str, non_pending))}")
        if not 3 <= len(books) <= 5:
            warnings.append(f"候选书通常应为 3–5 本，当前为 {len(books)} 本；不要为达数量而降低质量")
        if not 1 <= len(recommendations) <= 3:
            warnings.append(f"推荐书通常应为 1–3 本，当前为 {len(recommendations)} 本")
    elif phase in {"approved", "complete"}:
        approved = [book for book in books if isinstance(book, dict) and book.get("decision") == "approved"]
        if not 1 <= len(approved) <= 3:
            errors.append(f"{phase} 阶段只能选择 1–3 本书，当前为 {len(approved)} 本")
        used = [book for book in approved if book.get("used_in_notes") is True]
        if not 1 <= len(used) <= 3:
            errors.append(f"{phase} 阶段必须有 1–3 本已下载并用于正文的书籍")
        core_used = [book for book in used if book.get("role") == "core"]
        if len(core_used) != 1:
            errors.append(f"{phase} 阶段必须恰好有一本用于正文的主教材，当前为 {len(core_used)} 本")
        invalid_support = [
            str(book.get("id"))
            for book in used
            if book.get("role") not in {"core", "supplementary"}
        ]
        if invalid_support:
            errors.append(f"用于正文的书籍只能是主教材或补充书: {', '.join(invalid_support)}")

    supplements = data.get("supplements")
    if not isinstance(supplements, list):
        errors.append("supplements 必须是数组")
        supplements = []
    for index, item in enumerate(supplements):
        validate_supplement(item, index, errors)
    supplement_ids = [item.get("id") for item in supplements if isinstance(item, dict)]
    duplicate_supplements = sorted({item_id for item_id in supplement_ids if supplement_ids.count(item_id) > 1})
    if duplicate_supplements:
        errors.append(f"补充来源 ID 重复: {', '.join(map(str, duplicate_supplements))}")

    if phase == "complete":
        validate_extracts(data, manifest_path, errors)
        validate_note_sources(data, manifest_path, errors)

    return errors, warnings


def md_text(value: Any) -> str:
    if value is None:
        return "未注明"
    return str(value).replace("\r", " ").replace("\n", " ").strip()


def render_booklist(data: dict[str, Any]) -> str:
    phase_labels = {"candidate": "候选书审批", "approved": "书单已批准", "complete": "笔记已完成"}
    access_labels = {"full_text": "全文可访问", "preview": "部分预览", "metadata_only": "仅书目信息"}
    decision_labels = {"pending": "待确认", "approved": "已选择", "rejected": "未选择"}
    role_labels = {"core": "核心", "supplementary": "补充", "further_reading": "延伸阅读"}
    profile = data["learner_profile"]
    lines = [
        f"# {md_text(data['topic'])}：书目与证据清单",
        "",
        f"- 阶段：{phase_labels.get(data['phase'], md_text(data['phase']))}",
        f"- 生成/核验日期：{md_text(data['generated_at'])}",
        f"- 学习画像：{md_text(profile['level'])}；{md_text(profile['goal'])}；{md_text(profile['time_budget'])}",
        f"- 示例形式：{md_text(profile['example_style'])}",
        f"- 本次范围：{md_text(data['scope'])}",
        "",
        "## 证据等级",
        "",
        "- `full_text`：相关正文可合法访问，可按实际页码、章节或小节引用。",
        "- `preview`：只允许使用本次实际可见的目录、章节或摘录。",
        "- `metadata_only`：只能证明书籍身份与推荐价值，不能支撑笔记正文。",
        "",
        "## 推荐组合",
        "",
    ]
    recommendations = data.get("recommended_book_ids", [])
    lines.append("、".join(f"`{item}`" for item in recommendations) if recommendations else "尚无推荐组合。")
    lines.extend(["", "## 候选书", ""])

    for book in data["books"]:
        edition = md_text(book.get("edition"))
        year = md_text(book.get("year"))
        identifiers = "；".join(f"{key.upper()}: {md_text(value)}" for key, value in book["identifiers"].items())
        lines.extend(
            [
                f"### {book['id']} · {md_text(book['title'])}",
                "",
                f"- 作者：{', '.join(md_text(author) for author in book['authors'])}",
                f"- 出版信息：{md_text(book['publisher'])}，{year}，{edition}",
                f"- 语言：{', '.join(md_text(language) for language in book['languages'])}",
                f"- 标识：{identifiers}",
                f"- 定位：{role_labels.get(book['role'], book['role'])}；{access_labels.get(book['access_tier'], book['access_tier'])}；{decision_labels.get(book['decision'], book['decision'])}",
                f"- 正文使用：{'是（必须从本地实体文件读取）' if book['used_in_notes'] else '否'}",
                f"- 可靠性：{md_text(book['reliability_reason'])}",
                f"- 相关性：{md_text(book['relevance_reason'])}",
                f"- 局限：{md_text(book['limitations'])}",
                "- 核验证据：",
            ]
        )
        for evidence in book["evidence"]:
            label = f"{evidence['kind']} / {evidence['supports']} / {md_text(evidence['locator'])}"
            lines.append(f"  - [{label}]({evidence['url']})（核验于 {evidence['checked_at']}）")
        local_file = book.get("local_file")
        if isinstance(local_file, dict):
            local_path = str(local_file["path"]).replace("\\", "/")
            lines.extend(
                [
                    "- 本地实体文件：",
                    f"  - [打开本地文件]({local_path})",
                    f"  - 下载源：[{md_text(local_file['source_url'])}]({local_file['source_url']})",
                    f"  - 下载日期：{local_file['downloaded_at']}；类型：`{local_file['mime_type']}`",
                    f"  - SHA-256：`{local_file['sha256']}`",
                    f"  - 获取许可：{md_text(local_file['license'])}",
                ]
            )
        elif book["used_in_notes"]:
            lines.append("- 本地实体文件：缺失（清单校验将失败）")
        else:
            lines.append("- 本地实体文件：未下载；不作为笔记正文依据。")
        sections = book.get("selected_sections", [])
        if sections:
            lines.append("- 本次精读页段：")
            for section in sections:
                lines.append(
                    f"  - `{section['id']}` · {md_text(section['title'])}；"
                    f"PDF 页 {section['pdf_start']}–{section['pdf_end']}；"
                    f"书内页 {md_text(section['printed_pages'])}；{md_text(section['reason'])}"
                )
        lines.append("")

    lines.extend(["## 非书籍补充来源", ""])
    if data["supplements"]:
        for item in data["supplements"]:
            lines.extend(
                [
                    f"### {item['id']} · {md_text(item['title'])}",
                    "",
                    f"- 机构：{md_text(item['organization'])}",
                    f"- 用途：{md_text(item['role'])}；定位：{md_text(item['locator'])}",
                    f"- 局限：{md_text(item['limitations'])}",
                    f"- 链接：[{md_text(item['type'])}]({item['url']})（核验于 {item['checked_at']}）",
                    "",
                ]
            )
    else:
        lines.extend(["本阶段未使用非书籍补充来源。", ""])

    if data["phase"] == "candidate":
        lines.extend(
            [
                "## 请确认书单",
                "",
                "如需人工选书，请明确给出 1–3 个书籍 ID。",
                "",
            ]
        )
    return "\n".join(lines)


def sample_manifest() -> dict[str, Any]:
    def book(book_id: str, title: str, author: str, isbn13: str) -> dict[str, Any]:
        return {
            "id": book_id,
            "title": title,
            "authors": [author],
            "edition": "1st edition",
            "year": 2024,
            "publisher": "示例出版社",
            "languages": ["zh-CN"],
            "identifiers": {"isbn13": isbn13},
            "role": "core",
            "access_tier": "preview",
            "decision": "pending",
            "used_in_notes": False,
            "local_file": None,
            "selected_sections": [],
            "reliability_reason": "用于自测的可核验示例。",
            "relevance_reason": "覆盖测试主题。",
            "limitations": "仅为本地自测数据。",
            "evidence": [
                {
                    "kind": "publisher",
                    "url": f"https://publisher.example/{book_id}",
                    "checked_at": "2026-08-03",
                    "locator": "书目页",
                    "supports": "identity",
                },
                {
                    "kind": "preview",
                    "url": f"https://catalog.example.org/{book_id}",
                    "checked_at": "2026-08-03",
                    "locator": "可见预览",
                    "supports": "content",
                },
            ],
        }

    return {
        "schema_version": 2,
        "topic": "测试主题",
        "scope": "验证中文清单渲染",
        "learner_profile": {
            "level": "初学者",
            "goal": "验证脚本",
            "time_budget": "45 分钟",
            "example_style": "语言无关",
        },
        "phase": "candidate",
        "generated_at": "2026-08-03",
        "recommended_book_ids": ["B01", "B02", "B03"],
        "books": [
            book("B01", "示例一", "作者甲", "9780131103627"),
            book("B02", "示例二", "作者乙", "9780262033848"),
            book("B03", "示例三", "作者丙", "9780132350884"),
            book("B04", "示例四", "作者丁", "9780201633610"),
            book("B05", "示例五", "作者戊", "9780134685991"),
        ],
        "supplements": [],
    }


def self_test() -> None:
    data = sample_manifest()
    errors, warnings = validate_manifest(data)
    assert not errors, errors
    assert not warnings, warnings
    rendered = render_booklist(data)
    assert "测试主题" in rendered and "请确认书单" in rendered

    broken = json.loads(json.dumps(data, ensure_ascii=False))
    broken["books"][0]["identifiers"]["isbn13"] = "9780131103628"
    broken["books"][1]["id"] = "B01"
    broken["books"][2]["evidence"][1]["url"] = broken["books"][2]["evidence"][0]["url"]
    errors, _ = validate_manifest(broken)
    assert any("isbn13 校验失败" in error for error in errors)
    assert any("书籍 ID 重复" in error for error in errors)
    assert any("不同主机名" in error for error in errors)

    over_selected = json.loads(json.dumps(data, ensure_ascii=False))
    over_selected["phase"] = "approved"
    for book in over_selected["books"]:
        book["decision"] = "approved"
    errors, _ = validate_manifest(over_selected)
    assert any("只能选择 1–3 本书" in error for error in errors)
    assert any("必须有 1–3 本已下载" in error for error in errors)

    with tempfile.TemporaryDirectory() as temp_dir:
        run_dir = Path(temp_dir)
        materials = run_dir / "materials"
        materials.mkdir()
        local = json.loads(json.dumps(data, ensure_ascii=False))
        local["phase"] = "approved"
        for index, book in enumerate(local["books"]):
            book["decision"] = "approved" if index < 2 else "rejected"
        local["books"][1]["role"] = "supplementary"
        for index in (0, 1):
            book = local["books"][index]
            book["access_tier"] = "full_text"
            book["used_in_notes"] = True
            file_path = materials / f"{book['id']}.pdf"
            file_path.write_bytes(b"%PDF-1.4\n% self-test\n")
            book["local_file"] = {
                "path": f"materials/{book['id']}.pdf",
                "source_url": book["evidence"][0]["url"],
                "downloaded_at": "2026-08-03",
                "mime_type": "application/pdf",
                "sha256": file_sha256(file_path),
                "license": "自测文件",
            }
            book["selected_sections"] = [
                {
                    "id": f"{book['id']}-S01",
                    "title": "自测章节",
                    "pdf_start": 1,
                    "pdf_end": 1,
                    "printed_pages": "1",
                    "reason": "验证分块阅读清单。",
                }
            ]
        manifest_path = run_dir / "sources.json"
        errors, _ = validate_manifest(local, manifest_path)
        assert not errors, errors

        too_many_core = json.loads(json.dumps(local, ensure_ascii=False))
        too_many_core["books"][1]["role"] = "core"
        errors, _ = validate_manifest(too_many_core, manifest_path)
        assert any("恰好有一本用于正文的主教材" in error for error in errors)

        overlapping = json.loads(json.dumps(local, ensure_ascii=False))
        overlapping["books"][0]["selected_sections"].append(
            {
                "id": "B01-S02",
                "title": "重叠章节",
                "pdf_start": 1,
                "pdf_end": 2,
                "printed_pages": "1–2",
                "reason": "验证重叠检测。",
            }
        )
        errors, _ = validate_manifest(overlapping, manifest_path)
        assert any("页段重叠" in error for error in errors)

        local["phase"] = "complete"
        extracts = run_dir / "extracts"
        extracts.mkdir()
        (extracts / "B01-S01.pdf").write_bytes(b"%PDF-1.4\n% self-test\n")
        (extracts / "B02-S01.pdf").write_bytes(b"%PDF-1.4\n% self-test\n")
        valid_notes = (
            "# 测试笔记\n\n正文。\n\n## 来源\n\n"
            "- B01 — 示例一，[本地文件](materials/B01.pdf)。\n"
            "- B02 — 示例二，[本地文件](materials/B02.pdf)。\n"
        )
        (run_dir / "notes.md").write_text(valid_notes, encoding="utf-8")
        errors, _ = validate_manifest(local, manifest_path)
        assert not errors, errors

        (run_dir / "notes.md").write_text(
            valid_notes.replace("[本地文件](materials/B02.pdf)", "未链接本地文件"),
            encoding="utf-8",
        )
        errors, _ = validate_manifest(local, manifest_path)
        assert any("来源条目必须链接本地文件" in error for error in errors)
        (run_dir / "notes.md").write_text(valid_notes, encoding="utf-8")

        local["books"][0]["local_file"]["sha256"] = "0" * 64
        errors, _ = validate_manifest(local, manifest_path)
        assert any("sha256 与本地文件不一致" in error for error in errors)

        local["books"][0]["local_file"]["sha256"] = file_sha256(materials / "B01.pdf")
        (run_dir / "notes.md").write_text(
            "# 测试笔记\n\n正文。\n\n## 来源\n\n- B03 — 在线预览。\n",
            encoding="utf-8",
        )
        errors, _ = validate_manifest(local, manifest_path)
        assert any("未下载或未标记用于正文" in error for error in errors)

        (extracts / "B02-S01.pdf").unlink()
        errors, _ = validate_manifest(local, manifest_path)
        assert any("缺少裁剪文件: extracts/B02-S01.pdf" in error for error in errors)

    print("self-test: PASS")


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise ValueError(f"找不到清单: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON 解析失败（第 {exc.lineno} 行，第 {exc.colno} 列）: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise ValueError("清单根节点必须是对象")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", nargs="?", type=Path, help="sources.json 路径")
    parser.add_argument("--check", action="store_true", help="只校验，不写文件")
    parser.add_argument("--output", type=Path, help="校验通过后生成 booklist.md")
    parser.add_argument("--self-test", action="store_true", help="运行内置自测")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return 0
    if args.manifest is None:
        parser.error("必须提供 sources.json，或使用 --self-test")

    try:
        data = load_manifest(args.manifest)
    except ValueError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1

    errors, warnings = validate_manifest(data, args.manifest)
    for warning in warnings:
        print(f"警告: {warning}", file=sys.stderr)
    if errors:
        for error in errors:
            print(f"错误: {error}", file=sys.stderr)
        print(f"校验失败：{len(errors)} 个错误", file=sys.stderr)
        return 1

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(render_booklist(data), encoding="utf-8", newline="\n")
        print(f"校验通过，已生成: {args.output}")
    else:
        print("校验通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
