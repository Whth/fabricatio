from fabricatio.models.generic import Base, Described, Named, WithBriefing, WithDependency, WithFormatedJsonSchema


def test_base_initialization():
    base = Base()
    assert base is not None


def test_named_initialization():
    named = Named(name="Test Name")
    assert named.name == "Test Name"


def test_described_initialization():
    described = Described(description="Test Description")
    assert described.description == "Test Description"


def test_withbriefing_initialization():
    withbriefing = WithBriefing(name="Test Name", description="Test Description")
    assert withbriefing.name == "Test Name"
    assert withbriefing.description == "Test Description"


def test_withjsonexample_initialization():
    withjsonexample = WithFormatedJsonSchema()
    assert withjsonexample is not None


def test_withdependency_initialization():
    withdependency = WithDependency(dependencies=["file1.txt", "file2.txt"])
    assert withdependency.dependencies == ["file1.txt", "file2.txt"]


def test_withdependency_methods():
    withdependency = WithDependency(dependencies=["file1.txt"])
    withdependency.add_dependency("file2.txt")
    assert "file2.txt" in withdependency.dependencies
    withdependency.remove_dependency("file1.txt")
    assert "file1.txt" not in withdependency.dependencies


# New test cases
def test_withbriefing_update_briefing():
    withbriefing = WithBriefing(name="Test Name", description="Test Description")


def test_withjsonexample_json_example():
    withjsonexample = WithFormatedJsonSchema()
    json_example = withjsonexample.formated_json_schema()
    # Add assertions based on expected behavior
