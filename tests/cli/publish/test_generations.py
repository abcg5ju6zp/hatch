import os

import pytest

from hatch.publish.index import IndexPublisher, iter_planned_artifacts, select_generation_artifacts
from hatchling.builders import staging


@pytest.fixture
def publisher(temp_dir_cache):
    return IndexPublisher(None, temp_dir_cache, temp_dir_cache / "cache" / "index", {}, {})


def commit_generation(build_directory, session, generation, names):
    artifacts = staging.begin_generation(
        str(build_directory), generation=generation, session=session, targets=list(names)
    )
    for name in names:
        with open(os.path.join(artifacts, name), "wb") as f:
            f.write(f"contents of {name}".encode())
        staging.write_build_record(
            str(build_directory),
            generation,
            name,
            project="app",
            version="1.0",
            artifact_paths=[os.path.join(artifacts, name)],
        )
    staging.commit_generation(str(build_directory), generation)


class TestSelection:
    def test_plain_directory_without_generations(self, temp_dir):
        build_directory = temp_dir / "dist"
        build_directory.mkdir()
        (build_directory / "app-1.0.tar.gz").touch()

        assert select_generation_artifacts(build_directory) is None

    def test_missing_directory(self, temp_dir):
        assert select_generation_artifacts(temp_dir / "dist") is None

    def test_latest_session_selected(self, temp_dir):
        build_directory = temp_dir / "dist"
        commit_generation(build_directory, "session-1", "gen-a", ("app-1.0.tar.gz", "app-1.0.whl"))
        commit_generation(build_directory, "session-2", "gen-b", ("app-2.0.tar.gz",))
        commit_generation(build_directory, "session-2", "gen-c", ("app-2.0.whl",))

        plan = select_generation_artifacts(build_directory)
        assert plan == [
            ("gen-b", ["app-2.0.tar.gz"]),
            ("gen-c", ["app-2.0.whl"]),
        ]

        artifacts = [path.name for path in iter_planned_artifacts(build_directory, plan)]
        assert artifacts == ["app-2.0.tar.gz", "app-2.0.whl"]

    def test_old_artifacts_are_not_selected(self, temp_dir):
        build_directory = temp_dir / "dist"
        commit_generation(build_directory, "session-1", "gen-a", ("app-1.0.tar.gz", "app-1.0.whl"))
        commit_generation(build_directory, "session-2", "gen-b", ("app-2.0.tar.gz", "app-2.0.whl"))

        plan = select_generation_artifacts(build_directory)
        selected = {name for _generation, names in plan for name in names}
        assert selected == {"app-2.0.tar.gz", "app-2.0.whl"}


class TestPublishedState:
    def test_no_state_initially(self, publisher):
        assert publisher.read_published_generations() == {}

    def test_marks_generation_published_per_repo(self, publisher):
        publisher.mark_generation_published("gen-1", "https://repo.example")
        publisher.mark_generation_published("gen-2", "https://other.example")
        publisher.mark_generation_published("gen-1", "https://repo.example")  # idempotent

        state = publisher.read_published_generations()
        assert state == {
            "https://repo.example": ["gen-1"],
            "https://other.example": ["gen-2"],
        }

    def test_filter_published(self, publisher):
        publisher.mark_generation_published("gen-1", "https://repo.example")
        plan = [("gen-1", ["app-1.0.tar.gz"]), ("gen-2", ["app-2.0.tar.gz"])]

        assert publisher.filter_published_generations(plan, "https://repo.example") == [
            ("gen-2", ["app-2.0.tar.gz"])
        ]
        # A different repository has not seen either generation
        assert publisher.filter_published_generations(plan, "https://other.example") == plan

    def test_mark_complete_only_after_every_artifact(self, publisher):
        plan = [("gen-1", ["a.tar.gz", "b.whl"])]

        publisher.mark_generation_complete_if_done("gen-1", plan, {"a.tar.gz"}, "https://repo.example")
        assert publisher.read_published_generations() == {}

        publisher.mark_generation_complete_if_done(
            "gen-1", plan, {"a.tar.gz", "b.whl"}, "https://repo.example"
        )
        assert publisher.read_published_generations() == {"https://repo.example": ["gen-1"]}

    def test_same_confirmed_generation_is_not_uploaded_twice(self, temp_dir, publisher):
        build_directory = temp_dir / "dist"
        commit_generation(build_directory, "session-1", "gen-1", ("app-1.0.tar.gz", "app-1.0.whl"))

        plan = select_generation_artifacts(build_directory)
        publisher.mark_generation_published("gen-1", "https://repo.example")

        # The second publish attempt has nothing eligible for that repository
        assert publisher.filter_published_generations(plan, "https://repo.example") == []
