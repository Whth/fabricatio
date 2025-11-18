# `fabricatio-typst`

[MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python Versions](https://img.shields.io/pypi/pyversions/fabricatio-typst)
[![PyPI Version](https://img.shields.io/pypi/v/fabricatio-typst)](https://pypi.org/project/fabricatio-typst/)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-typst/week)](https://pepy.tech/projects/fabricatio-typst)
[![PyPI Downloads](https://static.pepy.tech/badge/fabricatio-typst)](https://pepy.tech/projects/fabricatio-typst)
[![Bindings: PyO3](https://img.shields.io/badge/bindings-pyo3-green)](https://github.com/PyO3/pyo3)
[![Build Tool: uv + maturin](https://img.shields.io/badge/built%20with-uv%20%2B%20maturin-orange)](https://github.com/astral-sh/uv)

A Python library for generating, validating and converting academic content using Typst format.

## 📦 Installation

This package is part of the `fabricatio` monorepo and can be installed as an optional dependency:

```bash
pip install fabricatio[typst]
```

Or install all components:

```bash
pip install fabricatio[full]
```

## 🔍 Overview

Provides tools for:

- Generating academic article proposals and outlines
  This feature uses natural language processing and machine learning techniques to generate well - structured academic
  article proposals and outlines. It analyzes the research topic and relevant literature to come up with a comprehensive
  proposal that includes a proposed title, research problem, technical approaches, and an outline of the article's
  structure. For example, given a research topic on "The impact of climate change on coastal ecosystems", it can
  generate a proposal with a clear statement of the problem, possible methods for data collection and analysis, and an
  outline of the main sections of the article.
- Writing full articles using RAG (Retrieval-Augmented Generation)
  The RAG - based article writing feature combines retrieval and generation capabilities. It retrieves relevant
  information from a knowledge base, such as academic papers, reports, and datasets, and uses this information to
  generate high - quality article content. For example, it can search for existing research on a particular topic,
  extract relevant facts and figures, and incorporate them into the article while maintaining a coherent narrative.
- Converting LaTeX math to Typst format
  This feature is designed to help users convert LaTeX math expressions to the Typst format. It parses the LaTeX math
  code and translates it into the equivalent Typst syntax. This is useful for users who are migrating from LaTeX to
  Typst or want to use Typst for academic writing with math content. For example, it can convert a LaTeX equation like "
  \(E = mc^2\)" to the Typst format.
- Managing bibliographies and citations
  The bibliography and citation management feature allows users to easily manage references in their academic articles.
  It can import bibliographic data from various sources, such as BibTeX files, and generate formatted citations and
  bibliographies in the desired style. For example, it can generate APA, MLA, or Chicago style citations and
  bibliographies based on the user's requirements.
- Validating and improving article structure
  This feature checks the structure of the academic article for coherence and logical flow. It can identify issues such
  as missing sections, inconsistent headings, or weak transitions between paragraphs. It then provides suggestions for
  improving the structure, such as adding or reordering sections, and strengthening the connections between different
  parts of the article.

Built on top of Fabricatio's agent framework with support for asynchronous execution.

## 🧩 Usage Example

```python
from fabricatio_typst.actions.article import GenerateArticleProposal
The `GenerateArticleProposal` class is responsible for generating article proposals. It takes a research topic or article briefing as input and uses a set of algorithms and templates to generate a detailed proposal. It interacts with other components of the library, such as the data models and retrieval mechanisms, to ensure the proposal is comprehensive and relevant.
from fabricatio_typst.models.article_proposal import ArticleProposal
The `ArticleProposal` model represents the generated article proposal. It contains attributes such as the title, research problem, technical approaches, and outline of the article. It provides methods for accessing and manipulating these attributes, as well as for validating the proposal's structure.


async def create_proposal():
    # Create a proposal based on a research topic
    proposer = GenerateArticleProposal()
    This line creates an instance of the `GenerateArticleProposal` class. Once created, the instance can be used to generate an article proposal by calling its `_execute` method with an appropriate article briefing.
    proposal: ArticleProposal = await proposer._execute(
    The `_execute` method of the `GenerateArticleProposal` class takes an article briefing as input and generates an `ArticleProposal` object. It performs a series of operations, such as retrieving relevant information, analyzing the topic, and applying templates, to generate the proposal.
        article_briefing="Research topic: The impact of climate change on coastal ecosystems"
    )

    print(f"Proposed title: {proposal.title}")
    print(f"Research problem: {proposal.focused_problem}")
    print(f"Technical approaches: {proposal.technical_approaches}")
```

## 📁 Structure

```
fabricatio-typst/
├── actions/          - Article generation workflows
│   ├── article.py    - Core article generation actions
│   └── article_rag.py- RAG-based content creation
├── capabilities/     - Citation and reference management
│   └── citation_rag.py
├── models/           - Data models for academic content
│   ├── article_base.py - Base classes for article components
│   ├── article_outline.py - Outline structure definitions
│   ├── article_proposal.py - Research proposal model
│   └── article_essence.py - Semantic fingerprint of papers
├── workflows/        - Predefined content generation pipelines
└── rust.pyi          - Rust extension interfaces
```

## 🔗 Dependencies

Built on top of other Fabricatio modules:

- `fabricatio-core` - Core interfaces and utilities
- `fabricatio-rag` - Retrieval-Augmented Generation capabilities
- `fabricatio-capabilities` - Base capability patterns

Includes Rust extensions for:

- TeX-to-Typst conversion
- Bibliography management
- Language detection
- Text processing

## 📄 License

MIT – see [LICENSE](../../LICENSE)

