"""Tiny thread-safe pub/sub so background jobs can stream progress to the browser (SSE) or the CLI."""
import asyncio
import threading
import time


class EventBus:
    def __init__(self):
        self._lock = threading.Lock()
        self._async = []      # (slug or None, loop, asyncio.Queue)
        self._callbacks = []  # (slug or None, fn)

    def publish(self, slug, event):
        event = dict(event, project=slug, ts=time.time())
        with self._lock:
            subs = list(self._async)
            cbs = list(self._callbacks)
        for s, loop, q in subs:
            if s in (None, slug):
                try:
                    loop.call_soon_threadsafe(q.put_nowait, event)
                except RuntimeError:
                    pass
        for s, fn in cbs:
            if s in (None, slug):
                try:
                    fn(event)
                except Exception:
                    pass

    def subscribe_async(self, slug=None):
        loop = asyncio.get_running_loop()
        q = asyncio.Queue(maxsize=1000)
        entry = (slug, loop, q)
        with self._lock:
            self._async.append(entry)
        return q, entry

    def unsubscribe_async(self, entry):
        with self._lock:
            if entry in self._async:
                self._async.remove(entry)

    def on(self, fn, slug=None):
        with self._lock:
            self._callbacks.append((slug, fn))
        return fn

    def off(self, fn):
        with self._lock:
            self._callbacks = [(s, f) for s, f in self._callbacks if f is not fn]


bus = EventBus()
