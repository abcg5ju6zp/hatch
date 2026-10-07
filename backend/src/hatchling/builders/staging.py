from __future__ import annotations

import hashlib
import json
import os
import platform
import secrets
import shutil
import tarfile
import tempfile
import zipfile
from contextlib import suppress
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from hatchling.metadata.utils import normalize_project_name

if TYPE_CHECKING:
    from collections.abc import Iterable

# The bookkeeping directory lives next to (rather than inside) the final build directory so
# that the build directory itself never contains anything but the confirmed artifact files.
# Existing consumers that iterate it (such as publishers looking for `.whl` and `.tar.gz`
# files) therefore keep behaving exactly as before.
PENDING_DIRECTORY = "staging"
CONFIRMED_DIRECTORY = "generations"
ARTIFACTS_DIRECTORY = "artifacts"
RECORDS_DIRECTORY = "records"
MANIFEST_FILE = "manifest.json"

MANIFEST_FORMAT = 1


class StagingError(Exception):
    """Raised when an artifact set cannot be built, validated or committed atomically."""


def new_generation_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    return f"{timestamp}-{secrets.token_hex(4)}"


def new_session_id() -> str:
    return secrets.token_hex(8)


def bookkeeping_directory(final_directory: str) -> str:
    absolute = os.path.abspath(final_directory)
    return os.path.join(os.path.dirname(absolute), f".{os.path.basename(absolute)}.hatch")


def pending_root(final_directory: str) -> str:
    return os.path.join(bookkeeping_directory(final_directory), PENDING_DIRECTORY)


def confirmed_root(final_directory: str) -> str:
    return os.path.join(bookkeeping_directory(final_directory), CONFIRMED_DIRECTORY)


def pending_directory(final_directory: str, generation: str) -> str:
    return os.path.join(pending_root(final_directory), generation)


def artifacts_directory(final_directory: str, generation: str) -> str:
    return os.path.join(pending_directory(final_directory, generation), ARTIFACTS_DIRECTORY)


def records_directory(final_directory: str, generation: str) -> str:
    return os.path.join(pending_directory(final_directory, generation), RECORDS_DIRECTORY)


def confirmed_manifest_path(final_directory: str, generation: str) -> str:
    return os.path.join(confirmed_root(final_directory), f"{generation}.json")


def cleanup_pending(final_directory: str) -> None:
    """Remove every unpublished generation left behind by aborted or interrupted builds."""
    root = pending_root(final_directory)
    if os.path.isdir(root):
        for name in os.listdir(root):
            shutil.rmtree(os.path.join(root, name), ignore_errors=True)
        with suppress(OSError):
            os.rmdir(root)


def begin_generation(
    final_directory: str,
    *,
    generation: str,
    session: str,
    targets: Iterable[str],
    project: str | None = None,
    version: str | None = None,
) -> str:
    """Create a fresh, empty, isolated generation directory and return its artifact directory."""
    # A new transaction starts after a successful prior run or after a restart, so every
    # unpublished directory left behind by an aborted process can be reclaimed now
    cleanup_pending(final_directory)

    staging = pending_directory(final_directory, generation)
    if os.path.exists(staging):  # no cov
        shutil.rmtree(staging, ignore_errors=True)

    os.makedirs(os.path.join(staging, ARTIFACTS_DIRECTORY), exist_ok=True)
    os.makedirs(os.path.join(staging, RECORDS_DIRECTORY), exist_ok=True)

    manifest = {
        "format": MANIFEST_FORMAT,
        "generation": generation,
        "session": session,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "project": project,
        "version": version,
        "targets": list(targets),
    }
    write_json(os.path.join(staging, MANIFEST_FILE), manifest)
    _fsync_directory(staging)
    return artifacts_directory(final_directory, generation)


def write_build_record(
    final_directory: str,
    generation: str,
    target: str,
    *,
    project: str | None,
    version: str | None,
    artifact_paths: Iterable[str],
) -> None:
    """Record the artifacts produced by a single (subprocess) builder for a pending generation."""
    staging_artifacts = artifacts_directory(final_directory, generation)
    records = records_directory(final_directory, generation)
    os.makedirs(records, exist_ok=True)

    entries = [describe_artifact(artifact_path, staging_artifacts) for artifact_path in artifact_paths]

    record = {
        "target": target,
        "project": project,
        "version": version,
        "artifacts": entries,
    }
    write_json(os.path.join(records, f"{_safe_name(target)}.json"), record)


