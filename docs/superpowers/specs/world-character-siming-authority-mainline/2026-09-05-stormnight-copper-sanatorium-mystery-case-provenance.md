# Stormnight Copper Sanatorium Case Provenance

The case is original repository content. Its only external inspiration is the
locked-room mystery structure of Project Gutenberg eBook #1661, *The
Adventure of the Speckled Band*, first published in 1892.

The repository does not vendor the source text, names, dialogue, illustrations,
or modern adaptations. The case uses new names, new locations, new clues, new
dialogue slots and new typed facts. The external source is retained only as a
structural provenance reference:

- https://www.gutenberg.org/ebooks/1661

Before commercial distribution, the release owner must independently confirm
public-domain status in every target jurisdiction and preserve this provenance
record in the package review artifact.

The immutable case fixture is `stormnight_case_content()` in
`backend/app/gameplay/p5/scripted_mystery_content.py`. Its admission digest is
derived from canonical normalized content; no caller-supplied digest is trusted.
