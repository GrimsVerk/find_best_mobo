# Vision — find_best_mobo

## What this project is for

This exists solely for me to collect as much of Buildzoid's motherboard
expertise as possible and use it to inform one buying decision: which AM5 board
to buy.

"Best" means **safe**, and safe has a specific technical meaning here. Buildzoid
has shown, with an oscilloscope, that some boards deliver voltage spikes to the
CPU that are extremely high but last only milliseconds — short enough that no
software monitoring tool can catch them. He posited those spikes as the reason
so many i9-13900Ks failed. I have a 13700K, a model that was also affected, and
that is how I found him. A similar failure pattern is documented for the 7800X3D
and I strongly suspect the boards are at fault there too, for the same reason.

I want to buy a 7950X3D or a 9950X3D, and I do not want to lose it the way those
chips were lost. It is also really important that the board can carry a **Zen 6
upgrade** — I want to keep this board through the next CPU as well, so it has to
last.

He is trustworthy to me because I have already relied on him once and it worked:
I found a video where he tuned a board very similar to mine, applied the same
logic and BIOS settings to undervolt my 13700K, and Cinebench temps dropped from
100°C to about 90°C. I know AMD chips do not overheat the same way. The voltage
spike thing is what I am after, and it is real.

## What counts as evidence

**Direct evidence** is Buildzoid assessing a specific board, and it is what I am
after.

**Transferred evidence counts too, and is often all there is.** If he says a
board is safe with some other AM5 CPU, that is genuine supporting evidence that
it is safe for the ones I am considering, even where the 7950X3D or 9950X3D is
never named. It has to be labelled as transferred rather than presented as
direct — but it must not be thrown away, because discarding it would throw away
most of what he has actually said.

**Transferred evidence is graded by power draw.** Safe with a 9900X is stronger
evidence than safe with a 7600X: the more current the board was asked to
deliver, the more the result tells me about a 16-core X3D part. Rank it that way
rather than treating every AM5 CPU as equivalent.

**Nothing before 1 January 2023 is ever considered.** The 7800X3D launched that
month and no board is really relevant before it. Some boards do predate their
CPU, so the cutoff is a little arbitrary — but I want a Zen 6 upgrade path
anyway, so I would prefer a newer board regardless. When I say "old" in this
document, I mean old *within* that window, not old in general.

## Priorities, in order

1. **Real, sourced information about which boards Buildzoid considers safe** for
   a 7950X3D or 9950X3D — and which he does not. This is the whole product.
2. **Surfacing videos that are dense in information about *this* problem** —
   packed with useful knowledge about board safety and the boards I would
   actually buy. Not "technically dense", though technical is completely fine.
   Dense in what is relevant to the decision I am making. If a video is about a
   board I would genuinely consider, I will watch all of it. What I refuse to do
   is sit through multiple hour-long videos about boards that are irrelevant to
   me, even if they technically work with AM5.
3. **Not wasting tokens.** Cost matters, but far less than the two above. Worst
   case I blow my 5-hour limit and wait; worst worst case I blow the weekly
   limit and wait a few days. Cost is about not being *stupid* — not spending
   budget I could have used on other projects — rather than a hard constraint.

## What I would trade away

- **Cost, for information quality.** Given a choice between a cheaper run and a
  better-sourced answer, take the better answer.
- **Completeness on Intel-focused videos.** A lot of his catalogue is Intel
  board testing. If a video is strictly about Intel, discard it completely —
  especially an older one.
- **Breadth, for relevance.** I do not want every AM5-compatible board. I want
  the ones worth considering.
- **My own reading time over my own watching time.** I would rather the system
  filter hard and hand me three videos than be safe and hand me thirty.

**The one trade that is graded rather than flat:** I assume more recent videos
are more likely to discuss a board relevant to me, so the more recent a video
is, the more important it is that the search is complete and the analysis
thorough. The known cost of discarding Intel videos is that he sometimes
compares an AMD board inside one — and if there is genuinely relevant
information about a good AMD board in an Intel video, that is really important
not to miss. I accept missing it in an old video. I do not accept missing it in
a recent one.

## Core tenets

These are stops on a *decision*, not on work. In practice each one resolves by
the agent choosing the other design, and it only halts to ask me if there is no
design that satisfies it at all — which for these four should approximately
never happen. None of them is a reason to stop working and wait for me.

1. **Never assert a safety verdict for a board he never assessed.** No inferring
   "probably fine" from a similar VRM, the same brand, or an adjacent model
   number. Transferring his result across CPUs on the *same* board is reasoning
   about his evidence and is wanted; inventing a result for a board he never
   touched is not, and no design decision may make that possible.
2. **Never present transferred evidence as direct.** A verdict carried over from
   a different AM5 CPU is labelled as such, with the CPU named, so I can weigh
   it myself.
3. **Never spend budget on material with no chance of relevance.** Where some
   other goal can only be met by processing content with no AMD or AM5 signal,
   that goal loses and a cheaper design is chosen. This is a rule for picking
   between designs, not a reason to stop and ask.
4. **Every claim carries a video and a timestamp.** Provenance is not optional
   in any design: a claim I cannot go and watch is not usable, and the pointer
   to the moment he said it *is* the recommendation of what to watch.

## What makes an answer unacceptable

- **A safety verdict on a board he never actually gave one for.** If he did not
  say it, the answer must say he did not say it. Silence has to read as silence.
- **Burning the weekly limit sifting through completely irrelevant transcripts.**
  That would genuinely annoy me, and it is the one failure I can name outright.
- **A recommendation I cannot go and check.** If I cannot get to the video and
  the moment he said it, I cannot act on it — the point is that I watch him and
  decide, not that I trust a summary.

## Background, not a requirement

**Zen 6.** I want this board to survive a Zen 6 upgrade, but Buildzoid will
almost never talk about it — his channel is technical and practical, testing
boards and CPUs that exist now, not future speculation. AMD has only recently
confirmed Zen 6 on AM5, so it may appear in the very latest videos and nowhere
else. So it is not a priority and must not be treated as a filter on his
content. It is here so that if a future stage ever looks up technical details
for a specific board, anything that would strictly rule out a Zen 6 upgrade path
disqualifies that board. No such lookup exists in the design today; this is
seeded for when it might.
