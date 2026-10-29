from dataclasses import dataclass


@dataclass(slots=True)
class Segment:
    """A time segment

    The class uses __slots__ (no per-instance __dict__), which saves about a quarter of the memory of
    an annotation (≈150 to ≈110 bytes): this matters for files with tens of thousands of segments.

    Attributes
    ----------
    start_time : float
        The start time in seconds
    end_time : float
        The end time in seconds
    """

    start_time: float
    end_time: float
