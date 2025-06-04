# `fabricatio-anki`

An extension of fabricatio, which brings up the capability of creating fully explainned anki deck package.

---

## 📦 Installation

This package is part of the `fabricatio` monorepo and can be installed as an optional dependency:

```bash
pip install fabricatio[anki]
```

Or install all components:

```bash
pip install fabricatio[full]
```

## 🔍 Overview

Provides essential tools for:

### Anki Deck Creation
This package enables the creation of fully explained Anki deck packages. It allows users to define card templates, add questions and answers, and organize them into decks. For example, you can create decks for different subjects or topics, and each card can have detailed explanations and additional information.

### Content Management
It offers features for managing the content of Anki decks. This includes adding media files such as images, audio, and video to cards, as well as categorizing and tagging cards for easy retrieval.

### Integration with Fabricatio
The package is designed to work seamlessly with the Fabricatio framework. It can leverage the capabilities of Fabricatio's agent framework to automate the deck creation process and integrate with other modules.

...



## 🧩 Key Features

### Template Customization
Users can customize the card templates according to their needs. This includes changing the layout, font, and color of the cards, as well as adding custom fields for additional information.

### Media Support
The package supports the addition of media files to cards. This enhances the learning experience by allowing users to include images, audio, and video in their Anki decks.

### Automation
It provides automation features for deck creation. For example, you can use scripts to generate cards based on a set of rules or data sources.

...


## 🔗 Dependencies

Core dependencies:

- `fabricatio-core` - Core interfaces and utilities
This dependency provides the fundamental building blocks for the Fabricatio framework. It includes interfaces for task management, event handling, and data models. The `fabricatio-anki` package uses these interfaces to interact with other modules in the Fabricatio ecosystem.
...

## 📄 License

MIT – see [LICENSE](LICENSE)

GitHub: [github.com/Whth/fabricatio](https://github.com/Whth/fabricatio)