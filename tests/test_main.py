from pathlib import Path

from main import acquire_instance_lock


class FakeLock:
    def __init__(self, path: str, *, succeeds: bool) -> None:
        self.path = path
        self.succeeds = succeeds
        self.timeout = None

    def tryLock(self, timeout: int) -> bool:
        self.timeout = timeout
        return self.succeeds


def test_acquire_instance_lock_returns_lock_when_available():
    created = []

    def factory(path: str):
        lock = FakeLock(path, succeeds=True)
        created.append(lock)
        return lock

    lock = acquire_instance_lock("tests", lock_factory=factory)

    assert lock is created[0]
    assert Path(lock.path).name == "FileGraph.lock"
    assert lock.timeout == 0


def test_acquire_instance_lock_returns_none_when_app_is_already_running():
    lock = acquire_instance_lock(
        "tests",
        lock_factory=lambda path: FakeLock(path, succeeds=False),
    )

    assert lock is None
