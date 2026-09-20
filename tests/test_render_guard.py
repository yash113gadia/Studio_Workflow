import threading
from unittest.mock import patch
import pytest
from app.core.render_guard import exclusive_render


def test_render_guard_releases_lease_on_failure():
    @exclusive_render
    def render(*args, **kwargs):
        raise ValueError('render failed')
    with patch('app.core.render_guard.GPULeaseManager.acquire', return_value=(True, 'token', 'ok')), patch('app.core.render_guard.GPULeaseManager.release') as release:
        with pytest.raises(ValueError): render(mock_mode=False)
        release.assert_called_once_with('token')


def test_render_guard_rejects_overlapping_render():
    entered = threading.Event()
    finish = threading.Event()
    @exclusive_render
    def render(*args, **kwargs):
        entered.set()
        finish.wait(2)
    worker = threading.Thread(target=lambda: render(mock_mode=True))
    worker.start()
    try:
        assert entered.wait(1)
        with pytest.raises(RuntimeError, match='already running'):
            render(mock_mode=True)
    finally:
        finish.set()
        worker.join(2)
