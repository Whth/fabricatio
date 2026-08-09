from typing import List

from fabricatio_capabilities.models.generic import WordCount
from fabricatio_core.models.generic import Described, SketchedAble, Titled
from pydantic import Field

from fabricatio_novel.models.context.chapter import ChapterContext
from fabricatio_novel.models.context.scene import SceneContext
from fabricatio_novel.models.context.story import StoryContext


class ScenePlan(Titled, Described, WordCount): ...


class StoryPlan(Titled, Described, WordCount):
    scenes: List[ScenePlan] = Field(default_factory=list)


class ChapterPlan(Titled, Described, WordCount):
    stories: List[StoryPlan] = Field(default_factory=list)


class NovelPlan(SketchedAble):
    chapters: List[ChapterPlan] = Field(default_factory=list)

    def build_chapter_contexts(self, language: str = "") -> List[ChapterContext]:
        return [
            ChapterContext(
                title=chapter.title,
                description=chapter.description,
                expected_word_count=chapter.expected_word_count,
                story_context=[
                    StoryContext(
                        title=story.title,
                        description=story.description,
                        expected_word_count=story.expected_word_count,
                        scene_context=[
                            SceneContext(
                                title=scene.title,
                                description=scene.description,
                                expected_word_count=scene.expected_word_count,
                                language=language,
                            )
                            for scene in story.scenes
                        ],
                    )
                    for story in chapter.stories
                ],
            )
            for chapter in self.chapters
        ]
