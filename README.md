<p align="center">
  <img src="assets/hero.png" alt="从可靠书籍中提取相关章节并生成学习笔记" width="100%">
</p>

<h1 align="center">build-book-study-notes</h1>

<p align="center">
  <strong>先问清你要学到什么程度，再真正查书、下载、提取相关页段，最后写成中文学习笔记。</strong>
</p>

<p align="center">
  <a href="https://learn.chatgpt.com/docs/build-skills"><img src="https://img.shields.io/badge/Codex-Skill-111827" alt="Codex Skill"></a>
  <img src="https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white" alt="Python 3.9 及以上">
  <img src="https://img.shields.io/badge/dependencies-stdlib%20only-0F766E" alt="仅使用 Python 标准库">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-D97706" alt="MIT 许可证"></a>
  <a href="https://github.com/guan695/build-book-study-notes/actions/workflows/quality.yml"><img src="https://github.com/guan695/build-book-study-notes/actions/workflows/quality.yml/badge.svg" alt="Quality checks"></a>
</p>

> **English summary:** `build-book-study-notes` is a Codex Skill for evidence-grounded learning. It asks for a learning brief, verifies real books through authoritative sources, downloads only lawful full texts, extracts the relevant PDF pages, and writes Chinese study notes with page-level provenance. The repository includes a dependency-free manifest validator and self-test.

## 解决什么问题

这个 Skill 不把几百页 PDF 一次性塞进上下文，也不根据模型记忆假装读过书。它先把相关原书页面裁成若干小 PDF，保留图片、公式和版式，再让 AI 分批阅读。

它把学习笔记任务拆成四个可以检查的环节：

- 先确认基础、可检验的学习目标、时间安排和讲解偏好；
- 只使用经过核验、能够合法下载的书籍全文；
- 用 `sources.json` 记录书目、哈希、用途和页段，并用脚本校验；
- 让每个模块的笔记链接到实际阅读过的原书和 PDF 页段。

仓库不包含任何原书 PDF。使用者需要自行从合法公开地址下载全文，原书只保存在本地学习目录中。

## 工作流程

```mermaid
flowchart LR
    A["你提出学习主题"] --> B["AI 询问基础、目标、时间和偏好"]
    B --> C["确认一次完整模块路线"]
    C --> D["逐个模块查书并裁剪小 PDF"]
    D --> E["生成当前模块笔记"]
    E -->|"还有模块"| D
    E -->|"全部完成"| F["统一交付"]
```

一个主题会按先备依赖和可检验的学习结果拆成必要数量的模块。用户只需确认一次完整路线，AI 会逐个模块完成，中间不再反复询问。每次上下文只处理当前模块，相关页段不设总数上限；“不限时间”表示不压缩讲解深度，而不是生成更短的概览。

## 使用方法

安装后，在任意学习目录输入：

```text
$build-book-study-notes 我想学习卡尔曼滤波。
```

Skill 不会直接套用默认设置，而会先询问：

1. 你现在掌握哪些先备知识？
2. 学完后希望能解释、推导、独立解题、用于项目，还是阅读论文？
3. 准备投入多少时间或希望采用什么节奏？
4. 偏好直观解释、公式、代码、案例，还是它们的组合？

主题较宽时，它会先给出完整模块路线。你确认一次后，它会按顺序完成全部模块；只有遇到确实需要你决定的问题才会暂停。

## 生成内容

```text
notes/<日期>-<总主题>/
├── sources.json
├── materials/
├── extracts/
└── notes/
    ├── 01-<知识点>.md
    ├── 02-<知识点>.md
    └── ...
```

按编号依次阅读 `notes/` 中的模块笔记即可。除非你明确要求，不生成书单报告或证据卡。

## 笔记质量要求

- 每个模块对应一个可以检验的学习结果；范围过大就继续拆分，不限制模块数。
- 数学或技术主题必须讲清假设、定义、符号、关系和关键推导，并提供可独立复算的代表性例子。
- 操作类主题必须说明原理、完整步骤、选择依据和排错方法；概念类主题必须讲清观点、证据和关系。
- 练习与答案用于检查用户约定的能力，不以固定题数凑格式。
- 所有数学变量、符号和公式使用 Markdown 可渲染的 LaTeX：行内 `$...$`，独立公式 `$$...$$`，不用裸 Unicode 数学符号。
- 关键结论必须能定位到本地小 PDF 中的具体页段。
- 最终只附简短来源，不把检索过程写进笔记。

## 安装

在 Codex 中调用 `$skill-installer`，并输入：

```text
从 https://github.com/guan695/build-book-study-notes 安装仓库根目录的 Skill，名称使用 build-book-study-notes。
```

也可以直接克隆。

Windows PowerShell：

```powershell
git clone https://github.com/guan695/build-book-study-notes.git "$env:USERPROFILE\.agents\skills\build-book-study-notes"
```

macOS / Linux：

```bash
git clone https://github.com/guan695/build-book-study-notes.git ~/.agents/skills/build-book-study-notes
```

安装后如果没有立即显示，请重启 Codex。

## 开发与校验

本项目只使用 Python 标准库，不需要安装第三方依赖。提交修改前运行：

```powershell
python -X utf8 scripts/book_manifest.py --self-test
python -X utf8 -m py_compile scripts/book_manifest.py
```

更完整的贡献约定见 [`CONTRIBUTING.md`](CONTRIBUTING.md)，变更记录见 [`CHANGELOG.md`](CHANGELOG.md)。

## 来源底线

- 必须实时联网核验真实书目。
- 实际使用的书必须下载合法全文到本地。
- 不绕过付费墙，不使用盗版或影子图书馆。
- 搜索摘要、零售页和评论不能支撑笔记正文。
- 找不到合法全文时停止，不伪装成已经读过书。

## 本地校验

```powershell
python -X utf8 scripts/book_manifest.py --self-test
python -X utf8 scripts/book_manifest.py <sources.json> --check
```

## 许可证

[MIT](LICENSE)
