from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

import pytest

from hatchling.builders.sdist import SdistBuilder
from hatchling.builders.wheel import WheelBuilder
from hatchling.metadata.core import ProjectMetadata
from hatchling.plugin.manager import PluginManager
from hatchling.version.generation import (
    STATIC_SOURCE,
    GenerationStore,
    VersionCoordinator,
    VersionGeneration,
)

if TYPE_CHECKING:
    from hatch.utils.fs import Path


STATIC_CONFIG = """\
[project]
name = "my-app"
version = "0.1.0"

[tool.hatch.build.targets.wheel]
packages = ["my_app"]
"""

REGEX_CONFIG = """\
[project]
name = "my-app"
dynamic = ["version"]

[tool.hatch.version]
path = "my_app/__about__.py"

[tool.hatch.build.targets.wheel]
packages = ["my_app"]
"""


def setup_project(path: Path, config: str, *, version: str | None = None) -> None:
    package_dir = path / "my_app"
    package_dir.mkdir(parents=True, exist_ok=True)
    package_dir.joinpath("__init__.py").touch()

    about = package_dir.joinpath("__about__.py")
    about.write_text(f'__version__ = {version!r}\n' if version is not None else "")

    path.joinpath("pyproject.toml").write_text(textwrap.dedent(config))


class TestVersionGeneration:
    def test_equality(self):
        first = VersionGeneration("0.1.0", "0.1.0", STATIC_SOURCE)
        second = VersionGeneration("0.1.0", "0.1.0", STATIC_SOURCE)
        third = VersionGeneration("0.2.0", "0.2.0", STATIC_SOURCE)

        assert first == second
        assert first != third

    def test_serialization_round_trip(self):
        generation = VersionGeneration("0.1.0", "0.1.0", "regex", "standard")

        assert VersionGeneration.from_dict(generation.to_dict()) == generation

    def test_prepare_commit(self, temp_dir):
        setup_project(temp_dir, STATIC_CONFIG)
        metadata = ProjectMetadata(str(temp_dir), PluginManager())

        candidate = metadata.prepare_version()
        assert candidate.version == "0.1.0"
        assert candidate.source_name == STATIC_SOURCE

        metadata.commit_version(candidate)

        assert metadata.version == "0.1.0"
        assert metadata.original_version == "0.1.0"


