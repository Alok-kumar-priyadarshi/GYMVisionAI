# file_name: coercion.py

"""Enum coercion for domain entities.

Entities are plain dataclasses, which perform no type conversion: assigning the
string ``"Duration"`` to a field annotated as ``ExerciseType`` leaves a ``str``
in place. Identity comparisons against the enum then silently fail.

Coercing in ``__post_init__`` keeps an entity's invariants true no matter how it
was constructed, whether from a repository row, an API payload or a test.
"""

from enum import Enum
from typing import Iterable, TypeVar

EnumT = TypeVar("EnumT", bound=Enum)


def as_enum(value: object, enum_type: type[EnumT]) -> EnumT:
    """Convert a value into a member of an enumeration.

    Args:
        value: An existing member, or a value that identifies one.
        enum_type: The enumeration to convert into.

    Returns:
        The matching member.

    Raises:
        ValueError: If the value identifies no member.
    """
    if isinstance(value, enum_type):
        return value
    return enum_type(value)


def as_enums(values: Iterable[object], enum_type: type[EnumT]) -> tuple[EnumT, ...]:
    """Convert an iterable of values into enumeration members."""
    return tuple(as_enum(value, enum_type) for value in values)