def describe_artifact(artifact_path: str, staging_artifacts: str) -> dict[str, Any]:
    path = os.path.normpath(artifact_path)
    artifacts_root = os.path.normpath(staging_artifacts)
    if os.path.dirname(path) != artifacts_root:
        message = f"Artifact was not written to the isolated build directory: {artifact_path}"
        raise StagingError(message)
    if not os.path.isfile(path):
        message = f"Artifact is missing or not a regular file: {artifact_path}"
        raise StagingError(message)

    name = os.path.basename(path)
    if not name or name in {os.curdir, os.pardir} or os.sep in name or (os.altsep and os.altsep in name):
        message = f"Artifact has an invalid file name: {name}"
        raise StagingError(message)

    size, digest = hash_file(path)
    return {"name": name, "size": size, "sha256": digest}


def load_build_record(final_directory: str, generation: str, target: str) -> dict[str, Any] | None:
    path = os.path.join(records_directory(final_directory, generation), f"{_safe_name(target)}.json")
    if not os.path.isfile(path):
        return None
    return read_json(path)


def assemble_generation(final_directory: str, generation: str) -> dict[str, Any]:
    """Combine the generation skeleton and all per-target records into one confirmed manifest."""
    staging = pending_directory(final_directory, generation)
    manifest_path = os.path.join(staging, MANIFEST_FILE)
    if not os.path.isfile(manifest_path):
        message = f"Unknown build generation: {generation}"
        raise StagingError(message)

    manifest = read_json(manifest_path)
    target_records = []
    records = records_directory(final_directory, generation)
    if os.path.isdir(records):
        target_records.extend(
            read_json(os.path.join(records, filename))
            for filename in sorted(os.listdir(records))
            if filename.endswith(".json")
        )

    recorded_targets = [record["target"] for record in target_records]
    expected_targets = list(manifest.get("targets", []))
    missing = [target for target in expected_targets if target not in recorded_targets]
    if missing:
        message = f"Build generation is incomplete, missing targets: {', '.join(missing)}"
        raise StagingError(message)

    artifacts = []
    project = manifest.get("project")
    version = manifest.get("version")
    records_by_target = {record["target"]: record for record in target_records}
    for target in expected_targets:
        record = records_by_target[target]
        if record.get("project"):
            project = project or record["project"]
        if record.get("version"):
            version = version or record["version"]
        for entry in record.get("artifacts", []):
            artifact = dict(entry)
            artifact["target"] = target
            artifacts.append(artifact)

    if not artifacts:
        message = "Build generation did not produce any artifacts"
        raise StagingError(message)

    # Artifact names must be unique across the whole set
    seen: set[str] = set()
    for artifact in artifacts:
        name = artifact["name"]
        if name in seen:
            message = f"Duplicate artifact in build generation: {name}"
            raise StagingError(message)
        seen.add(name)

    manifest["project"] = project
    manifest["version"] = version
    manifest["artifacts"] = artifacts
    return manifest


def validate_generation(final_directory: str, generation: str, manifest: dict[str, Any]) -> None:
    staging_artifacts = artifacts_directory(final_directory, generation)
    recorded_names = {artifact["name"] for artifact in manifest.get("artifacts", ())}

    # No partial/leftover files may exist alongside the declared artifact set
    actual_names = set()
    if os.path.isdir(staging_artifacts):
        for name in os.listdir(staging_artifacts):
            path = os.path.join(staging_artifacts, name)
            if not os.path.isfile(path):
                message = f"Unexpected entry in isolated build directory: {name}"
                raise StagingError(message)
            actual_names.add(name)

    extras = actual_names - recorded_names
    if extras:
        message = f"Unvalidated files left by a build hook or packaging step: {', '.join(sorted(extras))}"
        raise StagingError(message)

    project = manifest.get("project")
    version = manifest.get("version")
    for artifact in manifest.get("artifacts", ()):
        path = os.path.join(staging_artifacts, artifact["name"])
        validate_artifact(path, artifact, project, version)


