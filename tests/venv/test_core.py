import json
import os
import re
import subprocess
import sys
import time

import pytest

from hatch.utils.structures import EnvVars
from hatch.venv.core import VirtualEnv, locked_file


def test_initialization_does_not_create(temp_dir, platform):
    venv_dir = temp_dir / "venv"
    venv = VirtualEnv(venv_dir, platform)

    assert not venv.exists()

    with pytest.raises(OSError, match=f"Unable to locate executables directory within: {re.escape(str(venv_dir))}"):
        _ = venv.executables_directory


def test_remove_non_existent_no_error(temp_dir, platform):
    venv_dir = temp_dir / "venv"
    venv = VirtualEnv(venv_dir, platform)
    venv.remove()


def test_creation(temp_dir, platform):
    venv_dir = temp_dir / "venv"
    venv = VirtualEnv(venv_dir, platform)
    venv.create(sys.executable)

    assert venv_dir.is_dir()
    assert venv.exists()


def test_executables_directory(temp_dir, platform):
    venv_dir = temp_dir / "venv"
    venv = VirtualEnv(venv_dir, platform)
    venv.create(sys.executable)

    assert venv.executables_directory.is_dir()
    for entry in venv.executables_directory.iterdir():
        if entry.name.startswith("py"):
            break
    else:  # no cov
        msg = "Unable to locate Python executable"
        raise AssertionError(msg)


def test_activation(temp_dir, platform):
    venv_dir = temp_dir / "venv"
    venv = VirtualEnv(venv_dir, platform)
    venv.create(sys.executable)

    with EnvVars(exclude=VirtualEnv.IGNORED_ENV_VARS):
        os.environ["PATH"] = str(temp_dir)
        os.environ["VIRTUAL_ENV"] = "foo"
        for env_var in VirtualEnv.IGNORED_ENV_VARS:
            os.environ[env_var] = "foo"

        venv.activate()

        assert os.environ["PATH"] == f"{venv.executables_directory}{os.pathsep}{temp_dir}"
        assert os.environ["VIRTUAL_ENV"] == str(venv_dir)
        for env_var in VirtualEnv.IGNORED_ENV_VARS:
            assert env_var not in os.environ

        venv.deactivate()

        assert os.environ["PATH"] == str(temp_dir)
        assert os.environ["VIRTUAL_ENV"] == "foo"
        for env_var in VirtualEnv.IGNORED_ENV_VARS:
            assert os.environ[env_var] == "foo"


def test_activation_path_env_var_missing(temp_dir, platform):
    venv_dir = temp_dir / "venv"
    venv = VirtualEnv(venv_dir, platform)
    venv.create(sys.executable)

    with EnvVars(exclude=VirtualEnv.IGNORED_ENV_VARS):
        os.environ.pop("PATH", None)
        os.environ["VIRTUAL_ENV"] = "foo"
        for env_var in VirtualEnv.IGNORED_ENV_VARS:
            os.environ[env_var] = "foo"

        venv.activate()

        assert os.environ["PATH"] == f"{venv.executables_directory}{os.pathsep}{os.defpath}"
        assert os.environ["VIRTUAL_ENV"] == str(venv_dir)
        for env_var in VirtualEnv.IGNORED_ENV_VARS:
            assert env_var not in os.environ

        venv.deactivate()

        assert "PATH" not in os.environ
        assert os.environ["VIRTUAL_ENV"] == "foo"
        for env_var in VirtualEnv.IGNORED_ENV_VARS:
            assert os.environ[env_var] == "foo"


def test_context_manager(temp_dir, platform, extract_installed_requirements):
    venv_dir = temp_dir / "venv"
    venv = VirtualEnv(venv_dir, platform)
    venv.create(sys.executable)

    with EnvVars(exclude=VirtualEnv.IGNORED_ENV_VARS):
        os.environ["PATH"] = str(temp_dir)
        os.environ["VIRTUAL_ENV"] = "foo"
        for env_var in VirtualEnv.IGNORED_ENV_VARS:
            os.environ[env_var] = "foo"

        with venv:
            assert os.environ["PATH"] == f"{venv.executables_directory}{os.pathsep}{temp_dir}"
            assert os.environ["VIRTUAL_ENV"] == str(venv_dir)
            for env_var in VirtualEnv.IGNORED_ENV_VARS:
                assert env_var not in os.environ

            # Run here while we have cleanup
            output = platform.run_command(["pip", "freeze"], check=True, capture_output=True).stdout.decode("utf-8")
            assert not extract_installed_requirements(output.splitlines())

        assert os.environ["PATH"] == str(temp_dir)
        assert os.environ["VIRTUAL_ENV"] == "foo"
        for env_var in VirtualEnv.IGNORED_ENV_VARS:
            assert os.environ[env_var] == "foo"


