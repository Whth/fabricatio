"""A patch class for updating the description and name of a `WithBriefing` object."""

from fabricatio.models.generic import Patch, WithBriefing


class BriefingPatch[T:WithBriefing](Patch[T], WithBriefing):
    """Patch class for updating the description and name of a `WithBriefing` object."""
