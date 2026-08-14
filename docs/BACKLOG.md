# Backlog — Finding Best Mobo by Buildzoid

The standing queue of what *might* be built, as opposed to a plan, which covers
the one change being built now. Two sections, and the difference between them is
the owner's approval:

- **Approved** — the owner has said yes. An agent working unattended implements
  these top to bottom, and keeps going until the list is done or it is truly
  blocked (`AGENTS.md`, "Work queue").
- **Proposed** — ideas, written as text, **never coded unprompted**. They move
  up when the owner moves them.

## Approved

_(nothing yet)_

## Proposed

### Make template updates stop costing a manual intervention

Every `copier update` that conflicts fails the `template-sync` check and needs
an owner bypass to land. It has happened on both updates that conflicted (#4 and
#28) and it will happen on every future one, because the check demands a tree
byte-identical to a replayed update while a conflict is precisely the case
copier hands to a human. This entry is the standing intent to fix it rather than
keep paying it; the incident record is the ratchet's business and is being
logged separately, so nothing here depends on it having landed.

Three directions, not mutually exclusive, roughly in order of preference:

1. **Teach the check about conflicts.** Keep the replay's *pre-resolution* tree
   and require this repository's tree to differ from it only inside hunks copier
   marked as conflicted. Everything outside a conflict hunk stays byte-for-byte,
   so a hand edit smuggled into an untouched file still fails. This is the fix
   named in the escapes entry, and it belongs upstream in the template.
2. **Reduce how often conflicts happen at all.** Most of ours come from
   template-owned documents this project legitimately rewrote — the design doc
   skeleton above all. If the template kept its guidance out of files projects
   are expected to replace wholesale, the conflict surface shrinks.
3. **Make the bypass cheap and visible instead of ad hoc**, if neither of the
   above lands: a documented, logged path for "conflicted sync, resolutions
   reviewed", so the exception is a procedure rather than a judgment call made
   fresh each time under time pressure.

Both the check and the workflow it guards are owner-owned gate paths, so the
ruling is the owner's — this entry exists so it is not rediscovered from scratch
on the next update.