def validate_artifact(
    path: str,
    entry: dict[str, Any],
    project: str | None = None,
    version: str | None = None,
) -> None:
    if not os.path.isfile(path):
        message = f"Artifact is missing from the isolated build directory: {entry.get('name', path)}"
        raise StagingError(message)

    size, digest = hash_file(path)
    if size == 0:
        message = f"Artifact is empty: {entry['name']}"
        raise StagingError(message)
    if size != entry["size"]:
        message = f"Artifact size mismatch for `{entry['name']}`: expected {entry['size']}, got {size}"
        raise StagingError(message)
    if digest != entry["sha256"]:
        message = f"Artifact hash mismatch for `{entry['name']}`"
        raise StagingError(message)

    embedded_project = embedded_version = None
    name = entry["name"]
    if name.endswith(".whl"):
        embedded_project, embedded_version = read_wheel_metadata(path)
    elif name.endswith(".tar.gz"):
        embedded_project, embedded_version = read_sdist_metadata(path)

    if (
        embedded_project is not None
        and project is not None
        and normalize_project_name(embedded_project) != normalize_project_name(project)
    ):
        message = (
            f"Artifact `{name}` embeds project `{embedded_project}` which does not match "
            f"the build metadata project `{project}`"
        )
        raise StagingError(message)
    if embedded_version is not None and version is not None and embedded_version != version:
        message = (
            f"Artifact `{name}` embeds version `{embedded_version}` which does not match "
            f"the build metadata version `{version}`"
        )
        raise StagingError(message)


