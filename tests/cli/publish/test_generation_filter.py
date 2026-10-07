from __future__ import annotations

from hatch.publish.index import get_committed_artifacts, recurse_artifacts
from hatchling.version.generation import GenerationStore, VersionGeneration


def test_no_state_is_unfiltered(temp_dir):
    directory = temp_dir / "dist"
    directory.mkdir()
    directory.joinpath("my_app-0.1.0-py3-none-any.whl").touch()

    assert get_committed_artifacts(temp_dir, directory) is None

    artifacts = [path.name for path in recurse_artifacts([str(directory)], temp_dir)]
    assert artifacts == ["my_app-0.1.0-py3-none-any.whl"]


def test_stale_artifacts_are_excluded(temp_dir):
    directory = temp_dir / "dist"
    directory.mkdir()

    current = "my_app-0.2.0-py3-none-any.whl"
    stale = "my_app-0.1.0-py3-none-any.whl"
    directory.joinpath(current).touch()
    directory.joinpath(stale).touch()

    generation = VersionGeneration("0.2.0", "0.2.0", "regex", "standard")
    GenerationStore(str(temp_dir), str(directory)).save(committed=generation, artifacts=[current])

    artifacts = [path.name for path in recurse_artifacts([str(directory)], temp_dir)]
    assert artifacts == [current]


def test_in_progress_switch_is_unfiltered(temp_dir):
    directory = temp_dir / "dist"
    directory.mkdir()

    current = "my_app-0.2.0-py3-none-any.whl"
    directory.joinpath(current).touch()

    generation = VersionGeneration("0.2.0", "0.2.0", "regex", "standard")
    candidate = VersionGeneration("0.3.0", "0.3.0", "regex", "standard")
    GenerationStore(str(temp_dir), str(directory)).save(
        committed=generation, candidate=candidate, artifacts=[current]
    )

    assert get_committed_artifacts(temp_dir, directory) is None


def test_empty_artifact_list_is_unfiltered(temp_dir):
    directory = temp_dir / "dist"
    directory.mkdir()

    generation = VersionGeneration("0.2.0", "0.2.0", "regex", "standard")
    GenerationStore(str(temp_dir), str(directory)).save(committed=generation)

    assert get_committed_artifacts(temp_dir, directory) is None