def test_creation_allow_system_packages(temp_dir, platform, extract_installed_requirements):
    venv_dir = temp_dir / "venv"
    venv = VirtualEnv(venv_dir, platform)
    venv.create(sys.executable, allow_system_packages=True)

    with venv:
        output = platform.run_command(["pip", "freeze"], check=True, capture_output=True).stdout.decode("utf-8")

        assert len(extract_installed_requirements(output.splitlines())) > 0


def test_python_data(temp_dir, platform):
    venv_dir = temp_dir / "venv"
    venv = VirtualEnv(venv_dir, platform)
    venv.create(sys.executable)

    with venv:
        output = platform.run_command(
            ["python", "-W", "ignore", "-"],
            check=True,
            capture_output=True,
            input=b"import json,sys;print(json.dumps([path for path in sys.path if path]))",
        ).stdout.decode("utf-8")

        assert venv.environment is venv.environment
        assert venv.sys_path is venv.sys_path

        assert venv.environment["sys_platform"] == sys.platform
        assert venv.sys_path == json.loads(output)


def test_is_proper(temp_dir, platform):
    venv_dir = temp_dir / "venv"
    venv = VirtualEnv(venv_dir, platform)

    assert venv.is_proper() is False

    venv_dir.mkdir()
    assert venv.is_proper() is False

    (venv_dir / "pyvenv.cfg").touch()
    assert venv.is_proper() is False

    venv.remove()
    venv.create(sys.executable)
    assert venv.is_proper() is True


def test_creation_transaction_success(temp_dir, platform):
    venv_dir = temp_dir / "venv"
    venv = VirtualEnv(venv_dir, platform)

    with venv.creation_transaction() as proceed:
        assert proceed is True
        assert venv.marker_path.is_file()
        venv.create(sys.executable)

    assert venv.is_proper()
    assert not venv.marker_path.exists()
    assert not venv.backup_path.exists()


def test_creation_transaction_failure_removes_partial(temp_dir, platform):
    venv_dir = temp_dir / "venv"
    venv = VirtualEnv(venv_dir, platform)

    def fail():
        venv_dir.mkdir()
        (venv_dir / "partial").touch()
        raise RuntimeError

    with pytest.raises(RuntimeError), venv.creation_transaction():
        fail()

    assert not venv_dir.exists()
    assert not venv.marker_path.exists()
    assert not venv.backup_path.exists()


def test_creation_transaction_failure_restores_backup(temp_dir, platform):
    venv_dir = temp_dir / "venv"
    venv = VirtualEnv(venv_dir, platform)
    venv.create(sys.executable)

    with venv:
        platform.check_command([sys.executable, "-c", "import sys"])

    def fail():
        assert venv.backup_path.is_dir()
        assert not venv_dir.exists()

        venv_dir.mkdir()
        (venv_dir / "partial").touch()
        raise RuntimeError

    with pytest.raises(RuntimeError), venv.creation_transaction(replace_existing=True):
        fail()

    # The last known good environment was restored and still works
    assert venv.is_proper()
    assert not venv.marker_path.exists()
    assert not venv.backup_path.exists()

    with venv:
        platform.check_command(["python", "-c", "import sys"])


def test_creation_transaction_replace_existing_success(temp_dir, platform):
    venv_dir = temp_dir / "venv"
    venv = VirtualEnv(venv_dir, platform)
    venv.create(sys.executable)

    with venv.creation_transaction(replace_existing=True) as proceed:
        assert proceed is True
        assert venv.backup_path.is_dir()
        venv.create(sys.executable)

    assert venv.is_proper()
    assert not venv.marker_path.exists()
    assert not venv.backup_path.exists()


def test_creation_transaction_reuses_proper_environment(temp_dir, platform):
    venv_dir = temp_dir / "venv"
    venv = VirtualEnv(venv_dir, platform)
    venv.create(sys.executable)

    with venv.creation_transaction() as proceed:
        assert proceed is False

    assert not venv.marker_path.exists()
    assert not venv.backup_path.exists()


def test_creation_transaction_keep_env_preserves_partial(temp_dir, platform):
    venv_dir = temp_dir / "venv"
    venv = VirtualEnv(venv_dir, platform)

    def fail():
        venv_dir.mkdir()
        (venv_dir / "partial").touch()
        raise RuntimeError

    with pytest.raises(RuntimeError), venv.creation_transaction(keep_env=True):
        fail()

    assert venv_dir.is_dir()
    assert (venv_dir / "partial").is_file()
    assert not venv.marker_path.exists()
    assert not venv.backup_path.exists()


def test_creation_transaction_keyboard_interrupt_removes_partial(temp_dir, platform):
    venv_dir = temp_dir / "venv"
    venv = VirtualEnv(venv_dir, platform)

    def interrupt():
        venv_dir.mkdir()
        (venv_dir / "partial").touch()
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt), venv.creation_transaction():
        interrupt()

    assert not venv_dir.exists()
    assert not venv.marker_path.exists()


