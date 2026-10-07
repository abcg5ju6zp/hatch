import json
import os
import sys
import tempfile
import threading
import time
from collections.abc import Generator
from contextlib import contextmanager, suppress
from tempfile import TemporaryDirectory

from hatch.env.utils import add_verbosity_flag
from hatch.utils.env import PythonInfo
from hatch.utils.fs import Path
from hatch.venv.utils import get_random_venv_name

# Acquisition depth per resolved lock file path for the current process. This emulates reentrant
# locking because neither POSIX flock locks nor Windows region locks can be acquired twice by the
# same process while the first acquisition is still held.
_held_locks: dict[str, int] = {}
_held_locks_guard = threading.Lock()


@contextmanager
def locked_file(path: Path) -> Generator[None, None, None]:
    """Cross-process exclusive lock backed by a file, with per-process reentrancy."""
    resolved_path = str(Path(path).resolve())

    with _held_locks_guard:
        depth = _held_locks.get(resolved_path, 0)
        _held_locks[resolved_path] = depth + 1

    if depth:
        try:
            yield
        finally:
            with _held_locks_guard:
                next_depth = depth - 1
                if next_depth:
                    _held_locks[resolved_path] = next_depth
                else:
                    _held_locks.pop(resolved_path, None)

        return

    Path(path).parent.ensure_dir_exists()

    try:
        with open(path, "a+b") as lock_file:
            if sys.platform == "win32":
                import msvcrt

                # The region to lock must contain at least one byte
                lock_file.seek(0, os.SEEK_END)
                if lock_file.tell() == 0:
                    lock_file.write(b"h")
                    lock_file.flush()

                lock_file.seek(0)

                # Poll because the blocking variant only retries for 10 seconds, which is less
                # than the time environment creation may take
                while True:
                    try:
                        msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                        break
                    except OSError:
                        time.sleep(0.2)

                try:
                    yield
                finally:
                    lock_file.seek(0)
                    with suppress(OSError):
                        msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)

                try:
                    yield
                finally:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
    finally:
        with _held_locks_guard:
            _held_locks.pop(resolved_path, None)