class TestBuilds:
    def test_static_version_commits_generation(self, temp_dir):
        setup_project(temp_dir, STATIC_CONFIG)
        builder = WheelBuilder(str(temp_dir))

        artifacts = list(builder.build())

        assert len(artifacts) == 1
        assert artifacts[0].endswith("my_app-0.1.0-py2.py3-none-any.whl")

        state = GenerationStore(str(temp_dir), str(temp_dir / "dist")).load()
        assert state["committed"]["version"] == "0.1.0"
        assert state["committed"]["source_name"] == STATIC_SOURCE
        assert state["candidate"] is None
        assert state["artifacts"] == ["my_app-0.1.0-py2.py3-none-any.whl"]

    def test_dynamic_version_regex_source(self, temp_dir):
        setup_project(temp_dir, REGEX_CONFIG, version="0.2.0")
        builder = WheelBuilder(str(temp_dir))

        artifacts = list(builder.build())

        assert len(artifacts) == 1
        assert artifacts[0].endswith("my_app-0.2.0-py2.py3-none-any.whl")

        state = GenerationStore(str(temp_dir), str(temp_dir / "dist")).load()
        assert state["committed"]["version"] == "0.2.0"
        assert state["committed"]["original_version"] == "0.2.0"
        assert state["committed"]["source_name"] == "regex"
        assert state["committed"]["scheme_name"] == "standard"
        assert state["candidate"] is None

    def test_switching_generation_removes_stale_wheel(self, temp_dir):
        setup_project(temp_dir, REGEX_CONFIG, version="0.1.0")
        list(WheelBuilder(str(temp_dir)).build())

        dist = temp_dir / "dist"
        assert len(list(dist.glob("*.whl"))) == 1

        # Switch the version source to a new generation
        temp_dir.joinpath("my_app", "__about__.py").write_text('__version__ = "0.2.0"\n')
        list(WheelBuilder(str(temp_dir)).build())

        wheels = [path.name for path in dist.glob("*.whl")]
        assert wheels == ["my_app-0.2.0-py2.py3-none-any.whl"]

    def test_switching_generation_removes_stale_sdist(self, temp_dir):
        setup_project(temp_dir, REGEX_CONFIG, version="0.1.0")
        list(SdistBuilder(str(temp_dir)).build())

        dist = temp_dir / "dist"
        assert len(list(dist.glob("*.tar.gz"))) == 1

        temp_dir.joinpath("my_app", "__about__.py").write_text('__version__ = "0.2.0"\n')
        list(SdistBuilder(str(temp_dir)).build())

        sdists = [path.name for path in dist.glob("*.tar.gz")]
        assert sdists == ["my_app-0.2.0.tar.gz"]

    def test_unchanged_version_cache_hit(self, temp_dir):
        setup_project(temp_dir, REGEX_CONFIG, version="0.1.0")

        list(WheelBuilder(str(temp_dir)).build())
        list(WheelBuilder(str(temp_dir)).build())

        dist = temp_dir / "dist"
        wheels = [path.name for path in dist.glob("*.whl")]
        assert wheels == ["my_app-0.1.0-py2.py3-none-any.whl"]

        state = GenerationStore(str(temp_dir), str(dist)).load()
        assert state["committed"]["version"] == "0.1.0"
        assert state["candidate"] is None

    def test_sdist_and_wheel_share_generation(self, temp_dir):
        setup_project(temp_dir, REGEX_CONFIG, version="0.3.0")

        list(SdistBuilder(str(temp_dir)).build())
        list(WheelBuilder(str(temp_dir)).build())

        dist = temp_dir / "dist"
        assert sorted(path.name for path in dist.iterdir() if path.suffix in {".gz", ".whl"}) == [
            "my_app-0.3.0-py2.py3-none-any.whl",
            "my_app-0.3.0.tar.gz",
        ]

        state = GenerationStore(str(temp_dir), str(dist)).load()
        assert state["committed"]["version"] == "0.3.0"
        assert sorted(state["artifacts"]) == [
            "my_app-0.3.0-py2.py3-none-any.whl",
            "my_app-0.3.0.tar.gz",
        ]

    def test_metadata_records_resolved_version(self, temp_dir):
        setup_project(temp_dir, REGEX_CONFIG, version="0.2.0")
        builder = WheelBuilder(str(temp_dir))
        list(builder.build())

        metadata_file = builder.config.core_metadata_constructor(builder.metadata)
        assert "Version: 0.2.0\n" in metadata_file
        assert "Dynamic: version" not in metadata_file


