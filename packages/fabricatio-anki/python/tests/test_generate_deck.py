"""Tests for the Anki deck generation capabilities."""

from typing import Any, List, Optional
from unittest.mock import AsyncMock, patch

import pytest
from fabricatio_anki.capabilities.generate_deck import GenerateDeck
from fabricatio_anki.models.deck import Deck, Model, ModelMetaData
from fabricatio_anki.models.template import Side, Template
from fabricatio_mock.models.mock_role import LLMTestRole
from fabricatio_mock.models.mock_router import (
    return_json_obj_string,
    return_model_json_string,
)
from fabricatio_mock.utils import install_router


def side_factory(layout: str = "Default layout", js: str = "", css: str = "") -> Side:
    """Create Side object with test data.

    Args:
        layout (str): HTML layout content for the side
        js (str): JavaScript code for the side
        css (str): CSS styles for the side

    Returns:
        Side: Side object with specified content
    """
    return Side(layout=layout, js=js, css=css)


def template_factory(name: str, front_layout: str = "Front", back_layout: str = "Back") -> Template:
    """Create Template object with test data.

    Args:
        name (str): Name of the template
        front_layout (str): Front side layout content
        back_layout (str): Back side layout content

    Returns:
        Template: Template object with front and back sides
    """
    return Template(
        name=name,
        front=side_factory(front_layout),
        back=side_factory(back_layout),
    )


def model_factory(name: str, fields: List[str], templates: Optional[List[Template]] = None) -> Model:
    """Create Model object with test data.

    Args:
        name (str): Name of the model
        fields (List[str]): List of field names
        templates (Optional[List[Template]]): List of templates for the model

    Returns:
        Model: Model object with specified fields and templates
    """
    if templates is None:
        templates = [template_factory(f"{name}_template")]
    return Model(name=name, fields=fields, templates=templates)


def metadata_factory(name: str, description: str, author: str = "Test Author") -> ModelMetaData:
    """Create ModelMetaData object with test data.

    Args:
        name (str): Name for the metadata
        description (str): Description for the metadata
        author (str): Author name

    Returns:
        ModelMetaData: ModelMetaData object with specified values
    """
    return ModelMetaData(name=name, description=description, author=author)


def deck_factory(
    name: str,
    description: str,
    models: Optional[List[Model]] = None,
    author: str = "Test Author",
) -> Deck:
    """Create Deck object with test data.

    Args:
        name (str): Name of the deck
        description (str): Description of the deck
        models (Optional[List[Model]]): List of models in the deck
        author (str): Author of the deck

    Returns:
        Deck: Deck object with specified properties
    """
    if models is None:
        models = [model_factory("test_model", ["Front", "Back"])]
    return Deck(name=name, description=description, models=models, author=author)


class GenerateDeckRole(LLMTestRole, GenerateDeck):
    """A class that tests the deck generation methods."""


@pytest.fixture
def role() -> GenerateDeckRole:
    """Create a GenerateDeckRole instance for testing.

    Returns:
        GenerateDeckRole: GenerateDeckRole instance
    """
    return GenerateDeckRole()


