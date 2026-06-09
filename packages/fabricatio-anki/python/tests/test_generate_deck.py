"""Tests for the Anki deck generation capabilities."""

from typing import List, Optional

import orjson
import pytest
from fabricatio_anki.capabilities.generate_deck import GenerateDeck
from fabricatio_anki.models.deck import Deck, Model, ModelMetaData
from fabricatio_anki.models.template import Side, Template
from fabricatio_mock.models.mock_role import LLMTestRole
from fabricatio_mock.models.mock_router import return_router_usage
from fabricatio_mock.utils import code_block, generic_block, install_router_usage


def side_factory(layout: str = "Default layout", js: str = "", css: str = "") -> Side:
    """Create Side object with test data."""
    return Side(layout=layout, js=js, css=css)


def template_factory(name: str, front_layout: str = "Front", back_layout: str = "Back") -> Template:
    """Create Template object with test data."""
    return Template(name=name, front=side_factory(front_layout), back=side_factory(back_layout))


def model_factory(name: str, fields: List[str], templates: Optional[List[Template]] = None) -> Model:
    """Create Model object with test data."""
    if templates is None:
        templates = [template_factory(f"{name}_template")]
    return Model(name=name, fields=fields, templates=templates)


def metadata_factory(name: str, description: str, author: str = "Test Author") -> ModelMetaData:
    """Create ModelMetaData object with test data."""
    return ModelMetaData(name=name, description=description, author=author)


def deck_factory(
    name: str,
    description: str,
    models: Optional[List[Model]] = None,
    author: str = "Test Author",
) -> Deck:
    """Create Deck object with test data."""
    if models is None:
        models = [model_factory("test_model", ["Front", "Back"])]
    return Deck(name=name, description=description, models=models, author=author)


def _json_array(items: List[str]) -> str:
    """Serialize a list to a JSON code block for alist_v."""
    return code_block(orjson.dumps(items).decode(), "json")


def _json_obj(data: dict) -> str:
    """Serialize a dict to a JSON code block for propose."""
    return code_block(orjson.dumps(data).decode(), "json")


def _build_deck_responses(
    metadata_name: str,
    metadata_desc: str,
    model_reqs: List[str],
    template_reqs: List[str],
    model_name: str,
    template_name: str,
    front_html: str,
    back_html: str,
) -> list[str]:
    """Build the full LLM response chain for generate_deck.

    All responses are passed in a single return_router_usage call to avoid
    padding items being consumed between real responses (DummyModel is LIFO).

    Response consumption order:
    1. propose → metadata JSON (code block)
    2. alist_v → model requirements (code block JSON array)
    3. generate_model → ageneric_string → model name (generic block)
    4. generate_model → alist_v → template requirements (code block JSON array)
    5. generate_template → ageneric_string → template name (generic block)
    6. generate_template → acode_string → front HTML (python code block)
    7. generate_template → acode_string → back HTML (python code block)
    """
    return return_router_usage(
        _json_obj({"name": metadata_name, "description": metadata_desc}),
        _json_array(model_reqs),
        generic_block(model_name),
        _json_array(template_reqs),
        generic_block(template_name),
        code_block(front_html, "python"),
        code_block(back_html, "python"),
    )


class GenerateDeckRole(LLMTestRole, GenerateDeck):
    """A class that tests the deck generation methods."""


@pytest.fixture
def role() -> GenerateDeckRole:
    """Create a GenerateDeckRole instance for testing."""
    return GenerateDeckRole()


