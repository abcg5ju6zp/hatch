import io
import json
import os
import tarfile
import zipfile

import pytest

from hatchling.builders import staging


def write_file(path, contents=b"artifact contents"):
    with open(path, "wb") as f:
        f.write(contents)
    return path


class TestLifecycle:
    def test_begin_creates_isolated_directories(self, temp_dir):
        final = str(temp_dir / "dist")
        artifacts = staging.begin_generation(
            final, generation="gen-1", session="session-1", targets=["sdist", "wheel"]
        )

        assert os.path.isdir(artifacts)
        manifest = staging.read_json(os.path.join(staging.pending_directory(final, "gen-1"), "manifest.json"))
        assert manifest["generation"] == "gen-1"
        assert manifest["session"] == "session-1"
        assert manifest["targets"] == ["sdist", "wheel"]

    def test_bookkeeping_lives_next_to_build_directory(self, temp_dir):
        final = str(temp_dir / "dist")
        staging.begin_generation(final, generation="gen-1", session="s", targets=["sdist"])

        assert not os.path.exists(os.path.join(final, ".hatch"))
        assert os.path.isdir(os.path.join(str(temp_dir), ".dist.hatch"))

    def test_begin_removes_unpublished_generations(self, temp_dir):
        final = str(temp_dir / "dist")
        artifacts = staging.begin_generation(final, generation="dead", session="s", targets=["sdist"])
        write_file(os.path.join(artifacts, "partial.whl"), b"partial")

        staging.begin_generation(final, generation="alive", session="s", targets=["sdist"])

        assert not os.path.exists(staging.pending_directory(final, "dead"))
        assert os.path.isdir(staging.pending_directory(final, "alive"))

    def test_abort_discards_generation(self, temp_dir):
        final = str(temp_dir / "dist")
        artifacts = staging.begin_generation(final, generation="gen-1", session="s", targets=["sdist"])
        write_file(os.path.join(artifacts, "x.tar.gz"))

        staging.abort_generation(final, "gen-1")

        assert not os.path.exists(staging.pending_directory(final, "gen-1"))


