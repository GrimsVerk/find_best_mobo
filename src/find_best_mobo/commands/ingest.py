"""The `ingest` subcommand: validate one claims file and store it, or refuse.

The Python half of Stage B, and the half that spends nothing. An agent produced
the file; this stage decides whether it counts. **The agent is never trusted to
self-check** (BL-23), so nothing here believes the file until `parse_claims` has
read every field of it.

A refusal is the point rather than an inconvenience. R9 requires that a bundle
whose output fails validation is "reported and retried or set aside — never
silently dropped", and the shape of that here is: name every fault, append
nothing, and leave the bundle unconsumed so a retry has something to retry.

Nothing in this module invokes a model, and the module that would is not
imported.
"""

from __future__ import annotations

from argparse import Namespace
from collections.abc import Sequence
from pathlib import Path

from find_best_mobo.artifacts import MissingArtifact, require_file
from find_best_mobo.claims import InvalidClaims, parse_claims
from find_best_mobo.claimstore import BatchAlreadyStored, append_claims, store_path
from find_best_mobo.commands import subcommand_parser
from find_best_mobo.config import Config


def parse_args(argv: Sequence[str]) -> Namespace:
    """One claims file and the batch it belongs to.

    The batch is an argument rather than a field in the file, and deliberately:
    a file that declared its own batch could declare someone else's, which is
    the one mistake an append-only store cannot undo after the fact.
    """
    parser = subcommand_parser(
        "ingest", "Validate one claims file against the schema and append it to the store."
    )
    # Neither is declared required to argparse, and both are checked below
    # instead. argparse reports a MISSING required argument before an
    # UNRECOGNISED one, so `find-best-mobo ingest --nonsense` would complain
    # about the absent path and never name the flag — and R1006's rule is that
    # an undeclared flag is always named. This is the first stage in the project
    # to take arguments at all, which is why nothing hit the ordering before.
    parser.add_argument("path", nargs="?", help="the claims file to ingest")
    parser.add_argument("--batch", type=int, help="the batch it was extracted in")
    args = parser.parse_args(list(argv))
    missing = [
        name for name, value in (("path", args.path), ("--batch", args.batch)) if value is None
    ]
    if missing:
        parser.error(f"the following arguments are required: {', '.join(missing)}")
    return args


def run(config: Config, args: Namespace) -> int:
    """Validate the file, append it, and say what happened."""
    try:
        path = require_file(Path(args.path), "claims file", "extract")
    except MissingArtifact as error:
        print(error.message())
        return 1

    try:
        claims = parse_claims(path.read_text(encoding="utf-8"), path, args.batch)
    except InvalidClaims as error:
        # Every fault, in one message, so a malformed batch costs one round
        # trip rather than one per bad row.
        print(error.message())
        return 1

    try:
        appended = append_claims(claims, config)
    except BatchAlreadyStored as error:
        print(error.message())
        return 1

    print(f"Appended {appended} claims from {path} to {store_path(config)} as batch {args.batch}")
    if appended == 0:
        # A real value, not a failure: a bundle can genuinely contain no claim
        # about any board. Saying so keeps it distinguishable from a refusal,
        # which is the distinction R1005 and OD-9 insist on everywhere else.
        print("  The file was valid and held no claims. Nothing was appended.")
    return 0