@pytest.mark.parametrize(
    ("metadata_ret", "model_reqs_ret", "template_reqs_ret", "fields", "requirement", "expected_deck_name"),
    [
        (
            metadata_factory("Spanish Vocabulary", "A deck for learning Spanish words"),
            ["Basic vocabulary"],
            ["Word to translation"],
            ["Spanish", "English", "Example"],
            "Create a Spanish learning deck",
            "Spanish Vocabulary",
        ),
        (
            metadata_factory("Math Formulas", "Mathematical equations and formulas"),
            ["Algebra formulas"],
            ["Formula to name"],
            ["Formula", "Name", "Application"],
            "Create a math formulas deck",
            "Math Formulas",
        ),
        (
            metadata_factory("History Facts", "Important historical events and dates"),
            ["Ancient history"],
            ["Event to date"],
            ["Event", "Date", "Description"],
            "Create a history facts deck",
            "History Facts",
        ),
    ],
)
@pytest.mark.asyncio
async def test_generate_deck_success(
    role: GenerateDeckRole,
    metadata_ret: ModelMetaData,
    model_reqs_ret: List[str],
    template_reqs_ret: List[str],
    fields: List[str],
    requirement: str,
    expected_deck_name: str,
) -> None:
    """Test the generate_deck method with successful cases."""
    responses = _build_deck_responses(
        metadata_name=metadata_ret.name,
        metadata_desc=metadata_ret.description,
        model_reqs=model_reqs_ret,
        template_reqs=template_reqs_ret,
        model_name="test_model",
        template_name="test_template",
        front_html=f"<div>{{ {fields[0]} }} Front</div>",
        back_html=f"<div>{{ {fields[0]} }} Back</div>",
    )

    with install_router_usage(*responses):
        result = await role.generate_deck(requirement, fields)

        assert result is not None
        assert result.name == expected_deck_name
        assert result.description == metadata_ret.description
        assert len(result.models) >= 1


@pytest.mark.parametrize(
    ("requirement", "fields", "expected_name", "template_names"),
    [
        (
            "Basic vocabulary",
            ["Word", "Definition"],
            "basic_vocabulary_model",
            ["template_0"],
        ),
        (
            "Advanced grammar",
            ["Rule", "Example", "Exception"],
            "advanced_grammar_model",
            ["grammar_template"],
        ),
    ],
)
@pytest.mark.asyncio
async def test_generate_model_single_requirement(
    role: GenerateDeckRole,
    requirement: str,
    fields: List[str],
    expected_name: str,
    template_names: List[str],
) -> None:
    """Test the generate_model method with single requirement string."""
    front_html = f"<div>{{ {fields[0]} }}</div>"
    back_html = f"<div>{{ {fields[1] if len(fields) > 1 else fields[0]} }}</div>"

    responses = return_router_usage(
        generic_block(expected_name),
        _json_array(template_names),
        generic_block(template_names[0]),
        code_block(front_html, "python"),
        code_block(back_html, "python"),
    )

    with install_router_usage(*responses):
        result = await role.generate_model(fields, requirement)

        assert result is not None
        assert result.name == expected_name
        assert result.fields == fields
        assert len(result.templates) == len(template_names)


@pytest.mark.parametrize(
    ("requirements", "fields", "expected_count", "model_names"),
    [
        (
            ["Basic vocabulary"],
            ["Word", "Definition"],
            1,
            ["basic_vocabulary"],
        ),
        (
            ["Grammar rules"],
            ["Rule", "Example"],
            1,
            ["grammar_rules"],
        ),
    ],
)
@pytest.mark.asyncio
async def test_generate_model_multiple_requirements(
    role: GenerateDeckRole,
    requirements: List[str],
    fields: List[str],
    expected_count: int,
    model_names: List[str],
) -> None:
    """Test the generate_model method with multiple requirements."""
    template_reqs = ["Template 1", "Template 2"]
    all_responses = [
        # ageneric_string batch (1 per requirement)
        *[generic_block(n) for n in model_names],
        # alist_v batch (1 per requirement)
        *[code_block(orjson.dumps(template_reqs).decode(), "json") for _ in requirements],
        # gather of generate_template calls (3 per requirement: name + front + back)
        *[
            item
            for i in range(len(requirements))
            for item in [
                generic_block(f"template_{i}"),
                code_block(f"<div>Front Content {i}</div>", "python"),
                code_block(f"<div>Back Content {i}</div>", "python"),
            ]
        ],
    ]

    responses = return_router_usage(*all_responses)

    with install_router_usage(*responses):
        result = await role.generate_model(fields, requirements)

        assert result is not None
        assert len(result) == expected_count
        for i, model in enumerate(result):
            assert model.name == model_names[i]
            assert model.fields == fields


