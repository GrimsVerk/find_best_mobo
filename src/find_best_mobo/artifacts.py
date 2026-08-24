"""What each stage requires of the one before it, and how it says so.

The pipeline is a chain of files: `index` writes an index, `fetch` writes a
transcript cache, `select` writes selections, `estimate` reads all three. Before
R1005 a stage could read an absent upstream artifact as an empty one — BL-7
measured `estimate` projecting against a silently zero denominator, which is
indistinguishable from a real empty corpus and is the one number the checkpoint
exists to make trustworthy.

**Absence and emptiness are different facts and must read differently.** An
empty index is a channel with nothing in range: a real value, reported as one.
A missing index is a stage that never ran: an error, naming the artifact and the
command that produces it.

`MissingArtifact` subclasses `FileNotFoundError` deliberately. Every existing
`except FileNotFoundError` and every existing refusal keeps working, and no
caller has to learn a new exception to be correct — the subclass exists to carry
the three things the message needs, not to be caught on its own.
"""

from __future__ import annotations

import errno
import os
from pathlib import Path


class MissingArtifact(FileNotFoundError):
    """An upstream artifact is absent, and this names what produces it.

    Constructed the way a `FileNotFoundError` from the standard library is, so
    `.errno` and `.filename` carry what every existing handler already reads.
    """

    def __init__(self, path: Path, description: str, produced_by: str) -> None:
        super().__init__(errno.ENOENT, os.strerror(errno.ENOENT), str(path))
        self.path = path
        self.description = description
        self.produced_by = produced_by

    def message(self) -> str:
        """The one sentence R1005 asks for: what is missing, and what makes it."""
        return (
            f"No {self.description} at {self.path}. Run `find-best-mobo {self.produced_by}` first."
        )


def require_file(path: Path, description: str, produced_by: str) -> Path:
    """Return `path`, or raise `MissingArtifact` if it is not an existing file.

    A path of the wrong kind — a directory where a file is expected — counts as
    absent rather than as its own error class. The owner's remedy is the same
    either way, and a second message for a state nobody has hit is speculative.
    """
    if not path.is_file():
        raise MissingArtifact(path, description, produced_by)
    return path


def require_directory(path: Path, description: str, produced_by: str) -> Path:
    """Return `path`, or raise `MissingArtifact` if it is not an existing directory.

    **An empty directory passes.** That is the sentence this module exists to
    encode: `fetch` that ran and cached nothing leaves an empty cache, and a run
    over an empty corpus is a real result, not a broken precondition.
    """
    if not path.is_dir():
        raise MissingArtifact(path, description, produced_by)
    return path
