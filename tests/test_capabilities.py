from fabricatio.capabilities.advanced_judge import AdvancedJudge


def test_advanced_judge_exists():
    """Test that AdvancedJudge is properly imported."""
    assert AdvancedJudge is not None


def test_advanced_judge_instantiation():
    """Test basic instantiation of AdvancedJudge."""
    judge = AdvancedJudge()
    assert judge is not None


def test_advanced_judge_methods():
    """Test methods of AdvancedJudge."""
    judge = AdvancedJudge()

    # Test simple judgment
    result = judge.judge("This is a test")
    assert isinstance(result, dict)

    # Test batch judgment
    results = judge.batch_judge(["test1", "test2"])
    assert isinstance(results, list)
    assert len(results) == 2
    assert all(isinstance(r, dict) for r in results)


def test_advanced_judge_with_context():
    """Test judgment with additional context."""
    judge = AdvancedJudge()

    # Test with context data
    result = judge.judge("This is a test", context={"extra": "data"})
    assert isinstance(result, dict)
    assert "extra" in result or "error" in result  # Depending on implementation


def test_advanced_judge_invalid_input():
    """Test handling of invalid input."""
    judge = AdvancedJudge()

    # Test with empty string
    result = judge.judge("")
    assert isinstance(result, dict)
    assert "error" in result or "score" in result

    # Test with non-string input
    result = judge.judge(12345)
    assert isinstance(result, dict)
    assert "error" in result or "score" in result
