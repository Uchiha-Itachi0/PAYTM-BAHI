"""M3 · Memory: what BAHI remembers that the numbers can't show.

The book has the arithmetic. Memory keeps what people said: the shopkeeper's
notes, a customer's promise in chat, the nickname the shopkeeper uses. The
record is the book's own `memories` table (store/memories.py), which the
customer's page lists and Tonight reads; Cognee (cognee_client.py) keeps a copy
on the local Postgres to find it again by meaning, and the worker (worker.py)
fills it in the background.

What memory can never do: write an entry, change an amount, send a reminder, or
show the shopkeeper's notes to the customer. A wait can only hold a reminder.
"""