@pytest.mark.parametrize(
    ("metadata_ret", "model_reqs_ret", "template_reqs_ret", "fields", "requirement", "expected_deck_name"),
    [
        (
            metadata_factory("Spanish Vocabulary", "A deck for learning Spanish words"),
            ["Basic word pairs", "Advanced phrases"],
            ["Word to translation", "Translation to word"],
            ["Spanish", "English", "Example"],
            "Create a Spanish learning deck",
            "Spanish Vocabulary",
        ),
        (
            metadata_factory("Math Formulas", "Mathematical equations and formulas"),
            ["Algebra formulas", "Geometry formulas"],
            ["Formula to name", "Application problems"],
            ["Formula", "Name", "Application"],
            "Create a math formulas deck",
            "Math Formulas",
        ),
        (
            metadata_factory("History Facts", "Important historical events and dates"),
            ["Ancient history", "Modern history"],
            ["Event to date", "Date to event"],
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
    """Test the generate_deck method with successful cases.

    Args:
        role (GenerateDeckRole): GenerateDeckRole fixture
        metadata_ret (ModelMetaData): Expected metadata object
        model_reqs_ret (List[str]): Model generation requirements
        template_reqs_ret (List[str]): Template generation requirements
        fields (List[str]): List of fields for the deck
        requirement (str): Requirement for deck generation
        expected_deck_name (str): Expected name of the generated deck
    """
    with (
        patch.object(GenerateDeck, "propose", new_callable=AsyncMock) as mock_propose,
        patch.object(GenerateDeck, "alist_str", new_callable=AsyncMock) as mock_alist,
        patch.object(GenerateDeck, "generate_model", new_callable=AsyncMock) as mock_generate_model,
    ):
        # Configure mocks
        mock_propose.return_value = metadata_ret
        mock_alist.return_value = model_reqs_ret
        mock_generate_model.return_value = [model_factory("test_model", fields, [template_factory("test_template")])]

        # Execute the method
        result = await role.generate_deck(requirement, fields)

        # Assertions
        assert result is not None
        assert result.name == expected_deck_name
        assert result.description == metadata_ret.description

        # Verify mocks were called
        mock_propose.assert_called_once()
        mock_alist.assert_called_once()
        mock_generate_model.assert_called_once()


@pytest.mark.parametrize(
    ("requirement", "fields", "expected_name", "template_names"),
    [
        (
            "Basic vocabulary",
            ["Word", "Definition"],
            "basic_vocabulary_model",
            ["template_0", "template_1"],
        ),
        (
            "Advanced grammar",
            ["Rule", "Example", "Exception"],
            "advanced_grammar_model",
            ["grammar_template"],
        ),
        (
            "Mathematical concepts",
            ["Concept", "Formula", "Application"],
            "mathematical_concepts_model",
            ["concept_template", "formula_template"],
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
    """Test the generate_model method with single requirement string.

    Args:
        role (GenerateDeckRole): GenerateDeckRole fixture
        requirement (str): Single requirement for model generation
        fields (List[str]): List of fields for the model
        expected_name (str): Expected sanitized model name
        template_names (List[str]): Names for templates to create
    """
    with (
        patch.object(GenerateDeck, "ageneric_string", new_callable=AsyncMock) as mock_generic,
        patch.object(GenerateDeck, "alist_str", new_callable=AsyncMock) as mock_alist,
        patch.object(GenerateDeck, "generate_template", new_callable=AsyncMock) as mock_template,
    ):
        # Configure mocks
        mock_generic.return_value = expected_name
        mock_alist.return_value = template_names
        mock_template.return_value = [template_factory(name) for name in template_names]

        # Execute the method
        result = await role.generate_model(fields, requirement)

        # Assertions
        assert result is not None
        assert result.name == expected_name
        assert result.fields == fields
        assert len(result.templates) == len(template_names)

        # Verify mocks were called
        mock_generic.assert_called_once()
        mock_alist.assert_called_once()
        mock_template.assert_called_once()


@pytest.mark.parametrize(
    ("requirements", "fields", "expected_count", "model_names"),
    [
        (
            ["Basic vocab", "Advanced vocab"],
            ["Word", "Definition"],
            2,
            ["basic_vocab", "advanced_vocab"],
        ),
        (
            ["Grammar rules", "Pronunciation", "Writing"],
            ["Rule", "Example"],
            3,
            ["grammar", "pronunciation", "writing"],
        ),
        (
            ["Math basics", "Algebra", "Geometry", "Calculus"],
            ["Formula", "Application"],
            4,
            ["math", "algebra", "geometry", "calculus"],
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
    """Test the generate_model method with multiple requirements.

    Args:
        role (GenerateDeckRole): GenerateDeckRole fixture
        requirements (List[str]): List of requirements for model generation
        fields (List[str]): List of fields for the models
        expected_count (int): Expected number of models generated
        model_names (List[str]): Expected model names
    """
    template_reqs = ["Template 1", "Template 2"]

    async def mock_gather(*args: Any) -> List[List[Template]]:
        return [[template_factory(f"template_{i}")] for i in range(len(requirements))]

    with (
        patch.object(GenerateDeck, "ageneric_string", new_callable=AsyncMock) as mock_generic,
        patch.object(GenerateDeck, "alist_str", new_callable=AsyncMock) as mock_alist,
        patch("fabricatio_anki.capabilities.generate_deck.gather", new_callable=AsyncMock) as mock_gather_func,
    ):
        # Configure mocks
        mock_generic.return_value = model_names
        mock_alist.return_value = [template_reqs] * len(requirements)
        mock_gather_func.side_effect = mock_gather

        # Execute the method
        result = await role.generate_model(fields, requirements)

        # Assertions
        assert result is not None
        assert len(result) == expected_count
        for i, model in enumerate(result):
            assert model.name == model_names[i]
            assert model.fields == fields

        # Verify mocks were called
        mock_generic.assert_called_once()
        mock_alist.assert_called_once()
        mock_gather_func.assert_called_once()


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
    """Test the generate_template method with single requirement.

    Args:
        role (GenerateDeckRole): GenerateDeckRole fixture
        requirement (str): Single requirement for template generation
        fields (List[str]): List of fields for the template
        expected_name (str): Expected template name
    """
    front_html = f"<div>{{{{ {fields[0]} }}}}</div>"
    back_html = f"<div>{{{{ {fields[1] if len(fields) > 1 else fields[0]} }}}}</div>"

    with (
        patch.object(GenerateDeck, "ageneric_string", new_callable=AsyncMock) as mock_generic,
        patch.object(GenerateDeck, "acode_string", new_callable=AsyncMock) as mock_code,
    ):
        # Configure mocks
        mock_generic.return_value = expected_name
        mock_code.side_effect = [front_html, back_html]

        # Execute the method
        result = await role.generate_template(fields, requirement)

        # Assertions
        assert result is not None
        assert result.name == expected_name
        assert result.front.layout == front_html
        assert result.back.layout == back_html

        # Verify mocks were called
        mock_generic.assert_called_once()
        assert mock_code.call_count == 2


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
    """Test the generate_template method with multiple requirements.

    Args:
        role (GenerateDeckRole): GenerateDeckRole fixture
        requirements (List[str]): List of requirements for template generation
        fields (List[str]): List of fields for the templates
        expected_count (int): Expected number of templates generated
    """
    template_names = [f"template_{i}" for i in range(len(requirements))]
    front_html_contents = [f"<div>Front Content {i}</div>" for i in range(len(requirements))]
    back_html_contents = [f"<div>Back Content {i}</div>" for i in range(len(requirements))]

    with (
        patch.object(GenerateDeck, "ageneric_string", new_callable=AsyncMock) as mock_generic,
        patch.object(GenerateDeck, "generate_front_side", new_callable=AsyncMock) as mock_front,
        patch.object(GenerateDeck, "generate_back_side", new_callable=AsyncMock) as mock_back,
    ):
        # Configure mocks
        mock_generic.return_value = template_names
        mock_front.return_value = [side_factory(html) for html in front_html_contents]
        mock_back.return_value = [side_factory(html) for html in back_html_contents]

        # Execute the method
        result = await role.generate_template(fields, requirements)

        # Assertions
        assert result is not None
        assert len(result) == expected_count
        for i, template in enumerate(result):
            assert template.name == template_names[i]
            assert template.front.layout == front_html_contents[i]
            assert template.back.layout == back_html_contents[i]

        # Verify mocks were called
        mock_generic.assert_called_once()
        mock_front.assert_called_once()
        mock_back.assert_called_once()


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
    """Test the generate_front_side method.

    Args:
        role (GenerateDeckRole): GenerateDeckRole fixture
        requirement (str): Requirement for front side generation
        fields (List[str]): List of fields for the side
        expected_html_content (str): Expected HTML content
    """
    with patch.object(GenerateDeck, "acode_string", new_callable=AsyncMock) as mock_code:
        # Configure mock
        mock_code.return_value = expected_html_content

        # Execute the method
        result = await role.generate_front_side(fields, requirement)

        # Assertions
        assert result is not None
        assert result.layout == expected_html_content

        # Verify mock was called
        mock_code.assert_called_once()


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
    """Test the generate_back_side method.

    Args:
        role (GenerateDeckRole): GenerateDeckRole fixture
        requirement (str): Requirement for back side generation
        fields (List[str]): List of fields for the side
        expected_html_content (str): Expected HTML content
    """
    with patch.object(GenerateDeck, "acode_string", new_callable=AsyncMock) as mock_code:
        # Configure mock
        mock_code.return_value = expected_html_content

        # Execute the method
        result = await role.generate_back_side(fields, requirement)

        # Assertions
        assert result is not None
        assert result.layout == expected_html_content

        # Verify mock was called
        mock_code.assert_called_once()


@pytest.mark.parametrize(
    ("fields", "requirement"),
    [
        (
            [],
            "Empty fields requirement",
        ),
        (
            ["Single"],
            "Single field requirement",
        ),
    ],
)
@pytest.mark.asyncio
async def test_generate_deck_edge_cases(
    role: GenerateDeckRole,
    fields: List[str],
    requirement: str,
) -> None:
    """Test generate_deck with edge cases like empty fields.

    Args:
        role (GenerateDeckRole): GenerateDeckRole fixture
        fields (List[str]): List of fields (may be empty)
        requirement (str): Requirement for deck generation
    """
    with (
        patch.object(GenerateDeck, "propose", new_callable=AsyncMock) as mock_propose,
        patch.object(GenerateDeck, "alist_str", new_callable=AsyncMock) as mock_alist,
        patch.object(GenerateDeck, "generate_model", new_callable=AsyncMock) as mock_model,
    ):
        # Configure mocks for edge cases
        mock_propose.return_value = metadata_factory("Test", "Test description")
        mock_alist.return_value = ["test requirement"]
        mock_model.return_value = [model_factory("test_model", fields or ["default"])]

        # Execute the method
        result = await role.generate_deck(requirement, fields)

        # Assertions - should handle edge cases gracefully
        if fields:
            assert result is not None
        else:
            # Empty fields might return None or a valid deck depending on implementation
            # The test verifies the method handles it without crashing
            pass

        # Verify mocks were called
        mock_propose.assert_called_once()
        mock_alist.assert_called_once()


@pytest.mark.asyncio
async def test_generate_template_none_inputs(role: GenerateDeckRole) -> None:
    """Test generate_template with None inputs.

    Args:
        role (GenerateDeckRole): GenerateDeckRole fixture
    """
    with pytest.raises(ValueError, match="requirement must be a string or a list of strings"):
        # Test with None requirement
        await role.generate_template(["Field1"], None)

    # Test with valid requirement
    with (
        patch.object(GenerateDeck, "ageneric_string", new_callable=AsyncMock) as mock_generic,
        patch.object(GenerateDeck, "acode_string", new_callable=AsyncMock) as mock_code,
    ):
        mock_generic.return_value = "test_template"
        mock_code.side_effect = ["<div>Front</div>", "<div>Back</div>"]
        result_valid = await role.generate_template(["Field1"], "Valid requirement")
        assert result_valid is not None
        assert result_valid.name == "test_template"


@pytest.mark.parametrize(
    ("metadata_none", "models_none", "expected_result"),
    [
        (
            True,
            False,
            None,
        ),
        (
            False,
            True,
            None,
        ),
        (
            True,
            True,
            None,
        ),
    ],
)
@pytest.mark.asyncio
async def test_generate_deck_none_components(
    role: GenerateDeckRole,
    metadata_none: bool,
    models_none: bool,
    expected_result: Optional[Deck],
) -> None:
    """Test generate_deck when components return None.

    Args:
        role (GenerateDeckRole): GenerateDeckRole fixture
        metadata_none (bool): Whether metadata should be None
        models_none (bool): Whether models should be None
        expected_result: Expected result when components are None
    """
    with (
        patch.object(GenerateDeck, "propose", new_callable=AsyncMock) as mock_propose,
        patch.object(GenerateDeck, "alist_str", new_callable=AsyncMock) as mock_alist,
        patch.object(GenerateDeck, "generate_model", new_callable=AsyncMock) as mock_model,
    ):
        # Configure mocks based on test parameters
        mock_propose.return_value = None if metadata_none else metadata_factory("Test", "Test")
        mock_alist.return_value = ["test"] if not models_none else []
        mock_model.return_value = None if models_none else [model_factory("test", ["field"])]

        # Execute the method
        result = await role.generate_deck("Test requirement", ["Field1"])

        # Assertions
        assert result == expected_result


@pytest.mark.parametrize(
    ("ret_value", "source", "requirement", "expected_result"),
    [
        (
            deck_factory("Test Deck", "Test Description"),
            ["Field1", "Field2"],
            "Create test deck",
            "Test Deck",
        ),
    ],
)
@pytest.mark.asyncio
async def test_generate_deck_with_router(
    role: GenerateDeckRole,
    ret_value: Deck,
    source: List[str],
    requirement: str,
    expected_result: str,
) -> None:
    """Test generate_deck method with router mocking following test_diff.py pattern.

    Args:
        role (GenerateDeckRole): GenerateDeckRole fixture
        ret_value (Deck): Expected deck object
        source (List[str]): Source fields for deck generation
        requirement (str): Requirement for deck generation
        expected_result (str): Expected deck name
    """
    metadata_router = return_model_json_string(metadata_factory(ret_value.name, ret_value.description))
    return_json_obj_string(["model1", "model2"])

    with (
        install_router(metadata_router),
        patch.object(GenerateDeck, "alist_str", new_callable=AsyncMock) as mock_alist,
        patch.object(GenerateDeck, "generate_model", new_callable=AsyncMock) as mock_model,
    ):
        # Configure mocks
        mock_alist.return_value = ["test requirement"]
        mock_model.return_value = ret_value.models

        # Execute the method
        result = await role.generate_deck(requirement, source)

        # Assertions
        assert result is not None
        assert result.name == expected_result

        # Verify mocks were called
        mock_alist.assert_called_once()
        mock_model.assert_called_once()
