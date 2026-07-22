import asyncio


_SENTINEL = object()


class _WorkerError:

    __slots__ = ("exc",)

    def __init__(self, exc: BaseException):
        self.exc = exc


async def iter_in_thread(sync_gen):
    """
    Consume a blocking synchronous generator (e.g. one that makes
    blocking network calls to an LLM or TTS provider) without
    freezing the asyncio event loop.

    The generator is driven to completion on a worker thread.
    Each item it yields is handed back to the event loop through
    a thread-safe queue, so whatever else is running on the loop -
    most importantly, the websocket's `receive()` loop reading mic
    audio - keeps running the entire time the generator is
    blocked on network I/O.

    Cancellation (ResponseController.cancel()) still works exactly
    as before: it's checked *inside* the generator body, between
    chunks, same as when it ran directly on the loop. This only
    changes *where* the generator runs, not its logic.
    """

    loop = asyncio.get_running_loop()

    queue: asyncio.Queue = asyncio.Queue()

    def worker():

        try:

            for item in sync_gen:

                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    item,
                )

        except BaseException as exc:  # noqa: BLE001

            loop.call_soon_threadsafe(
                queue.put_nowait,
                _WorkerError(exc),
            )

        finally:

            loop.call_soon_threadsafe(
                queue.put_nowait,
                _SENTINEL,
            )

    loop.run_in_executor(None, worker)

    while True:

        item = await queue.get()

        if item is _SENTINEL:
            return

        if isinstance(item, _WorkerError):
            raise item.exc

        yield item