@pytest.mark.parametrize(
    ("requirement", "fields", "expected_name"),
    [
        (
            "Word recognition",
            ["Word", "Definition"],
            "word_recognition_template",
        ),
        (
            "Math problem solving",
            ["Problem", "Solution", "Steps"],
            "math_problem_solving_template",
        ),
    ],
)
@pytest.mark.asyncio
async def test_generate_template_single_requirement(
    role: GenerateDeckRole,
    requirement: str,
    fields: List[str],
    expected_name: str,
) -> None:
    """Test the generate_template method with single requirement."""
    front_html = f"<div>{{ {fields[0]} }}</div>"
    back_html = f"<div>{{ {fields[1] if len(fields) > 1 else fields[0]} }}</div>"

    responses = return_router_usage(
        generic_block(expected_name),
        code_block(front_html, "python"),
        code_block(back_html, "python"),
    )

    with install_router_usage(*responses):
        result = await role.generate_template(fields, requirement)

        assert result is not None
        assert result.name == expected_name
        assert result.front.layout == front_html
        assert result.back.layout == back_html


@pytest.mark.parametrize(
    ("requirements", "fields", "expected_count"),
    [
        (
            ["Basic template", "Advanced template"],
            ["Front", "Back"],
            2,
        ),
        (
            ["Word cards", "Definition cards", "Example cards"],
            ["Word", "Definition", "Example"],
            3,
        ),
    ],
)
@pytest.mark.asyncio
async def test_generate_template_multiple_requirements(
    role: GenerateDeckRole,
    requirements: List[str],
    fields: List[str],
    expected_count: int,
) -> None:
    """Test the generate_template method with multiple requirements."""
    template_names = [f"template_{i}" for i in range(len(requirements))]
    front_html_contents = [f"<div>Front Content {i}</div>" for i in range(len(requirements))]
    back_html_contents = [f"<div>Back Content {i}</div>" for i in range(len(requirements))]

    all_responses = [
        # ageneric_string batch (1 per requirement for template names)
        *[generic_block(n) for n in template_names],
        # acode_string batch for fronts (1 per requirement)
        *[code_block(h, "python") for h in front_html_contents],
        # acode_string batch for backs (1 per requirement)
        *[code_block(h, "python") for h in back_html_contents],
    ]

    responses = return_router_usage(*all_responses)

    with install_router_usage(*responses):
        result = await role.generate_template(fields, requirements)

        assert result is not None
        assert len(result) == expected_count
        for template in result:
            assert template.name in template_names
            assert template.front is not None
            assert template.back is not None


@pytest.mark.parametrize(
    ("requirement", "fields", "expected_html_content"),
    [
        (
            "Show word on front",
            ["Word", "Definition"],
            "<div>{{Word}}</div>",
        ),
        (
            "Display math problem",
            ["Problem", "Solution"],
            "<div class='problem'>{{Problem}}</div>",
        ),
    ],
)
@pytest.mark.asyncio
async def test_generate_front_side(
    role: GenerateDeckRole,
    requirement: str,
    fields: List[str],
    expected_html_content: str,
) -> None:
    """Test the generate_front_side method."""
    responses = return_router_usage(code_block(expected_html_content, "python"))

    with install_router_usage(*responses):
        result = await role.generate_front_side(fields, requirement)

        assert result is not None
        assert result.layout == expected_html_content


