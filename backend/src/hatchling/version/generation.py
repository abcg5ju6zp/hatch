from __future__ import annotations

import hashlib
import json
import os
import tempfile
from contextlib import suppress
from typing import Any

# The name used for generations that originate from the static `project.version` field
STATIC_SOURCE = "static"

# The reserved per-project directory in which generation ledgers are kept. It is excluded from
# every build target so it never enters the artifacts.
GENERATION_DIRECTORY = ".hatch"
GENERATION_LEDGER_DIRECTORY = "build"
GENERATION_FILE = "generation.json"

STATE_VERSION = 1
_EMPTY_STATE: dict[str, Any] = {
    "version": STATE_VERSION,
    "committed": None,
    "candidate": None,
    "artifacts": [],
    "candidate_artifacts": [],
}


class VersionGeneration:
    """
    An immutable snapshot of a single version generation.

    A generation bundles every version-related input that the metadata, builders, and publisher must
    agree on so that they switch together rather than each potentially observing a different version.
    """

    __slots__ = ("original_version", "scheme_name", "source_name", "version")

    def __init__(self, version: str, original_version: str, source_name: str, scheme_name: str = "") -> None:
        self.version = version
        self.original_version = original_version
        self.source_name = source_name
        self.scheme_name = scheme_name

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, VersionGeneration):
            return NotImplemented

        return (
            self.version == other.version
            and self.original_version == other.original_version
            and self.source_name == other.source_name
            and self.scheme_name == other.scheme_name
        )

    def __hash__(self) -> int:
        return hash((self.version, self.original_version, self.source_name, self.scheme_name))

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}("
            f"version={self.version!r}, source={self.source_name!r}, scheme={self.scheme_name!r})"
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "version": self.version,
            "original_version": self.original_version,
            "source_name": self.source_name,
            "scheme_name": self.scheme_name,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VersionGeneration:
        return cls(
            data["version"],
            data.get("original_version", data["version"]),
            data.get("source_name", ""),
            data.get("scheme_name", ""),
        )


class GenerationStore:
    """
    Persists generation state in a reserved per-project ledger directory.

    The ledger is keyed by the (real) build output directory so that multiple output directories
    for one project each have independent state. The state distinguishes a generation that has been
    committed (i.e. every consumer has switched to it) from a candidate that is in the process of
    being adopted. The presence of a candidate after a restart indicates that a previous process
    died mid-switch and that recovery is required.
    """

    def __init__(self, root: str, directory: str) -> None:
        self.root = root
        self.directory = directory
        key = hashlib.sha256(os.path.realpath(directory).encode("utf-8")).hexdigest()
        self.path = os.path.join(
            root, GENERATION_DIRECTORY, GENERATION_LEDGER_DIRECTORY, key, GENERATION_FILE
        )

    def exists(self) -> bool:
        return os.path.isfile(self.path)

    def load(self) -> dict[str, Any]:
        if not os.path.isfile(self.path):
            return _empty_state()

        try:
            with open(self.path, encoding="utf-8") as f:
                state = json.load(f)
        except (OSError, json.JSONDecodeError):
            return _empty_state()

        if not isinstance(state, dict) or not isinstance(state.get("committed"), dict | None):
            return _empty_state()

        state.setdefault("version", STATE_VERSION)
        state.setdefault("candidate", None)
        state.setdefault("artifacts", [])
        state.setdefault("candidate_artifacts", [])
        if (
            not isinstance(state["candidate"], dict | None)
            or not isinstance(state["artifacts"], list)
            or not isinstance(state["candidate_artifacts"], list)
        ):
            return _empty_state()

        return state

    def save(
        self,
        *,
        committed: VersionGeneration | None,
        candidate: VersionGeneration | None = None,
        artifacts: list[str] | tuple[str, ...] = (),
        candidate_artifacts: list[str] | tuple[str, ...] = (),
    ) -> None:
        parent_dir = os.path.dirname(self.path)
        os.makedirs(parent_dir, exist_ok=True)

        state = {
            "version": STATE_VERSION,
            "committed": committed.to_dict() if committed is not None else None,
            "candidate": candidate.to_dict() if candidate is not None else None,
            "artifacts": list(artifacts),
            "candidate_artifacts": list(candidate_artifacts),
        }

        fd, temporary_path = tempfile.mkstemp(dir=parent_dir)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(state, f)
                f.flush()
                os.fsync(f.fileno())

            os.replace(temporary_path, self.path)
        except BaseException:
            with suppress(OSError):
                os.remove(temporary_path)
            raise

    def committed_generation(self) -> VersionGeneration | None:
        committed = self.load()["committed"]
        return VersionGeneration.from_dict(committed) if committed is not None else None

    def candidate_generation(self) -> VersionGeneration | None:
        candidate = self.load()["candidate"]
        return VersionGeneration.from_dict(candidate) if candidate is not None else None


class VersionCoordinator:
    """
    Orchestrates the two-phase switch of a version generation.

    - Phase 1 (`begin`): the candidate version, dynamic fields, and plugin configuration are parsed and
      validated without altering the committed generation.
    - Phase 2 (`commit`): metadata adopts the candidate, it is recorded as committed, and artifacts that
      belonged to previous generations are removed.

    Any failure path (configuration error, unavailable VCS/source, aborted build, or process restart)
    leaves consumers on the last committed generation and discards candidate artifacts.
    """

    def __init__(self, metadata: Any, directory: str) -> None:
        self.metadata = metadata
        self.directory = directory
        self.store = GenerationStore(metadata.root, directory)

    def recover(self) -> None:
        """
        Clean up after a process that died while switching generations.

        Artifacts are only removed when the candidate generation differs from the committed one so that
        a crash during a same-version (cache-hit) rebuild never destroys the last good artifacts.
        """
        state = self.store.load()
        candidate_data = state["candidate"]
        if candidate_data is None:
            return

        candidate = VersionGeneration.from_dict(candidate_data)
        committed = VersionGeneration.from_dict(state["committed"]) if state["committed"] is not None else None
        if committed is None or committed != candidate:
            candidate_artifacts = state.get("candidate_artifacts", [])
            if candidate_artifacts:
                self._remove_named_artifacts(candidate_artifacts)
            else:
                self._remove_generation_artifacts(candidate)

        self.store.save(committed=committed, artifacts=state["artifacts"])

    def begin(self) -> VersionGeneration:
        """
        Resolve and validate the candidate generation.

        On failure the committed generation (if any) is restored into the metadata, candidate artifacts
        are purged, and the original exception is propagated.
        """
        try:
            candidate = self.metadata.prepare_version()
        except BaseException:
            self._fallback()
            raise

        state = self.store.load()
        self.store.save(
            committed=VersionGeneration.from_dict(state["committed"]) if state["committed"] is not None else None,
            candidate=candidate,
            artifacts=state["artifacts"],
            candidate_artifacts=[],
        )
        return candidate

    def commit(self, candidate: VersionGeneration, produced: list[str]) -> bool:
        """
        Record the candidate as the committed generation.

        Returns whether the generation changed, in which case artifacts from previous generations are
        removed. Same-version (cache-hit) builds leave existing artifacts untouched.
        """
        state = self.store.load()
        committed = VersionGeneration.from_dict(state["committed"]) if state["committed"] is not None else None
        changed = committed is None or committed != candidate

        artifacts = sorted({
            *state["artifacts"],
            *(os.path.basename(path) for path in produced),
        }) if not changed else sorted(os.path.basename(path) for path in produced)

        # Persist the exact candidate artifact names before switching metadata.
        # Recovery can then remove only this failed candidate, even when it has
        # the same version string as the committed generation.
        self.store.save(
            committed=committed,
            candidate=candidate,
            artifacts=state["artifacts"],
            candidate_artifacts=[os.path.basename(path) for path in produced],
        )
        self.metadata.commit_version(candidate)
        self.store.save(committed=candidate, artifacts=artifacts, candidate_artifacts=[])

        if changed:
            self._remove_stale_artifacts(candidate, keep=set(artifacts))

        return changed

    def abort(self, candidate: VersionGeneration, produced: list[str]) -> None:
        """
        Roll back a generation switch whose build did not complete.

        If the candidate is the generation that is already committed (e.g. the consumer simply stopped
        iterating after a successful build) nothing is done. A failed same-version rebuild keeps the
        produced artifacts as representatives. A failed switch to a new generation purges its artifacts
        and restores the previous one.
        """
        state = self.store.load()
        committed = VersionGeneration.from_dict(state["committed"]) if state["committed"] is not None else None
        if committed == candidate:
            return

        if committed is not None:
            candidate_artifacts = state.get("candidate_artifacts", [])
            self._remove_named_artifacts([*candidate_artifacts, *(os.path.basename(path) for path in produced)])
            self.store.save(committed=committed, artifacts=state["artifacts"])
            self.metadata.restore_version(committed)
        else:
            for path in produced:
                with suppress(OSError):
                    os.remove(path)

            self.store.save(committed=None, artifacts=state.get("artifacts", []))

    def discard(self) -> None:
        """Clear the candidate marker without producing anything (e.g. hooks-only builds)."""
        state = self.store.load()
        committed = VersionGeneration.from_dict(state["committed"]) if state["committed"] is not None else None
        self.store.save(committed=committed, artifacts=state["artifacts"])

    def _fallback(self) -> None:
        state = self.store.load()
        candidate_data = state["candidate"]
        committed = VersionGeneration.from_dict(state["committed"]) if state["committed"] is not None else None
        candidate = VersionGeneration.from_dict(candidate_data) if candidate_data is not None else None
        if candidate is not None and (committed is None or committed != candidate):
            self._remove_generation_artifacts(candidate)

        self.store.save(committed=committed, artifacts=state["artifacts"])
        if committed is not None:
            self.metadata.restore_version(committed)

    def _remove_generation_artifacts(self, generation: VersionGeneration) -> None:
        for path, version in iter_named_artifacts(self.directory, self.metadata.name):
            if version == generation.version:
                with suppress(OSError):
                    os.remove(path)

    def _remove_named_artifacts(self, names: list[str] | tuple[str, ...]) -> None:
        wanted = set(names)
        for name in wanted:
            with suppress(OSError):
                os.remove(os.path.join(self.directory, name))

    def _remove_stale_artifacts(self, generation: VersionGeneration, *, keep: set[str]) -> None:
        for path, version in iter_named_artifacts(self.directory, self.metadata.name):
            if version != generation.version and os.path.basename(path) not in keep:
                with suppress(OSError):
                    os.remove(path)


def iter_named_artifacts(directory: str, project_name: str):
    """
    Yield `(path, version)` for every build artifact in `directory` that parses as belonging to the
    project. Files with unparseable names or other project names are ignored conservatively.
    """
    from hatchling.metadata.utils import normalize_project_name

    normalized_name = normalize_project_name(project_name)

    for filename in os.listdir(directory):
        path = os.path.join(directory, filename)
        if not os.path.isfile(path):
            continue

        parsed = _parse_named_artifact(filename)
        if parsed is None:
            continue

        name, version = parsed
        if normalize_project_name(name) == normalized_name:
            yield path, version


def _parse_named_artifact(filename: str) -> tuple[str, str] | None:
    from packaging.utils import parse_sdist_filename, parse_wheel_filename

    try:
        if filename.endswith(".whl"):
            name, version, _build_tags, _file_tags = parse_wheel_filename(filename)
        elif filename.endswith(".tar.gz"):
            name, version = parse_sdist_filename(filename)
        else:
            return None
    except Exception:  # noqa: BLE001
        return None

    return name, str(version)


def _empty_state() -> dict[str, Any]:
    state = dict(_EMPTY_STATE)
    state["artifacts"] = []
    return state
