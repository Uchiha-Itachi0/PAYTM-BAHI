"""The munshi: the shop's bookkeeper, as an agent.

The shopkeeper talks or types. Sarvam's model (`sarvam.munshi`) understands him,
looks people up through `tools`, asks when it is not sure, and proposes the entry
as a card. Code keeps the book: every tool reads the real book or makes a draft,
the draft is checked, and only his yes turns it into an entry, through the same
ledger code a typed entry uses. See `brain` for the loop.
"""
