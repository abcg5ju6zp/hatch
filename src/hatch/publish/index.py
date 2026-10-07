from __future__ import annotations

import re
from typing import TYPE_CHECKING

from hatch.publish.plugin.interface import PublisherInterface
from hatch.utils.fs import Path
from hatchling.metadata.utils import normalize_project_name

if TYPE_CHECKING:
    from collections.abc import Iterable


class IndexPublisher(PublisherInterface):
    PLUGIN_NAME = "index"

    def get_repos(self):
        global_plugin_config = self.plugin_config.copy()
        defined_repos = self.plugin_config.pop("repos", {})
        self.plugin_config.pop("repo", None)

        # Normalize type
        repos = {}
        for repo, data in defined_repos.items():
            if isinstance(data, str):
                repos[repo] = {"url": data}
            elif not isinstance(data, dict):
                self.app.abort(f"Hatch config field `publish.index.repos.{repo}` must be a string or a mapping")
            elif "url" not in data:
                self.app.abort(f"Hatch config field `publish.index.repos.{repo}` must define a `url` key")
            else:
                repos[repo] = data

        # Ensure PyPI correct
        for repo, url in (
            ("main", "https://upload.pypi.org/legacy/"),
            ("test", "https://test.pypi.org/legacy/"),
        ):
            repos.setdefault(repo, {})["url"] = url

        # Populate defaults
        for config in repos.values():
            for key, value in global_plugin_config.items():
                config.setdefault(key, value)

        return repos

    def publish(self, artifacts: list, options: dict):
        """
        https://warehouse.readthedocs.io/api-reference/legacy.html#upload-api
        """
        from collections import defaultdict

        from hatch.index.core import PackageIndex
        from hatch.index.publish import get_sdist_form_data, get_wheel_form_data
        from hatch.publish.auth import AuthenticationCredentials
        from hatchling.builders.constants import DEFAULT_BUILD_DIRECTORY

        explicitly_selected = bool(artifacts)
        if not artifacts:
            artifacts = [DEFAULT_BUILD_DIRECTORY]

        repo = options["repo"] if "repo" in options else self.plugin_config.get("repo", "main")
        repos = self.get_repos()
        repo_config: dict[str, str] = repos[repo] if repo in repos else {"url": repo}
        credentials = AuthenticationCredentials(
            app=self.app,
            cache_dir=self.cache_dir,
            options=options,
            repo=repo,
            repo_config=repo_config,
        )

        index = PackageIndex(
            repo_config["url"],
            user=credentials.username,
            auth=credentials.password,
            ca_cert=options.get("ca_cert", repo_config.get("ca-cert")),
            client_cert=options.get("client_cert", repo_config.get("client-cert")),
            client_key=options.get("client_key", repo_config.get("client-key")),
        )

        # Artifacts produced by atomic builds are grouped by confirmed generation. Only the latest
        # build session is eligible and a generation is never uploaded twice.
        generation_plan = None
        if not explicitly_selected:
            generation_plan = select_generation_artifacts(self.root / DEFAULT_BUILD_DIRECTORY)
            if generation_plan is not None:
                generation_plan = self.filter_published_generations(generation_plan, str(index.url))
                if not generation_plan:
                    self.app.abort(code=0)

        existing_artifacts: dict[str, set[str]] = {}

        # Use as an ordered set
        project_versions: dict[str, dict[str, None]] = defaultdict(dict)

        artifact_paths: Iterable[Path]
        if generation_plan is None:
            artifact_paths = recurse_artifacts(artifacts, self.root)
            generation_by_name = {}
        else:
            artifact_paths = list(iter_planned_artifacts(self.root / DEFAULT_BUILD_DIRECTORY, generation_plan))
            generation_by_name = {
                artifact: generation for generation, names in generation_plan for artifact in names
            }

        artifacts_found = False
        uploaded_by_generation: dict[str, set[str]] = defaultdict(set)
        for artifact in artifact_paths:
            if artifact.name.endswith(".whl"):
                data = get_wheel_form_data(artifact)
            elif artifact.name.endswith(".tar.gz"):
                data = get_sdist_form_data(artifact)
            else:
                continue

            artifacts_found = True

            for field in ("name", "version"):
                if field not in data:
                    self.app.abort(f"Missing required field `{field}` in artifact: {artifact}")

            try:
                displayed_path = str(artifact.relative_to(self.root))
            except ValueError:
                displayed_path = str(artifact)

            self.app.display_info(f"{displayed_path} ...", end=" ")

            project_name = normalize_project_name(data["name"])
            if project_name not in existing_artifacts:
                try:
                    response = index.get_simple_api(project_name)
                    response.raise_for_status()
                except Exception:  # no cov  # noqa: BLE001
                    existing_artifacts[project_name] = set()
                else:
                    existing_artifacts[project_name] = set(parse_artifacts(response.text))

            if artifact.name in existing_artifacts[project_name]:
                self.app.display_warning("already exists")
                planned_generation = generation_by_name.get(artifact.name)
                if planned_generation is not None:
                    uploaded_by_generation[planned_generation].add(artifact.name)
                    self.mark_generation_complete_if_done(
                        planned_generation, generation_plan, uploaded_by_generation[planned_generation], str(index.url)
                    )
                continue

            try:
                index.upload_artifact(artifact, data)
            except Exception as e:  # noqa: BLE001
                self.app.display_error("failed")
                self.app.abort(f"Error uploading to repository: {index.repo} - {e}".replace(index.auth, "*****"))
            else:
                self.app.display_success("success")

                existing_artifacts[project_name].add(artifact.name)
                project_versions[project_name][data["version"]] = None

                planned_generation = generation_by_name.get(artifact.name)
                if planned_generation is not None:
                    uploaded_by_generation[planned_generation].add(artifact.name)
                    self.mark_generation_complete_if_done(
                        planned_generation, generation_plan, uploaded_by_generation[planned_generation], str(index.url)
                    )

        if not options["initialize_auth"]:
            if not artifacts_found:
                self.app.abort("No artifacts found")
            elif not project_versions:
                self.app.abort(code=0)

        for project_name, versions in project_versions.items():
            self.app.display_info()
            self.app.display_mini_header(project_name)
            for version in versions:
                self.app.display_info(str(index.urls.project.child(project_name, version, "").to_iri()))

        credentials.write_updated_data()

    @property
    def published_state_file(self) -> Path:
        return self.cache_dir / "published.json"

    def read_published_generations(self) -> dict:
        import json

        if not self.published_state_file.is_file():
            return {}

        try:
            data = json.loads(self.published_state_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

        return data if isinstance(data, dict) else {}

    def mark_generation_published(self, generation: str, repo_url: str) -> None:
        import json

        state = self.read_published_generations()
        generations = state.setdefault(repo_url, [])
        if generation not in generations:
            generations.append(generation)

        self.cache_dir.ensure_dir_exists()
        self.published_state_file.write_atomic(json.dumps(state, indent=2, sort_keys=True), "w", encoding="utf-8")

    def filter_published_generations(self, generation_plan, repo_url):
        published = set(self.read_published_generations().get(repo_url, ()))
        return [(generation, names) for generation, names in generation_plan if generation not in published]

    def mark_generation_complete_if_done(self, generation, generation_plan, uploaded_names, repo_url) -> None:
        expected_names = next((names for gen_id, names in generation_plan if gen_id == generation), ())
        if set(expected_names).issubset(set(uploaded_names)):
            self.mark_generation_published(generation, repo_url)


def select_generation_artifacts(build_directory: Path) -> list[tuple[str, list[str]]] | None:
    """Select the latest build session's artifact sets.

    Returns `None` when the directory predates generation tracking so that callers keep using
    their traditional directory-based discovery rules.
    """
    from hatchling.builders import staging

    if not build_directory.is_dir() or not staging.has_generations(str(build_directory)):
        return None

    _session, manifests = staging.latest_session(str(build_directory))
    return [
        (manifest["generation"], [artifact["name"] for artifact in manifest.get("artifacts", ())])
        for manifest in manifests
    ]


def iter_planned_artifacts(build_directory: Path, generation_plan: list[tuple[str, list[str]]]) -> Iterable[Path]:
    for _generation, names in generation_plan:
        for name in names:
            artifact = build_directory / name
            if artifact.is_file():
                yield artifact


def recurse_artifacts(artifacts: list, root) -> Iterable[Path]:
    for raw_artifact in artifacts:
        artifact = Path(raw_artifact)
        if not artifact.is_absolute():
            artifact = root / artifact

        if artifact.is_file():
            yield artifact
        elif artifact.is_dir():
            yield from artifact.iterdir()


def parse_artifacts(artifact_payload):
    for match in re.finditer(r"<a [^>]+>([^<]+)</a>", artifact_payload):
        yield match.group(1)