@pytest.mark.parametrize(
    ("requirement", "fields", "expected_html_content"),
    [
        (
            "Show definition on back",
            ["Word", "Definition"],
            "<div>{{Definition}}</div>",
        ),
        (
            "Display solution steps",
            ["Problem", "Solution", "Steps"],
            "<div class='solution'>{{Solution}}<br>{{Steps}}</div>",
        ),
    ],
)
@pytest.mark.asyncio
async def test_generate_back_side(
    role: GenerateDeckRole,
    requirement: str,
    fields: List[str],
    expected_html_content: str,
) -> None:
    """Test the generate_back_side method."""
    responses = return_router_usage(code_block(expected_html_content, "python"))

    with install_router_usage(*responses):
        result = await role.generate_back_side(fields, requirement)

        assert result is not None
        assert result.layout == expected_html_content


@pytest.mark.parametrize(
    ("fields", "requirement"),
    [
        (["Front", "Back"], "Empty deck test"),
        (["Field1", "Field2", "Field3"], "Three-field test"),
    ],
)
@pytest.mark.asyncio
async def test_generate_deck_empty_model_requirements(
    role: GenerateDeckRole,
    fields: List[str],
    requirement: str,
) -> None:
    """Test generate_deck returns None when model requirements are empty."""
    metadata = metadata_factory("Test Deck", "Test description")

    responses = return_router_usage(
        _json_obj({"name": metadata.name, "description": metadata.description}),
        code_block("[]", "json"),
    )

    with install_router_usage(*responses):
        result = await role.generate_deck(requirement, fields)

        assert result is None


@pytest.mark.asyncio
async def test_generate_template_none_inputs(role: GenerateDeckRole) -> None:
    """Test generate_template with inputs that may cause None returns."""
    fields = ["Word", "Definition"]
    requirement = "test_template"

    responses = return_router_usage(
        generic_block("test_template"),
        code_block("", "python"),
        code_block("", "python"),
    )

    with install_router_usage(*responses):
        result = await role.generate_template(fields, requirement)

        if result is not None:
            assert result.name == "test_template"


@pytest.mark.parametrize(
    ("fields", "requirement"),
    [
        (["Front", "Back"], "Deck with None metadata"),
        (["Field1", "Field2"], "Another deck test"),
    ],
)
@pytest.mark.asyncio
async def test_generate_deck_none_metadata(
    role: GenerateDeckRole,
    fields: List[str],
    requirement: str,
) -> None:
    """Test generate_deck when metadata propose returns None."""
    responses = return_router_usage(
        generic_block("invalid json that cannot be parsed as ModelMetaData"),
        generic_block("invalid json again"),
        generic_block("invalid json third attempt"),
        _json_array(["Template requirement 1"]),
    )

    with install_router_usage(*responses):
        result = await role.generate_deck(requirement, fields)

        assert result is None


@pytest.mark.parametrize(
    ("requirement", "fields", "expected_deck_name"),
    [
        (
            "Build a vocabulary deck",
            ["Word", "Definition"],
            "vocabulary_deck",
        ),
        (
            "Create a science deck",
            ["Question", "Answer"],
            "science_deck",
        ),
    ],
)
@pytest.mark.asyncio
async def test_generate_deck_with_router(
    role: GenerateDeckRole,
    requirement: str,
    fields: List[str],
    expected_deck_name: str,
) -> None:
    """Test generate_deck method with router mocking following test_diff.py pattern."""
    responses = _build_deck_responses(
        metadata_name=expected_deck_name,
        metadata_desc=f"Description for {expected_deck_name}",
        model_reqs=["Model requirement 1"],
        template_reqs=["Template requirement 1"],
        model_name="test_model",
        template_name="test_template",
        front_html=f"<div>{{ {fields[0]} }}</div>",
        back_html=f"<div>{{ {fields[1]} }}</div>",
    )

    with install_router_usage(*responses):
        result = await role.generate_deck(requirement, fields)

        assert result is not None
        assert result.name == expected_deck_name
        assert result.description == f"Description for {expected_deck_name}"
        assert len(result.models) >= 1