def test_creation_transaction_removes_unmarked_partial_directory(temp_dir, platform):
    venv_dir = temp_dir / "venv"
    venv = VirtualEnv(venv_dir, platform)
    venv_dir.mkdir()
    (venv_dir / "garbage").touch()

    with venv.creation_transaction() as proceed:
        assert proceed is True
        assert not venv_dir.exists()
        venv.create(sys.executable)

    assert venv.is_proper()


def test_recover_removes_interrupted_fresh_creation(temp_dir, platform):
    venv_dir = temp_dir / "venv"
    venv = VirtualEnv(venv_dir, platform)
    venv_dir.mkdir()
    (venv_dir / "partial").touch()
    venv.marker_path.write_text("{}")

    venv.recover_interrupted()

    assert not venv_dir.exists()
    assert not venv.marker_path.exists()
    assert not venv.backup_path.exists()


def test_recover_restores_interrupted_replacement(temp_dir, platform):
    venv_dir = temp_dir / "venv"
    venv = VirtualEnv(venv_dir, platform)

    # Simulate a complete environment parked as the backup during a replacement
    backup = VirtualEnv(venv.backup_path, platform)
    backup.create(sys.executable)

    venv_dir.mkdir()
    (venv_dir / "partial").touch()
    venv.marker_path.write_text("{}")

    venv.recover_interrupted()

    assert venv.is_proper()
    assert not venv.marker_path.exists()
    assert not venv.backup_path.exists()

    with venv:
        platform.check_command(["python", "-c", "import sys"])


def test_recover_removes_marker_of_completed_environment(temp_dir, platform):
    venv_dir = temp_dir / "venv"
    venv = VirtualEnv(venv_dir, platform)
    venv.create(sys.executable)
    venv.marker_path.write_text("{}")

    venv.recover_interrupted()

    assert venv.is_proper()
    assert not venv.marker_path.exists()


def test_recover_restores_orphan_backup_without_target(temp_dir, platform):
    venv_dir = temp_dir / "venv"
    venv = VirtualEnv(venv_dir, platform)

    backup = VirtualEnv(venv.backup_path, platform)
    backup.create(sys.executable)

    venv.recover_interrupted()

    assert venv.is_proper()
    assert not venv.backup_path.exists()

    with venv:
        platform.check_command(["python", "-c", "import sys"])


def test_recover_removes_orphan_backup_with_proper_target(temp_dir, platform):
    venv_dir = temp_dir / "venv"
    venv = VirtualEnv(venv_dir, platform)
    venv.create(sys.executable)

    backup = VirtualEnv(venv.backup_path, platform)
    backup.create(sys.executable)

    venv.recover_interrupted()

    assert venv.is_proper()
    assert not venv.backup_path.exists()


def test_recover_does_not_touch_unmarked_unrelated_directory(temp_dir, platform):
    venv_dir = temp_dir / "venv"
    venv = VirtualEnv(venv_dir, platform)
    venv_dir.mkdir()
    marker_file = venv_dir / "unrelated"
    marker_file.touch()

    venv.recover_interrupted()

    assert marker_file.is_file()
    assert not venv.marker_path.exists()
    assert not venv.backup_path.exists()


def test_remove_cleans_up_artifacts(temp_dir, platform):
    venv_dir = temp_dir / "venv"
    venv = VirtualEnv(venv_dir, platform)
    venv.create(sys.executable)
    venv.marker_path.write_text("{}")

    backup = VirtualEnv(venv.backup_path, platform)
    backup.create(sys.executable)

    venv.lock_path.touch()

    venv.remove()

    assert not venv_dir.exists()
    assert not venv.marker_path.exists()
    assert not venv.backup_path.exists()
    assert not venv.lock_path.exists()


def test_locked_file_is_reentrant(temp_dir):
    lock_path = temp_dir / "env.lock"

    with locked_file(lock_path), locked_file(lock_path):
        assert lock_path.is_file()

    # Fully released: it can be acquired again by the same process
    with locked_file(lock_path):
        assert lock_path.is_file()


def test_creation_transaction_serializes_processes(temp_dir, platform):
    venv_dir = temp_dir / "venv"
    venv = VirtualEnv(venv_dir, platform)

    script = """\
import sys
import time
from hatch.utils.fs import Path
from hatch.utils.platform import Platform
from hatch.venv.core import VirtualEnv

venv = VirtualEnv(Path(sys.argv[1]), Platform())
with venv.creation_transaction():
    time.sleep(3)
"""

    process = subprocess.Popen([sys.executable, "-c", script, str(venv_dir)])
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and not venv.marker_path.is_file():
            if process.poll() is not None:
                pytest.fail("helper process exited before acquiring the lock")

            time.sleep(0.05)

        assert venv.marker_path.is_file()

        start = time.monotonic()
        with locked_file(venv.lock_path):
            elapsed = time.monotonic() - start

        assert elapsed >= 2
    finally:
        process.wait(timeout=30)

    assert process.returncode == 0
    assert not venv.marker_path.exists()
    assert not venv_dir.exists()