class TestCommit:
    def test_commits_validated_set(self, temp_dir):
        final = str(temp_dir / "dist")
        os.makedirs(final)
        write_file(os.path.join(final, "old.tar.gz"), b"old")
        artifacts = staging.begin_generation(final, generation="gen-1", session="s", targets=["sdist"])

        source = write_file(os.path.join(artifacts, "new-1.0.tar.gz"), b"new")
        staging.write_build_record(
            final,
            "gen-1",
            "sdist",
            project="new",
            version="1.0",
            artifact_paths=[source],
        )

        manifest = staging.commit_generation(final, "gen-1")

        assert os.path.isfile(os.path.join(final, "new-1.0.tar.gz"))
        assert not os.path.exists(staging.pending_directory(final, "gen-1"))
        confirmed = staging.read_json(staging.confirmed_manifest_path(final, "gen-1"))
        assert confirmed == manifest
        assert [a["name"] for a in manifest["artifacts"]] == ["new-1.0.tar.gz"]
        assert manifest["project"] == "new"
        assert manifest["version"] == "1.0"

    def test_build_directory_contains_only_artifacts(self, temp_dir):
        final = str(temp_dir / "dist")
        artifacts = staging.begin_generation(final, generation="gen-1", session="s", targets=["sdist"])
        write_file(os.path.join(artifacts, "app-1.0.tar.gz"))
        staging.write_build_record(
            final, "gen-1", "sdist", project="app", version="1.0", artifact_paths=[os.path.join(artifacts, "app-1.0.tar.gz")]
        )

        staging.commit_generation(final, "gen-1")

        assert sorted(os.listdir(final)) == ["app-1.0.tar.gz"]

    def test_failure_keeps_previous_set_intact(self, temp_dir):
        final = str(temp_dir / "dist")
        os.makedirs(final)
        write_file(os.path.join(final, "app-1.0.tar.gz"), b"complete old set")

        artifacts = staging.begin_generation(final, generation="gen-2", session="s", targets=["sdist"])
        write_file(os.path.join(artifacts, "app-2.0.tar.gz"), b"new")
        # Simulate a compression/hook failure: the record is missing entirely
        with pytest.raises(staging.StagingError, match="incomplete"):
            staging.commit_generation(final, "gen-2")

        assert os.path.isfile(os.path.join(final, "app-1.0.tar.gz"))
        assert not os.path.exists(os.path.join(final, "app-2.0.tar.gz"))
        assert not staging.iter_confirmed_manifests(final)

    def test_corrupted_artifact_rejected(self, temp_dir):
        final = str(temp_dir / "dist")
        os.makedirs(final)
        artifacts = staging.begin_generation(final, generation="gen-1", session="s", targets=["sdist"])
        source = write_file(os.path.join(artifacts, "app-1.0.tar.gz"), b"contents")
        staging.write_build_record(
            final, "gen-1", "sdist", project="app", version="1.0", artifact_paths=[source]
        )

        # Tamper with the artifact after it was recorded, keeping the size identical
        with open(source, "wb") as f:
            f.write(b"contenzs")

        with pytest.raises(staging.StagingError, match="hash mismatch"):
            staging.commit_generation(final, "gen-1")

        assert not os.path.exists(os.path.join(final, "app-1.0.tar.gz"))

    def test_unexpected_file_rejected(self, temp_dir):
        final = str(temp_dir / "dist")
        artifacts = staging.begin_generation(final, generation="gen-1", session="s", targets=["sdist"])
        source = write_file(os.path.join(artifacts, "app-1.0.tar.gz"))
        write_file(os.path.join(artifacts, "partial-2.0.whl"), b"leftover")
        staging.write_build_record(
            final, "gen-1", "sdist", project="app", version="1.0", artifact_paths=[source]
        )

        with pytest.raises(staging.StagingError, match="Unvalidated files"):
            staging.commit_generation(final, "gen-1")

    def test_empty_artifact_rejected(self, temp_dir):
        final = str(temp_dir / "dist")
        artifacts = staging.begin_generation(final, generation="gen-1", session="s", targets=["sdist"])
        source = write_file(os.path.join(artifacts, "app-1.0.tar.gz"), b"")
        staging.write_build_record(
            final, "gen-1", "sdist", project="app", version="1.0", artifact_paths=[source]
        )

        with pytest.raises(staging.StagingError, match="empty"):
            staging.commit_generation(final, "gen-1")

    def test_artifact_outside_staging_rejected(self, temp_dir):
        final = str(temp_dir / "dist")
        staging.begin_generation(final, generation="gen-1", session="s", targets=["sdist"])
        outside = write_file(str(temp_dir / "rogue.tar.gz"))

        with pytest.raises(staging.StagingError, match="isolated build directory"):
            staging.write_build_record(
                final, "gen-1", "sdist", project="app", version="1.0", artifact_paths=[outside]
            )

    def test_clean_rules_remove_old_versions(self, temp_dir):
        final = str(temp_dir / "dist")
        os.makedirs(final)
        write_file(os.path.join(final, "app-1.0.tar.gz"), b"old sdist")
        write_file(os.path.join(final, "app-1.0-py3-none-any.whl"), b"old wheel")
        write_file(os.path.join(final, "notes.txt"), b"keep me")

        artifacts = staging.begin_generation(final, generation="gen-2", session="s", targets=["sdist", "wheel"])
        sdist = write_file(os.path.join(artifacts, "app-2.0.tar.gz"), b"new sdist")
        wheel = write_file(os.path.join(artifacts, "app-2.0-py3-none-any.whl"), b"new wheel")
        staging.write_build_record(
            final, "gen-2", "sdist", project="app", version="2.0", artifact_paths=[sdist]
        )
        staging.write_build_record(
            final, "gen-2", "wheel", project="app", version="2.0", artifact_paths=[wheel]
        )

        manifest = staging.commit_generation(
            final,
            "gen-2",
            clean_rules={
                "sdist": {"suffixes": (".tar.gz",), "names": ()},
                "wheel": {"suffixes": (".whl",), "names": ()},
            },
        )

        committed = set(os.listdir(final))
        assert committed == {"app-2.0.tar.gz", "app-2.0-py3-none-any.whl", "notes.txt"}
        assert {a["name"] for a in manifest["artifacts"]} == committed - {"notes.txt"}

    def test_clean_rules_explicit_names_for_custom_targets(self, temp_dir):
        final = str(temp_dir / "dist")
        os.makedirs(final)
        write_file(os.path.join(final, "app-1.0.bin"), b"old custom")
        write_file(os.path.join(final, "app-1.0.tar.gz"), b"unrelated")

        artifacts = staging.begin_generation(final, generation="gen-2", session="s", targets=["custom"])
        binary = write_file(os.path.join(artifacts, "app-2.0.bin"), b"new custom")
        staging.write_build_record(
            final, "gen-2", "custom", project="app", version="2.0", artifact_paths=[binary]
        )

        staging.commit_generation(
            final, "gen-2", clean_rules={"custom": {"suffixes": (), "names": ("app-1.0.bin",)}}
        )

        assert set(os.listdir(final)) == {"app-2.0.bin", "app-1.0.tar.gz"}


