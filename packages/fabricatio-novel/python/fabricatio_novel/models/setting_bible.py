"""Setting Bible (设定集) models — the novel's timeless settings facts.

Design spec ``2026-08-08-novel-gen-overhaul-design.md`` §3.2: a feature-free
:class:`CoreSettingBible` carries only universal sections; style-specific
sections are mixins composed into a derived subclass selected per novel via
``novel_config.setting_bible_model``.

Tense-split rule (D6): the bible is the timeless base — it answers "who is
this person / what is this world". Anything that changes across chapters
(current rank, relationship progress, golden-finger progress, arc stage,
deadlines) is NOT here; it lives in the event log / line web with
timestamps.

Persistence is workflow-owned (D17): the bible is an in-memory
:class:`PersistentAble` object; checkpoints and the ``bible.md`` export are
workflow Actions.
"""

from typing import Dict, List, Literal, Optional, Self

from fabricatio_capabilities.models.generic import PersistentAble
from fabricatio_core.models.generic import Base
from pydantic import Field


class WorldRule(Base):
    """世界规则 / 力量体系条目 — a rule of the world or the power system."""

    name: str
    """Rule name (e.g. 修炼境界划分 / 灵气浓度)."""

    description: str
    """What the rule is and how it works."""

    constraints: List[str] = Field(default_factory=list)
    """限制 / 代价 — limits, costs, and side effects of the rule."""

    is_taboo: bool = False
    """世界禁忌 flag — violations carry dramatic weight."""


class Faction(Base):
    """势力条目 — 门派 / 家族 / 帝国 / 组织."""

    name: str
    """Faction name."""

    position: str = ""
    """定位 — role in the world (e.g. 正道魁首 / 边陲小派)."""

    structure: str = ""
    """组织架构 — hierarchy and internal division."""

    resources: str = ""
    """资源 — wealth, territory, influence, backing."""

    stance: str = ""
    """与主角 / 彼此关系 — stance toward the protagonist and other factions."""

    key_members: List[str] = Field(default_factory=list)
    """Key members (references :class:`CharacterEntry` names)."""


class CharacterEntry(Base):
    """角色条目 — the timeless character base (无时态基底).

    Answers "who is this person". Time-varying quantities (rank, relationship
    progress, golden-finger progress) live in the event log / line web, never
    here (D6).
    """

    name: str
    """Character name — the consistency anchor (StateLedger / line web key on it)."""

    role: str
    """protagonist | supporting | antagonist."""

    appearance: str = ""
    """外貌 — physical description."""

    personality: str = ""
    """性格 — surface and deep personality."""

    desire: str = ""
    """欲望 / 目标 — what drives this character."""

    fear: str = ""
    """恐惧 / 底线 — what this character fears or refuses."""

    language_style: str = ""
    """说话风格 — speech patterns and verbal habits."""

    golden_finger: Optional[str] = None
    """金手指规则面 — the cheat's RULES/limits/side effects, not its progress."""


class GlossaryEntry(Base):
    """术语条目 — the terminology consistency anchor (一致性锚点)."""

    term: str
    """The term as first encountered (possibly an alias spelling)."""

    canonical: str
    """标准写法 — the canonical spelling/name."""

    aliases: List[str] = Field(default_factory=list)
    """别名 — other accepted spellings / nicknames."""

    definition: str = ""
    """定义 — what the term means."""


class ForeshadowEntry(Base):
    """伏笔条目 — a planted thread awaiting payoff."""

    description: str
    """What is planted and (ideally) how it pays off."""

    planted_chapter: Optional[int] = None
    """1-based chapter where it was planted (back-filled by event audits)."""

    payoff_chapter: Optional[int] = None
    """1-based chapter where it is paid off."""

    status: Literal["open", "paid", "dropped"] = "open"
    """Foreshadow lifecycle status."""


class CoreSettingBible(PersistentAble):
    """设定集核心 — only universal sections; genre variance rides on mixins (D1/D8).

    Over-structuring constrains LLM output and costs tokens to transmit, so
    the core carries just the fields every novel needs; extended sections
    (历史/文明/种族/物品/时间线) are deliberate additions via the mixin
    pattern, never v1 core fields.
    """

    premise: str = ""
    """一句话世界观 — the world in one sentence."""

    genre_tags: List[str] = Field(default_factory=list)
    """题材标签 — genre tags."""

    tone: str = ""
    """基调 — 热血 / 黑暗 / 轻松 / 悬疑 ..."""

    selling_points: List[str] = Field(default_factory=list)
    """卖点 — the novel's selling points (D5, standard 大纲辅助设定 item)."""

    world_rules: List[WorldRule] = Field(default_factory=list)
    """世界规则 / 力量体系 entries."""

    factions: List[Faction] = Field(default_factory=list)
    """势力 entries."""

    characters: List[CharacterEntry] = Field(default_factory=list)
    """角色 entries — the canonical roster."""

    glossary: List[GlossaryEntry] = Field(default_factory=list)
    """术语 entries — the terminology consistency anchor."""

    foreshadowing: List[ForeshadowEntry] = Field(default_factory=list)
    """伏笔 entries."""

    changelog: List[str] = Field(default_factory=list)
    """设定变更记录 — append-only change log (auto-sync and manual update both append)."""

    def append_changelog(self, entry: str) -> Self:
        """Append one change-log entry and return self (chainable).

        Args:
            entry: The change description (e.g. "absorbed character X from
                drift candidates", "updated world_rules section").
        """
        ...

    def section_counts(self) -> Dict[str, int]:
        """Per-section entry counts, for creation/sync summary logging.

        Returns:
            Mapping of section name → entry count (world_rules, factions,
            characters, glossary, foreshadowing).
        """
        ...


class StyleSettingMixin(Base):
    """文风 / 命名 / 文本格式 extension section — composed into a derived bible.

    Example::

        class MyNovelSettingBible(CoreSettingBible, StyleSettingMixin):
            \"\"\"Derived: core + style extension, selected via novel_config.\"\"\"

    Text-format rules fold in here as two minimal fields — no separate class
    (D8). The style constraints render verbatim into every event/chapter
    prompt as the static 文本格式规范 block.
    """

    narrative_voice: str = ""
    """视角 / 人称 — point of view and person."""

    style_tone: str = ""
    """文风基调 — prose style and tone."""

    naming_rules: str = ""
    """命名规则 — 人名 / 地名 / 功法名 rules."""

    style_constraints: List[str] = Field(default_factory=list)
    """Abstract natural-language constraints (D13): one rule per entry —
    格式/尺度/禁忌/文风细则 (e.g. "对话用中文双引号…包裹", "性描写尺度:
    清水, 亲密场面留白处理"). No enum, no per-rule schema, no taboo word-list.
    """
