"""Value objects shared by highlight collection and presentation."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Highlight:
    """A timestamped link to a notable point in a video."""

    seconds: int
    url: str
