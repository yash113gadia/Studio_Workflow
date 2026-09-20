"""Serialize Creator renders and hold the heavy-GPU lease with a live heartbeat."""
from functools import wraps
from contextlib import contextmanager
import threading
import uuid
from app.core.gpu_lease import GPULeaseManager
from app.core.config import settings

_lock = threading.Lock()


@contextmanager
def gpu_render_lease(owner_prefix: str):
    """Hold the process render lock and database GPU lease with a heartbeat."""
    if not _lock.acquire(blocking=False):
        raise RuntimeError("A heavy GPU render is already running. Wait for it to finish.")
    token = None
    stop = threading.Event()
    thread = None
    try:
        ok, token, message = GPULeaseManager.acquire(owner_prefix + "_" + uuid.uuid4().hex)
        if not ok:
            raise RuntimeError(message)

        def heartbeat():
            while not stop.wait(settings.gpu_lease.heartbeat_interval_seconds):
                GPULeaseManager.heartbeat(token)

        thread = threading.Thread(target=heartbeat, daemon=True)
        thread.start()
        yield
    finally:
        stop.set()
        if thread:
            thread.join(timeout=10)
        if token:
            GPULeaseManager.release(token)
        _lock.release()


def exclusive_render(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        mock = kwargs.get('mock_mode', args[2] if len(args) > 2 else False)
        if mock:
            if not _lock.acquire(blocking=False):
                raise RuntimeError('A Creator render is already running. Wait for it to finish.')
            try:
                return func(*args, **kwargs)
            finally:
                _lock.release()
        with gpu_render_lease("creator"):
            return func(*args, **kwargs)
    return wrapper
