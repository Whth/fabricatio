# `fabricatio-typst`

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
- Writing full articles using RAG (Retrieval-Augmented Generation)
- Converting LaTeX math to Typst format
- Managing bibliographies and citations
- Validating and improving article structure

Built on top of Fabricatio's agent framework with support for asynchronous execution.

## 🧩 Usage Example

```python
from fabricatio_typst.actions.article import GenerateArticleProposal
from fabricatio_typst.models.article_proposal import ArticleProposal


async def create_proposal():
    # Create a proposal based on a research topic
    proposer = GenerateArticleProposal()
    proposal: ArticleProposal = await proposer._execute(
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

MIT – see [LICENSE](LICENSE)

GitHub: [github.com/Whth/fabricatio](https://github.com/Whth/fabricatio)