class TestEmbeddedMetadata:
    @staticmethod
    def make_wheel(path, name, version):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr(
                "app-1.0.dist-info/METADATA",
                f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n",
            )
        with open(path, "wb") as f:
            f.write(buffer.getvalue())

    @staticmethod
    def make_sdist(path, name, version):
        with tarfile.open(path, "w:gz") as archive:
            contents = f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n".encode()
            info = tarfile.TarInfo("app-1.0/PKG-INFO")
            info.size = len(contents)
            archive.addfile(info, io.BytesIO(contents))

    def test_wheel_metadata_matches(self, temp_dir):
        final = str(temp_dir / "dist")
        artifacts = staging.begin_generation(final, generation="g", session="s", targets=["wheel"])
        path = os.path.join(artifacts, "app-1.0-py3-none-any.whl")
        self.make_wheel(path, "app", "1.0")
        staging.write_build_record(
            final, "g", "wheel", project="app", version="1.0", artifact_paths=[path]
        )

        staging.commit_generation(final, "g")

    def test_wheel_version_mismatch_rejected(self, temp_dir):
        final = str(temp_dir / "dist")
        artifacts = staging.begin_generation(final, generation="g", session="s", targets=["wheel"])
        path = os.path.join(artifacts, "app-2.0-py3-none-any.whl")
        self.make_wheel(path, "app", "2.0")
        staging.write_build_record(
            final, "g", "wheel", project="app", version="1.0", artifact_paths=[path]
        )

        with pytest.raises(staging.StagingError, match="embeds version"):
            staging.commit_generation(final, "g")

    def test_wheel_name_normalization(self, temp_dir):
        final = str(temp_dir / "dist")
        artifacts = staging.begin_generation(final, generation="g", session="s", targets=["wheel"])
        path = os.path.join(artifacts, "my_app-1.0-py3-none-any.whl")
        self.make_wheel(path, "my-app", "1.0")
        staging.write_build_record(
            final, "g", "wheel", project="My.App", version="1.0", artifact_paths=[path]
        )

        staging.commit_generation(final, "g")

    def test_sdist_metadata_matches(self, temp_dir):
        final = str(temp_dir / "dist")
        artifacts = staging.begin_generation(final, generation="g", session="s", targets=["sdist"])
        path = os.path.join(artifacts, "app-1.0.tar.gz")
        self.make_sdist(path, "app", "1.0")
        staging.write_build_record(
            final, "g", "sdist", project="app", version="1.0", artifact_paths=[path]
        )

        staging.commit_generation(final, "g")

    def test_custom_artifact_skips_metadata_check(self, temp_dir):
        final = str(temp_dir / "dist")
        artifacts = staging.begin_generation(final, generation="g", session="s", targets=["custom"])
        path = os.path.join(artifacts, "app-1.0.bin")
        write_file(path, b"binary payload")
        staging.write_build_record(
            final, "g", "custom", project="app", version="1.0", artifact_paths=[path]
        )

        staging.commit_generation(final, "g")


class TestSessions:
    def _commit_generation(self, temp_dir, session, generation, names):
        final = str(temp_dir / "dist")
        targets = ["sdist" if name.endswith(".tar.gz") else "wheel" for name in names]
        artifacts = staging.begin_generation(
            final, generation=generation, session=session, targets=targets
        )
        for name in names:
            path = write_file(os.path.join(artifacts, name), f"contents of {name}".encode())
            target = "sdist" if name.endswith(".tar.gz") else "wheel"
            staging.write_build_record(
                final, generation, target, project="app", version="1.0", artifact_paths=[path]
            )
        staging.commit_generation(final, generation)

    def test_latest_session_groups_generations(self, temp_dir):
        self._commit_generation(temp_dir, "session-1", "gen-a", ["app-1.0.tar.gz", "app-1.0.whl"])
        self._commit_generation(temp_dir, "session-2", "gen-b", ["member-2.0.tar.gz"])
        self._commit_generation(temp_dir, "session-2", "gen-c", ["member-2.0.whl"])

        final = str(temp_dir / "dist")
        session, manifests = staging.latest_session(final)
        assert session == "session-2"
        assert [m["generation"] for m in manifests] == ["gen-b", "gen-c"]
        assert staging.session_artifact_names(manifests) == ["member-2.0.tar.gz", "member-2.0.whl"]

    def test_no_generations(self, temp_dir):
        session, manifests = staging.latest_session(str(temp_dir / "dist"))
        assert session is None
        assert manifests == []

    def test_confirmed_manifests_are_valid_json_documents(self, temp_dir):
        self._commit_generation(temp_dir, "session-1", "gen-a", ["app-1.0.tar.gz", "app-1.0.whl"])

        final = str(temp_dir / "dist")
        path = staging.confirmed_manifest_path(final, "gen-a")
        with open(path, encoding="utf-8") as f:
            assert json.load(f)["generation"] == "gen-a"

    def test_generation_and_session_ids_are_unique(self):
        assert staging.new_generation_id() != staging.new_generation_id()
        assert staging.new_session_id() != staging.new_session_id()
