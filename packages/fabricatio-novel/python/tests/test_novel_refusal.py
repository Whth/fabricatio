"""Refusal-guard tests for scene composition: the ratio bands, the judge, the retries and the failure."""

from typing import Unpack

import pytest
from fabricatio_core.models.kwargs_types import LLMKwargs, ValidateKwargs
from fabricatio_mock import MockScript, Value, make_test_role
from fabricatio_novel.capabilities.novel import NovelCompose
from fabricatio_novel.models.context.scene import SceneContext
from fabricatio_novel.models.refusal import SceneRefusedError

REFUSAL = "I am sorry, but I cannot write this scene."
"""Eleven words against a forty-word budget: 0.28 of the budget, well under the 0.8 floor."""

MIDDLE = " ".join(["the rain fell hard"] * 13)
"""Fifty-two words against a forty-word budget: 1.30, inside the judged band."""

PROSE = " ".join(["the rain fell hard"] * 20)
"""Eighty words against a forty-word budget: 2.0, over the 1.5 accept ratio."""


def scene_ctx() -> SceneContext:
    """Build the scene every test composes: forty planned words, nothing written yet."""
    return SceneContext(title="Departure", description="The hero leaves home.", expected_word_count=40)


class TestSceneRefusalBands:
    """The three bands the guard reads a reply by."""

    async def test_a_below_floor_reply_is_asked_again_without_judging(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert a short reply draws a retry rather than a verdict, and the retry's prose is kept."""
        role = make_test_role(NovelCompose, name="novel_role")
        ctx = scene_ctx()
        judged: list[str] = []

        async def fake_judge(
            prompt: str,
            affirm_case: str = "",
            deny_case: str = "",
            send_to: str | None = None,
            **kwargs: Unpack[ValidateKwargs[bool]],
        ) -> bool | None:
            judged.append(prompt)
            raise AssertionError("a reply under the floor is a refusal without asking a judge")

        monkeypatch.setattr(type(role), "ajudge", staticmethod(fake_judge))
        with MockScript.from_values(
            Value.from_text(REFUSAL, name="refusal"),
            Value.from_text(PROSE, name="scene prose"),
        ):
            scene = await role.compose_scene(ctx)

        assert judged == []  # the floor decided on its own
        assert scene is not None
        assert scene.content == PROSE
        assert REFUSAL not in ctx.content

    async def test_an_over_accept_reply_is_kept_without_judging(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert prose over the accept ratio is taken on the ratio alone, one ask, no verdict."""
        role = make_test_role(NovelCompose, name="novel_role")
        ctx = scene_ctx()
        judged: list[str] = []
        asked: list[str] = []

        async def fake_judge(
            prompt: str,
            affirm_case: str = "",
            deny_case: str = "",
            send_to: str | None = None,
            **kwargs: Unpack[ValidateKwargs[bool]],
        ) -> bool | None:
            judged.append(prompt)
            raise AssertionError("a reply over the accept ratio is prose without asking a judge")

        async def fake_aask(question: str, send_to: str | None = None, **kwargs: Unpack[LLMKwargs]) -> str:
            asked.append(question)
            return PROSE

        monkeypatch.setattr(type(role), "ajudge", staticmethod(fake_judge))
        monkeypatch.setattr(type(role), "aask", staticmethod(fake_aask))

        scene = await role.compose_scene(ctx)

        assert judged == []
        assert len(asked) == 1
        assert scene is not None
        assert scene.content == PROSE

    async def test_the_middle_band_is_put_to_the_judge(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert a ratio between the floor and the accept ratio is decided by one verdict."""
        role = make_test_role(NovelCompose, name="novel_role")
        ctx = scene_ctx()
        judged: list[str] = []

        async def fake_judge(
            prompt: str,
            affirm_case: str = "",
            deny_case: str = "",
            send_to: str | None = None,
            **kwargs: Unpack[ValidateKwargs[bool]],
        ) -> bool | None:
            judged.append(prompt)
            return False  # not a refusal

        monkeypatch.setattr(type(role), "ajudge", staticmethod(fake_judge))
        with MockScript.from_values(Value.from_text(MIDDLE, name="terse but complete scene")):
            scene = await role.compose_scene(ctx)

        assert len(judged) == 1  # exactly one call went to the judge
        assert MIDDLE in judged[0]  # carrying the reply
        assert "Departure" in judged[0]  # and what the scene was asked to be
        assert scene is not None
        assert scene.content == MIDDLE

    async def test_the_judge_can_send_a_middle_band_reply_back(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert a middle-band reply the judge reads as a refusal is asked again."""
        role = make_test_role(NovelCompose, name="novel_role")
        ctx = scene_ctx()
        verdicts = [True, False]  # refusal, then prose
        judged: list[str] = []

        async def fake_judge(
            prompt: str,
            affirm_case: str = "",
            deny_case: str = "",
            send_to: str | None = None,
            **kwargs: Unpack[ValidateKwargs[bool]],
        ) -> bool | None:
            judged.append(prompt)
            return verdicts.pop(0)

        monkeypatch.setattr(type(role), "ajudge", staticmethod(fake_judge))
        with MockScript.from_values(
            Value.from_text(MIDDLE, name="judged a refusal"),
            Value.from_text(PROSE, name="scene prose"),
        ):
            scene = await role.compose_scene(ctx)

        assert len(judged) == 1  # only the middle-band reply needed a verdict; the retry's prose did not
        assert MIDDLE in judged[0]
        assert scene is not None
        assert scene.content == PROSE

    async def test_a_verdict_the_judge_cannot_give_reads_as_a_refusal(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert a middle-band reply nobody could vouch for is asked again instead of written down."""
        role = make_test_role(NovelCompose, name="novel_role")
        ctx = scene_ctx()
        verdicts: list[bool | None] = [None, False]

        async def fake_judge(
            prompt: str,
            affirm_case: str = "",
            deny_case: str = "",
            send_to: str | None = None,
            **kwargs: Unpack[ValidateKwargs[bool]],
        ) -> bool | None:
            return verdicts.pop(0)

        monkeypatch.setattr(type(role), "ajudge", staticmethod(fake_judge))
        with MockScript.from_values(
            Value.from_text(MIDDLE, name="reply the judge could not answer for"),
            Value.from_text(PROSE, name="scene prose"),
        ):
            scene = await role.compose_scene(ctx)

        assert scene is not None
        assert scene.content == PROSE


class TestSceneRefusalRetries:
    """What a refused scene costs and what happens when the retries run out."""

    async def test_a_retry_bypasses_the_cache_read_and_still_stores(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert the first ask keeps the caller's kwargs and the retry reads past the cache while storing its answer."""
        role = make_test_role(NovelCompose, name="novel_role")
        ctx = scene_ctx()
        calls: list[dict[str, object]] = []
        replies = [REFUSAL, PROSE]

        async def fake_aask(question: str, send_to: str | None = None, **kwargs: Unpack[LLMKwargs]) -> str:
            calls.append(dict(kwargs))
            return replies.pop(0)

        monkeypatch.setattr(type(role), "aask", staticmethod(fake_aask))

        scene = await role.compose_scene(ctx)

        assert len(calls) == 2
        assert "no_cache" not in calls[0]  # the first ask reads the cache like any other call
        assert calls[1] == {
            "no_cache": True,
            "no_store": False,
        }  # the retry re-asks the deployment and stores its answer
        assert scene is not None
        assert scene.content == PROSE

    async def test_every_attempt_refused_fails_the_run(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert four refusals in a row raise instead of serializing policy text into the novel."""
        role = make_test_role(NovelCompose, name="novel_role")
        ctx = scene_ctx()
        with (
            MockScript.from_values(
                Value.from_text(REFUSAL, name="refusal"),
                Value.from_text(REFUSAL, name="refusal"),
                Value.from_text(REFUSAL, name="refusal"),
                Value.from_text(REFUSAL, name="refusal"),
            ),
            pytest.raises(SceneRefusedError, match="Scene 'Departure' read as a refusal on every one of its 4 attempt"),
        ):
            await role.compose_scene(ctx)

        assert not ctx.content  # the refusals never reached the context, so nothing can serialize them

    async def test_the_role_retry_budget_wins_over_the_package_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert a role that allows no retry fails the scene on its first refusal."""
        role = make_test_role(NovelCompose, name="novel_role")
        role.refusal_max_retries = 0
        ctx = scene_ctx()
        asked = 0

        async def fake_aask(question: str, send_to: str | None = None, **kwargs: Unpack[LLMKwargs]) -> str:
            nonlocal asked
            asked += 1
            return REFUSAL

        monkeypatch.setattr(type(role), "aask", staticmethod(fake_aask))

        with pytest.raises(SceneRefusedError, match="every one of its 1 attempt"):
            await role.compose_scene(ctx)

        assert asked == 1

    async def test_a_blank_reply_is_retried_like_a_refusal(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Assert a blank answer costs a retry rather than failing the scene outright."""
        role = make_test_role(NovelCompose, name="novel_role")
        ctx = scene_ctx()
        with MockScript.from_values(
            Value.from_text("", name="blank reply"),
            Value.from_text(PROSE, name="scene prose"),
        ):
            scene = await role.compose_scene(ctx)

        assert scene is not None
        assert scene.content == PROSE