def commit_generation(
    final_directory: str,
    generation: str,
    *,
    clean_rules: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Validate the isolated set and replace the target artifact set in one operation."""
    manifest = assemble_generation(final_directory, generation)
    validate_generation(final_directory, generation, manifest)

    staging_artifacts = artifacts_directory(final_directory, generation)
    parent = os.path.dirname(os.path.abspath(final_directory))
    replacement = os.path.join(parent, f".{os.path.basename(final_directory)}.next-{generation}")
    shutil.rmtree(replacement, ignore_errors=True)
    os.makedirs(replacement, exist_ok=True)

    # Build the complete next directory without touching the visible one. This
    # makes cleaning and multi-file replacement part of one directory swap.
    if os.path.isdir(final_directory):
        explicit_names = _explicit_clean_names(clean_rules or {})
        for name in os.listdir(final_directory):
            source = os.path.join(final_directory, name)
            if clean_rules and os.path.isfile(source):
                remove = False
                for rule in clean_rules.values():
                    suffixes = tuple(rule.get("suffixes", ()))
                    names = set(rule.get("names", ()))
                    if name in names or (name.endswith(suffixes) and name not in explicit_names):
                        remove = True
                        break
                if remove:
                    continue
            destination = os.path.join(replacement, name)
            if os.path.isdir(source) and not os.path.islink(source):
                shutil.copytree(source, destination, symlinks=True)
            else:
                shutil.copy2(source, destination, follow_symlinks=False)

    for artifact in manifest["artifacts"]:
        source = os.path.join(staging_artifacts, artifact["name"])
        target = os.path.join(replacement, artifact["name"])
        _replace_file(source, target)
        _fsync_path(target)

    _fsync_directory(replacement)
    _atomic_replace_directory(replacement, final_directory)
    _fsync_directory(parent)

    manifest_path = confirmed_manifest_path(final_directory, generation)
    os.makedirs(confirmed_root(final_directory), exist_ok=True)
    write_json(manifest_path, manifest)
    _fsync_directory(confirmed_root(final_directory))

    shutil.rmtree(pending_directory(final_directory, generation), ignore_errors=True)
    _remove_empty_directory(pending_root(final_directory))
    return manifest


def _atomic_replace_directory(replacement: str, target: str) -> None:
    """Atomically publish a complete directory, preserving the old one on failure."""
    if not os.path.lexists(target):
        os.replace(replacement, target)
        return
    if not os.path.isdir(target):
        raise StagingError(f"Build output is not a directory: {target}")

    if platform.system() == "Darwin":
        import ctypes

        libc = ctypes.CDLL(None, use_errno=True)
        renameatx_np = libc.renameatx_np
        renameatx_np.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        renameatx_np.restype = ctypes.c_int
        result = renameatx_np(-2, target.encode(), -2, replacement.encode(), 0x00000002)
        if result != 0:
            error = ctypes.get_errno()
            raise OSError(error, os.strerror(error))
        shutil.rmtree(replacement, ignore_errors=True)
        return

    raise StagingError("atomic directory replacement is unavailable on this platform")


def abort_generation(final_directory: str, generation: str) -> None:
    """Discard an isolated set, leaving the previously confirmed set untouched."""
    shutil.rmtree(pending_directory(final_directory, generation), ignore_errors=True)
    _remove_empty_directory(pending_root(final_directory))


def iter_confirmed_manifests(final_directory: str) -> list[dict[str, Any]]:
    root = confirmed_root(final_directory)
    if not os.path.isdir(root):
        return []

    manifests = []
    for filename in os.listdir(root):
        if not filename.endswith(".json"):
            continue
        path = os.path.join(root, filename)
        if os.path.isfile(path):
            try:
                manifests.append(read_json(path))
            except (OSError, json.JSONDecodeError):  # no cov
                continue

    manifests.sort(key=lambda manifest: (manifest.get("created_at", ""), manifest.get("generation", "")))
    return manifests


def has_generations(final_directory: str) -> bool:
    return bool(iter_confirmed_manifests(final_directory))


def latest_session(final_directory: str) -> tuple[str | None, list[dict[str, Any]]]:
    manifests = iter_confirmed_manifests(final_directory)
    if not manifests:
        return None, []

    session = manifests[-1].get("session")
    return session, [manifest for manifest in manifests if manifest.get("session") == session]


def session_artifact_names(manifests: Iterable[dict[str, Any]]) -> list[str]:
    # Use as an ordered set while preserving generation order
    names: dict[str, None] = {}
    for manifest in manifests:
        for artifact in manifest.get("artifacts", ()):
            names.setdefault(artifact["name"], None)
    return list(names)


def read_wheel_metadata(path: str) -> tuple[str | None, str | None]:
    try:
        with zipfile.ZipFile(path) as archive:
            metadata_name = next(
                name
                for name in archive.namelist()
                if name.endswith(".dist-info/METADATA")
            )
            contents = archive.read(metadata_name).decode("utf-8", "replace")
    except (OSError, StopIteration, zipfile.BadZipFile):
        return None, None

    return parse_core_metadata(contents)


def read_sdist_metadata(path: str) -> tuple[str | None, str | None]:
    try:
        with tarfile.open(path, "r:gz") as archive:
            member = next(member for member in archive.getmembers() if member.name.endswith("/PKG-INFO"))
            extracted = archive.extractfile(member)
            if extracted is None:
                return None, None
            contents = extracted.read().decode("utf-8", "replace")
    except (OSError, StopIteration, tarfile.TarError):
        return None, None

    return parse_core_metadata(contents)


def parse_core_metadata(contents: str) -> tuple[str | None, str | None]:
    name = version = None
    for line in contents.splitlines():
        if not line.strip():
            break
        if name is None and line.lower().startswith("name:"):
            name = line.split(":", 1)[1].strip()
        elif version is None and line.lower().startswith("version:"):
            version = line.split(":", 1)[1].strip()
        if name is not None and version is not None:
            break

    return name, version


def hash_file(path: str) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)

    return size, digest.hexdigest()


def write_json(path: str, data: dict[str, Any]) -> None:
    directory = os.path.dirname(path) or os.curdir
    fd, temporary = tempfile.mkstemp(dir=directory, prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)
            f.write("\n")
            f.flush()
            _fsync_path(f)
        os.replace(temporary, path)
    except BaseException:
        with suppress(OSError):
            os.remove(temporary)
        raise


def read_json(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _explicit_clean_names(clean_rules: dict[str, dict[str, Any]]) -> set[str]:
    names: set[str] = set()
    for rule in clean_rules.values():
        names.update(rule.get("names", ()))
    return names


def _safe_name(name: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in name)


def _replace_file(source: str, target: str) -> None:
    try:
        os.replace(source, target)
    except OSError:
        # Cross-device move or layered container filesystem
        shutil.copy2(source, target)
        os.remove(source)


def _fsync_path(path: Any) -> None:
    try:
        fd = path.fileno() if hasattr(path, "fileno") else os.open(path, os.O_RDONLY)
    except OSError:
        return

    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        if not hasattr(path, "fileno"):
            os.close(fd)


def _fsync_directory(directory: str) -> None:
    if not os.path.isdir(directory):
        return

    fd = None
    try:
        fd = os.open(directory, os.O_RDONLY)
        os.fsync(fd)
    except OSError:
        pass
    finally:
        if fd is not None:
            os.close(fd)


def _remove_empty_directory(directory: str) -> None:
    with suppress(OSError):
        os.rmdir(directory)