class TestFailures:
    def test_unknown_source_falls_back_to_last_metadata(self, temp_dir):
        setup_project(temp_dir, REGEX_CONFIG, version="0.1.0")
        list(WheelBuilder(str(temp_dir)).build())

        temp_dir.joinpath("pyproject.toml").write_text(textwrap.dedent("""\
            [project]
            name = "my-app"
            dynamic = ["version"]

            [tool.hatch.version]
            source = "does-not-exist"

            [tool.hatch.build.targets.wheel]
            packages = ["my_app"]
        """))

        with pytest.raises(Exception, match="Unknown version source"):
            list(WheelBuilder(str(temp_dir)).build())

        dist = temp_dir / "dist"
        assert [path.name for path in dist.glob("*.whl")] == [
            "my_app-0.1.0-py2.py3-none-any.whl"
        ]

        state = GenerationStore(str(temp_dir), str(dist)).load()
        assert state["committed"]["version"] == "0.1.0"
        assert state["candidate"] is None

    def test_source_unavailable_falls_back(self, temp_dir):
        setup_project(temp_dir, REGEX_CONFIG, version="0.1.0")
        list(WheelBuilder(str(temp_dir)).build())

        temp_dir.joinpath("pyproject.toml").write_text(textwrap.dedent("""\
            [project]
            name = "my-app"
            dynamic = ["version"]

            [tool.hatch.version]
            source = "env"
            variable = "MY_APP_VERSION"
        """))

        with pytest.raises(Exception, match="Error getting the version from source `env`"):
            list(WheelBuilder(str(temp_dir)).build())

        dist = temp_dir / "dist"
        state = GenerationStore(str(temp_dir), str(dist)).load()
        assert state["committed"]["version"] == "0.1.0"
        assert state["candidate"] is None
        assert [path.name for path in dist.glob("*.whl")] == [
            "my_app-0.1.0-py2.py3-none-any.whl"
        ]

    def test_dirty_source_check_keeps_previous_metadata(self, temp_dir):
        setup_project(temp_dir, REGEX_CONFIG, version="0.1.0")
        list(WheelBuilder(str(temp_dir)).build())

        # A version source (e.g. a VCS source) refuses to resolve dirty sources
        dirty_script = temp_dir.joinpath("dirty.py")
        dirty_script.write_text('raise RuntimeError("the source tree is dirty")\n')

        temp_dir.joinpath("pyproject.toml").write_text(textwrap.dedent("""\
            [project]
            name = "my-app"
            dynamic = ["version"]

            [tool.hatch.version]
            source = "code"
            path = "dirty.py"
        """))

        with pytest.raises(Exception, match="the source tree is dirty"):
            list(WheelBuilder(str(temp_dir)).build())

        dist = temp_dir / "dist"
        state = GenerationStore(str(temp_dir), str(dist)).load()
        assert state["committed"]["version"] == "0.1.0"
        assert state["candidate"] is None

    def test_aborted_build_restores_previous_generation(self, temp_dir):
        setup_project(temp_dir, REGEX_CONFIG, version="0.1.0")
        list(WheelBuilder(str(temp_dir)).build())

        hook_dir = temp_dir.joinpath("hooks")
        hook_dir.mkdir()
        hook_dir.joinpath("hook.py").write_text(textwrap.dedent("""\
            from hatchling.builders.hooks.plugin.interface import BuildHookInterface


            class BadHook(BuildHookInterface):
                def initialize(self, version, build_data):
                    raise RuntimeError("VCS is unavailable")
        """))

        temp_dir.joinpath("pyproject.toml").write_text(textwrap.dedent("""\
            [project]
            name = "my-app"
            dynamic = ["version"]

            [tool.hatch.version]
            path = "my_app/__about__.py"

            [tool.hatch.build.targets.wheel]
            packages = ["my_app"]

            [tool.hatch.build.hooks.custom]
            path = "hooks/hook.py"
        """))
        temp_dir.joinpath("my_app", "__about__.py").write_text('__version__ = "0.2.0"\n')

        with pytest.raises(RuntimeError, match="VCS is unavailable"):
            list(WheelBuilder(str(temp_dir)).build())

        dist = temp_dir / "dist"
        assert [path.name for path in dist.glob("*.whl")] == [
            "my_app-0.1.0-py2.py3-none-any.whl"
        ]

        state = GenerationStore(str(temp_dir), str(dist)).load()
        assert state["committed"]["version"] == "0.1.0"
        assert state["candidate"] is None


class TestRecovery:
    def test_crash_recovery_purges_candidate(self, temp_dir):
        setup_project(temp_dir, REGEX_CONFIG, version="0.1.0")
        list(WheelBuilder(str(temp_dir)).build())

        dist = temp_dir / "dist"
        store = GenerationStore(str(temp_dir), str(dist))

        candidate = VersionGeneration("0.2.0", "0.2.0", "regex", "standard")
        state = store.load()
        store.save(
            committed=VersionGeneration.from_dict(state["committed"]),
            candidate=candidate,
            artifacts=state["artifacts"],
        )
        dist.joinpath("my_app-0.2.0-py2.py3-none-any.whl").touch()

        coordinator = VersionCoordinator(ProjectMetadata(str(temp_dir), PluginManager()), str(dist))
        coordinator.recover()

        assert not dist.joinpath("my_app-0.2.0-py2.py3-none-any.whl").exists()
        assert dist.joinpath("my_app-0.1.0-py2.py3-none-any.whl").exists()

        recovered = store.load()
        assert recovered["committed"]["version"] == "0.1.0"
        assert recovered["candidate"] is None

    def test_crash_recovery_same_version_keeps_artifacts(self, temp_dir):
        setup_project(temp_dir, REGEX_CONFIG, version="0.1.0")
        list(WheelBuilder(str(temp_dir)).build())

        dist = temp_dir / "dist"
        store = GenerationStore(str(temp_dir), str(dist))

        generation = VersionGeneration("0.1.0", "0.1.0", "regex", "standard")
        state = store.load()
        store.save(
            committed=generation,
            candidate=generation,
            artifacts=state["artifacts"],
        )

        coordinator = VersionCoordinator(ProjectMetadata(str(temp_dir), PluginManager()), str(dist))
        coordinator.recover()

        assert dist.joinpath("my_app-0.1.0-py2.py3-none-any.whl").exists()
        assert store.load()["candidate"] is None