class VirtualEnv:
    IGNORED_ENV_VARS = ("__PYVENV_LAUNCHER__", "PYTHONHOME")

    def __init__(self, directory, platform, verbosity=0):
        self.directory = directory
        self.platform = platform
        self.verbosity = verbosity
        self.python_info = PythonInfo(platform)

        self._env_vars_to_restore = {}
        self._executables_directory = None

    def activate(self):
        self._env_vars_to_restore["VIRTUAL_ENV"] = os.environ.pop("VIRTUAL_ENV", None)
        os.environ["VIRTUAL_ENV"] = str(self.directory)

        old_path = os.environ.pop("PATH", None)
        self._env_vars_to_restore["PATH"] = old_path
        if old_path is None:
            os.environ["PATH"] = f"{self.executables_directory}{os.pathsep}{os.defpath}"
        else:
            os.environ["PATH"] = f"{self.executables_directory}{os.pathsep}{old_path}"

        for env_var in self.IGNORED_ENV_VARS:
            self._env_vars_to_restore[env_var] = os.environ.pop(env_var, None)

    def deactivate(self):
        for env_var, value in self._env_vars_to_restore.items():
            if value is None:
                os.environ.pop(env_var, None)
            else:
                os.environ[env_var] = value

        self._env_vars_to_restore.clear()

    def create(self, python, *, allow_system_packages=False):
        # WARNING: extremely slow import
        from virtualenv import cli_run

        self.directory.ensure_parent_dir_exists()

        command = [str(self.directory), "--no-download", "--no-periodic-update", "--python", python]

        if allow_system_packages:
            command.append("--system-site-packages")

        # Decrease verbosity since the virtualenv CLI defaults to something like +2 verbosity
        add_verbosity_flag(command, self.verbosity, adjustment=-1)

        cli_run(command)

    def remove(self):
        self.directory.remove()

        with suppress(OSError):
            self.marker_path.unlink(missing_ok=True)

        with suppress(OSError):
            self.backup_path.remove()

        with suppress(OSError):
            self.lock_path.unlink(missing_ok=True)

    def exists(self):
        return self.directory.is_dir()

    @property
    def marker_path(self) -> Path:
        return self.directory.parent / f".{self.directory.name}.creating"

    @property
    def backup_path(self) -> Path:
        return self.directory.parent / f".{self.directory.name}.backup"

    @property
    def lock_path(self) -> Path:
        # Keep the lock outside of the environment storage directory so that it does not interfere
        # with directory listings while being unique per resolved environment location
        resolved_directory = Path(self.directory).resolve()
        return Path(tempfile.gettempdir()) / f"hatch-env-{resolved_directory.long_id}.lock"

    def is_proper(self, directory=None) -> bool:
        """Indicate whether the directory contains what appears to be a usable virtual environment."""
        directory = self.directory if directory is None else Path(directory)

        if not directory.is_dir() or not (directory / "pyvenv.cfg").is_file():
            return False

        executables_directory = directory / ("Scripts" if self.platform.windows else "bin")

        if self.platform.windows and not executables_directory.is_dir():
            # PyPy
            executables_directory = directory / "bin"

        if not executables_directory.is_dir():
            return False

        candidates = ("python.exe", "pythonw.exe") if self.platform.windows else ("python", "python3")

        for candidate in candidates:
            if (executables_directory / candidate).exists():
                return True

        # Versioned interpreter links (e.g. python3.13) without the unversioned aliases
        return any(entry.is_file() or entry.is_symlink() for entry in executables_directory.glob("python3.*"))

    def recover_interrupted(self) -> None:
        """Restore a consistent state from a creation that ended abruptly during a previous run."""
        # Do not create anything when there is no trace of an environment, such as for incompatible
        # environments that have never been created
        if not self.directory.parent.is_dir():
            return

        if not (self.marker_path.is_file() or self.backup_path.is_dir() or self.directory.exists()):
            return

        with locked_file(self.lock_path):
            self._recover_interrupted()

    def _recover_interrupted(self) -> None:
        target = self.directory
        marker = self.marker_path
        backup = self.backup_path

        if marker.is_file():
            if backup.is_dir():
                # A replacement was interrupted: the target is the incomplete new environment and
                # the backup is the last known good environment, so restore the latter
                if target.exists():
                    target.remove()

                os.rename(backup, target)
            elif not self.is_proper():
                # A fresh creation was interrupted: the target is unusable, so discard it
                if target.exists():
                    target.remove()
            # Otherwise the creation finished but the marker removal was interrupted

            marker.unlink(missing_ok=True)
        elif backup.is_dir():
            if not target.exists() or not self.is_proper():
                if target.exists():
                    target.remove()

                os.rename(backup, target)
            else:
                # The replacement finished but the backup removal was interrupted
                backup.remove()

    def _write_marker(self) -> None:
        # The marker documents which process was creating the environment and when, solely for
        # diagnostic purposes; its mere presence (alongside the lock) drives recovery
        payload = json.dumps({"pid": os.getpid(), "time": time.time()})
        self.marker_path.write_atomic(payload, "w", encoding="utf-8")

    @contextmanager
    def creation_transaction(
        self, *, keep_env: bool = False, replace_existing: bool = False
    ) -> Generator[bool, None, None]:
        """
        Provide a consistent environment around creation at the final directory.

        The virtual environment is always built at its final location because absolute paths are
        baked into the created files (e.g. script shebangs), so it cannot be relocated afterwards.
        Any previously available environment is parked next to it and restored if creation fails.

        Yields whether creation should proceed. A value of ``False`` indicates that a usable
        environment already exists and, when ``replace_existing`` is not enabled, is reused.
        """
        self.directory.ensure_parent_dir_exists()

        with locked_file(self.lock_path):
            self._recover_interrupted()

            if self.is_proper():
                if not replace_existing:
                    yield False
                    return

                # Park the last known good environment so that it can be restored on failure
                os.rename(self.directory, self.backup_path)
            elif self.directory.exists():
                # An incomplete directory left behind without a marker or backup
                self.directory.remove()

            self._write_marker()

            try:
                yield True
            except BaseException:
                if not keep_env:
                    with suppress(OSError):
                        if self.directory.exists():
                            self.directory.remove()

                    if self.backup_path.is_dir():
                        os.rename(self.backup_path, self.directory)

                self.marker_path.unlink(missing_ok=True)
                raise
            else:
                # Declare the creation complete before discarding the backup so that an abrupt
                # termination cannot restore a partially removed backup
                self.marker_path.unlink(missing_ok=True)

                if self.backup_path.is_dir():
                    self.backup_path.remove()

    @property
    def executables_directory(self):
        if self._executables_directory is None:
            exe_dir = self.directory / ("Scripts" if self.platform.windows else "bin")
            if exe_dir.is_dir():
                self._executables_directory = exe_dir
            # PyPy
            elif self.platform.windows:
                exe_dir = self.directory / "bin"
                if exe_dir.is_dir():
                    self._executables_directory = exe_dir
                else:
                    msg = f"Unable to locate executables directory within: {self.directory}"
                    raise OSError(msg)
            # Debian
            elif (self.directory / "local").is_dir():  # no cov
                exe_dir = self.directory / "local" / "bin"
                if exe_dir.is_dir():
                    self._executables_directory = exe_dir
                else:
                    msg = f"Unable to locate executables directory within: {self.directory}"
                    raise OSError(msg)
            else:
                msg = f"Unable to locate executables directory within: {self.directory}"
                raise OSError(msg)

        return self._executables_directory

    @property
    def environment(self):
        return self.python_info.environment

    @property
    def sys_path(self):
        return self.python_info.sys_path

    def __enter__(self):
        self.activate()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.deactivate()


class TempVirtualEnv(VirtualEnv):
    def __init__(self, parent_python, platform, verbosity=0):
        self.parent_python = parent_python
        self.parent_dir = TemporaryDirectory()
        directory = Path(self.parent_dir.name).resolve() / get_random_venv_name()

        super().__init__(directory, platform, verbosity)

    def remove(self):
        super().remove()
        self.parent_dir.cleanup()

    def __enter__(self):
        self.create(self.parent_python)
        return super().__enter__()

    def __exit__(self, exc_type, exc_value, traceback):
        super().__exit__(exc_type, exc_value, traceback)
        self.remove()


class UVVirtualEnv(VirtualEnv):
    def create(self, python, *, allow_system_packages=False):
        command = [os.environ.get("HATCH_UV", "uv"), "venv", str(self.directory), "--python", python]
        if allow_system_packages:
            command.append("--system-site-packages")

        add_verbosity_flag(command, self.verbosity, adjustment=-1)
        self.platform.run_command(command)


class TempUVVirtualEnv(TempVirtualEnv, UVVirtualEnv): ...
