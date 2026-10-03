"""Cognee, for the rest of BAHI: remember a text, recall by meaning, forget.

Cognee is async and BAHI's API is not (service/app.py), so Cognee runs on one
event loop in a thread of its own, and these calls wait on it. One loop, kept
for the life of the process: its Postgres connections belong to that loop.

It is imported the first time it is needed, after its settings are in place
(settings.py): the API starts as fast as before, and the tests never load it.
Each shop's memory is its own Cognee dataset, `shop-<shop id>`, stored in its
own schema; a recall is asked of that dataset only.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import threading
from collections.abc import Coroutine
from typing import Any, Protocol, TypeVar
from uuid import UUID

from bahi.memory import settings

log = logging.getLogger(__name__)

T = TypeVar("T")

#: A remember runs Sarvam over the text and OpenAI over the pieces: seconds.
REMEMBER_S = 120.0
#: A recall only looks things up (no model writes an answer): about a second.
RECALL_S = 20.0
FORGET_S = 60.0
#: What a recall hands the munshi, at most.
RECALLED_CHARS = 3000


class Memory(Protocol):
    """What BAHI asks of a memory. Cognee in the app; a fake in the tests."""

    def remember(self, shop_id: str, text: str, customer_id: str) -> str | None:
        """Keeps the text in this shop's memory; its id there, if known."""
        ...

    def recall(self, shop_id: str, question: str) -> str:
        """What this shop's memory holds that answers the question, as text for
        the munshi to read. Empty when nothing does."""
        ...

    def forget(self, shop_id: str, cognee_id: str) -> None: ...


def dataset(shop_id: str) -> str:
    return f"shop-{shop_id}"


class Cognee:
    """The memory, on the local Postgres. Thread-safe: every call runs on the
    one loop."""

    def __init__(self, database_url: str) -> None:
        self._url = database_url
        self._loop: asyncio.AbstractEventLoop | None = None
        self._lock = threading.Lock()
        self._cognee: Any = None

    def _run(self, make: Coroutine[Any, Any, T], timeout: float) -> T:
        with self._lock:
            if self._loop is None:
                os.environ.update(settings.cognee_env(self._url))
                loop = asyncio.new_event_loop()
                threading.Thread(
                    target=loop.run_forever, name="cognee", daemon=True
                ).start()
                self._loop = loop
        return asyncio.run_coroutine_threadsafe(make, self._loop).result(timeout)

    async def _import(self) -> Any:
        if self._cognee is None:
            import cognee  # type: ignore[import-untyped]

            self._cognee = cognee
        return self._cognee

    def remember(self, shop_id: str, text: str, customer_id: str) -> str | None:
        return self._run(self._remember(shop_id, text, customer_id), REMEMBER_S)

    async def _remember(self, shop_id: str, text: str, customer_id: str) -> str | None:
        cognee = await self._import()
        r = await cognee.remember(
            text, dataset_name=dataset(shop_id), node_set=[f"customer:{customer_id}"]
        )
        if getattr(r, "status", "completed") != "completed":
            raise RuntimeError(f"Cognee could not remember it: {r.error}")
        if not r.dataset_id:
            return None
        # Its result lists every item in the dataset, and its content_hash is
        # the first item's, not ours (a second note took the first's id on 1
        # Oct, and forgetting it removed the wrong one). Cognee keys a text by
        # the MD5 of its words: ours is the item with that hash, or none.
        ours = hashlib.md5(text.encode("utf-8")).hexdigest()
        rows = await cognee.datasets.list_data(UUID(str(r.dataset_id)))
        found = [d for d in rows if d.content_hash == ours]
        return str(found[-1].id) if found else None

    def recall(self, shop_id: str, question: str) -> str:
        return self._run(self._recall(shop_id, question), RECALL_S)

    async def _recall(self, shop_id: str, question: str) -> str:
        cognee = await self._import()
        try:
            found = await cognee.recall(
                question, datasets=[dataset(shop_id)], only_context=True
            )
        except Exception as e:  # noqa: BLE001 - nothing remembered yet is not an error
            if "not found" in str(e).lower() or "NotFound" in type(e).__name__:
                return ""
            raise
        text = "\n".join(str(getattr(r, "text", r)) for r in found or [])
        return text[:RECALLED_CHARS]

    def forget(self, shop_id: str, cognee_id: str) -> None:
        self._run(self._forget(shop_id, cognee_id), FORGET_S)

    async def _forget(self, shop_id: str, cognee_id: str) -> None:
        cognee = await self._import()
        await cognee.forget(data_id=UUID(cognee_id), dataset=dataset(shop_id))

    def wipe(self) -> None:
        """Empties the whole memory. Only a check database may be wiped."""
        if not self._url.rstrip("/").endswith("_check"):
            raise RuntimeError("only a *_check memory database can be wiped")
        self._run(self._wipe(), FORGET_S)

    async def _wipe(self) -> None:
        cognee = await self._import()
        await cognee.prune.prune_data()
        await cognee.prune.prune_system(metadata=True)


_memory: Memory | None = None
_faked: Memory | None = None
_memory_lock = threading.Lock()


def get() -> Memory | None:
    """The memory, or None when it is off (settings.enabled)."""
    global _memory
    if _faked is not None:
        return _faked
    if not settings.enabled():
        return None
    with _memory_lock:
        if _memory is None:
            url = settings.url()
            assert url is not None
            _memory = Cognee(url)
        return _memory


def use(memory: Memory | None) -> None:
    """Tests: put a fake memory in, or None to take it out."""
    global _faked
    _faked = memory
