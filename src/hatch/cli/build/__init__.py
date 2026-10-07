from __future__ import annotations

from typing import TYPE_CHECKING

import click

if TYPE_CHECKING:
    from hatch.cli.application import Application
    from hatch.project.core import Project


@click.command(short_help="Build a project")
@click.argument("location", required=False)
@click.option(
    "--target",
    "-t",
    "targets",
    multiple=True,
    help=(
        "The target to build, overriding project defaults. This may be selected multiple times e.g. `-t sdist -t wheel`"
    ),
)
@click.option(
    "--all",
    "-a",
    "build_all",
    is_flag=True,
    help=(
        "Whether or not to build the workspace root and every workspace member defined by the selected "
        "environment. Artifacts are written to the workspace root's `dist` directory by default"
    ),
)
@click.option(
    "--hooks-only", is_flag=True, help="Whether or not to only execute build hooks [env var: `HATCH_BUILD_HOOKS_ONLY`]"
)
@click.option(
    "--no-hooks", is_flag=True, help="Whether or not to disable build hooks [env var: `HATCH_BUILD_NO_HOOKS`]"
)
@click.option(
    "--ext",
    is_flag=True,
    help=(
        "Whether or not to only execute build hooks for distributing binary Python packages, such as "
        "compiling extensions. Equivalent to `--hooks-only -t wheel`"
    ),
)
@click.option(
    "--clean",
    "-c",
    is_flag=True,
    help="Whether or not existing artifacts should first be removed [env var: `HATCH_BUILD_CLEAN`]",
)
@click.option(
    "--clean-hooks-after",
    is_flag=True,
    help=(
        "Whether or not build hook artifacts should be removed after each build "
        "[env var: `HATCH_BUILD_CLEAN_HOOKS_AFTER`]"
    ),
)
@click.option("--clean-only", is_flag=True, hidden=True)
@click.pass_obj
def build(
    app: Application, location, targets, build_all, hooks_only, no_hooks, ext, clean, clean_hooks_after, clean_only
):
    """Build a project."""
    app.ensure_environment_plugin_dependencies()

    from hatch.config.constants import AppEnvVars
    from hatch.project.constants import DEFAULT_BUILD_DIRECTORY
    from hatch.utils.fs import Path
    from hatchling.builders import staging

    if ext:
        hooks_only = True
        targets = ("wheel",)
    elif not targets:
        targets = ("sdist", "wheel")

    env_vars = {}
    if app.verbose:
        env_vars[AppEnvVars.VERBOSE] = str(app.verbosity)
    elif app.quiet:
        env_vars[AppEnvVars.QUIET] = str(abs(app.verbosity))

    # Every project of a single invocation belongs to the same session so that publishers can
    # treat all of the resulting, individually confirmed generations as one release
    session_id = staging.new_session_id()

    if not build_all:
        _build_project(
            app,
            app.project,
            location,
            targets,
            hooks_only=hooks_only,
            no_hooks=no_hooks,
            clean=clean,
            clean_hooks_after=clean_hooks_after,
            clean_only=clean_only,
            env_vars=env_vars,
            session_id=session_id,
        )
        return

    environment = app.project.get_environment()
    members = environment.workspace.members
    if not members:
        app.abort(
            f"The `--all` flag requires workspace members to be defined in field "
            f"`tool.hatch.envs.{environment.name}.workspace.members`"
        )

    # Artifacts from every project are consolidated in a single directory, defaulting to the
    # workspace root. The location must be absolute because each member builds from its own path
    build_directory = str(Path(location).resolve() if location else app.project.location / DEFAULT_BUILD_DIRECTORY)

    # The workspace root is built without needing to be listed as a member, but only when it
    # defines a project itself rather than merely being a container for workspace configuration
    projects = [app.project] if app.project.defines_project else []
    projects.extend(member.project for member in members if member.project.location != app.project.location)
    for project in projects:
        if not clean_only:
            app.display_header(project.metadata.name)

        _build_project(
            app,
            project,
            build_directory,
            targets,
            hooks_only=hooks_only,
            no_hooks=no_hooks,
            clean=clean,
            clean_hooks_after=clean_hooks_after,
            clean_only=clean_only,
            env_vars=env_vars,
            session_id=session_id,
        )


def _build_project(
    app: Application,
    project: Project,
    location,
    targets,
    *,
    hooks_only,
    no_hooks,
    clean,
    clean_hooks_after,
    clean_only,
    env_vars,
    session_id,
):
    from hatch.project.config import env_var_enabled
    from hatch.project.constants import BUILD_BACKEND, DEFAULT_BUILD_DIRECTORY, BuildEnvVars
    from hatch.utils.fs import Path
    from hatch.utils.structures import EnvVars

    build_dir = Path(location).resolve() if location else None

    with EnvVars(env_vars):
        project.prepare_build_environment(targets=[target.split(":")[0] for target in targets])

    # Environment variables can request the same modes as the explicit flags
    hooks_only = hooks_only or env_var_enabled(BuildEnvVars.HOOKS_ONLY)
    no_hooks = no_hooks or env_var_enabled(BuildEnvVars.NO_HOOKS)

    # Hooks-only and clean-only runs do not produce a new artifact set, so they bypass the
    # isolated staging directory and operate on the configured directory directly
    if hooks_only or clean_only:
        _build_legacy(
            app,
            project,
            location,
            targets,
            build_backend=project.metadata.build.build_backend,
            hooks_only=hooks_only,
            no_hooks=no_hooks,
            clean=clean,
            clean_hooks_after=clean_hooks_after,
            clean_only=clean_only,
            env_vars=env_vars,
        )
        return

    effective_clean = clean or env_var_enabled(BuildEnvVars.CLEAN)

    with project.location.as_cwd(), project.build_env.get_env_vars():
        build_backend = project.metadata.build.build_backend
        if build_backend != BUILD_BACKEND:
            _build_with_frontend(
                app,
                project,
                targets,
                build_dir or project.location / DEFAULT_BUILD_DIRECTORY,
                session_id=session_id,
                clean=effective_clean,
            )
            return

        directories = {
            target: _resolve_target_directory(project, target.partition(":")[0], build_dir) for target in targets
        }
        distinct_directories = set(directories.values())

        # Only a shared destination across every target can be replaced as a single atomic set
        if len(distinct_directories) != 1:
            _build_legacy(
                app,
                project,
                location,
                targets,
                build_backend=build_backend,
                hooks_only=hooks_only,
                no_hooks=no_hooks,
                clean=clean,
                clean_hooks_after=clean_hooks_after,
                clean_only=clean_only,
                env_vars=env_vars,
            )
            return

        _build_with_hatchling(
            app,
            project,
            targets,
            next(iter(distinct_directories)),
            env_vars=env_vars,
            session_id=session_id,
            clean=effective_clean,
            clean_hooks_after=clean_hooks_after,
            no_hooks=no_hooks,
        )


def _resolve_target_directory(project: Project, target_name: str, build_dir):
    import os

    from hatch.project.constants import BuildEnvVars
    from hatch.utils.fs import Path

    if build_dir is not None:
        return build_dir

    env_location = os.environ.get(BuildEnvVars.LOCATION)
    if env_location:
        directory = Path(env_location)
        if not directory.is_absolute():
            directory = project.location / directory
        return Path(os.path.abspath(str(directory)))

    directory = Path(project.config.build.target(target_name).directory)
    if not directory.is_absolute():
        directory = project.location / directory
    return Path(os.path.abspath(str(directory)))


def _build_with_hatchling(app, project, targets, final_directory, *, env_vars, session_id, clean, clean_hooks_after, no_hooks):
    from hatch.project.config import env_var_enabled
    from hatch.project.constants import BuildEnvVars
    from hatch.utils.runner import ExecutionContext
    from hatchling.builders import staging

    final = str(final_directory)
    generation = staging.new_generation_id()
    artifacts_directory = staging.begin_generation(final, generation=generation, session=session_id, targets=list(targets))
    adopted_names: set[str] = set()

    try:
        for target in targets:
            target_name, _, _ = target.partition(":")
            app.display_header(target_name)

            command = ["python", "-u", "-m", "hatchling", "build", "--target", target]
            command.extend(("--directory", artifacts_directory))

            if no_hooks or env_var_enabled(BuildEnvVars.NO_HOOKS):
                command.append("--no-hooks")

            if clean_hooks_after or env_var_enabled(BuildEnvVars.CLEAN_HOOKS_AFTER):
                command.append("--clean-hooks-after")

            if clean:
                command.append("--clean")

            context = ExecutionContext(project.build_env)
            context.add_shell_command(command)
            context.env_vars.update(env_vars)
            context.env_vars.update({
                BuildEnvVars.SESSION: session_id,
                BuildEnvVars.GENERATION: generation,
                BuildEnvVars.FINAL_LOCATION: final,
            })
            app.execute_context(context)

            # A backend that participates in the transaction writes its own record. Older
            # versions (or non-participating processes) simply leave their artifacts in the
            # isolated directory, so adopt anything new that appeared there under this target
            if staging.load_build_record(final, generation, target) is None:
                produced = _adopt_target_artifacts(final, generation, target, artifacts_directory, adopted_names)
                adopted_names.update(produced)

        clean_rules = None
        if clean:
            clean_rules = {}
            for target in targets:
                target_name = target.partition(":")[0]
                if target_name == "sdist":
                    clean_rules[target] = {"suffixes": (".tar.gz",), "names": ()}
                elif target_name == "wheel":
                    clean_rules[target] = {"suffixes": (".whl",), "names": ()}
                else:
                    record = staging.load_build_record(final, generation, target) or {}
                    clean_rules[target] = {
                        "suffixes": (),
                        "names": tuple(artifact["name"] for artifact in record.get("artifacts", ())),
                    }

        staging.commit_generation(final, generation, clean_rules=clean_rules)
    except BaseException:
        staging.abort_generation(final, generation)
        raise


def _adopt_target_artifacts(final, generation, target, artifacts_directory, known_names):
    import os

    from hatch.index.publish import get_sdist_form_data, get_wheel_form_data
    from hatch.utils.fs import Path
    from hatchling.builders import staging

    current_names = {
        name
        for name in os.listdir(artifacts_directory)
        if os.path.isfile(os.path.join(artifacts_directory, name))
    }
    new_names = sorted(current_names - known_names)
    if not new_names:
        return set()

    project = None
    version = None
    paths = []
    for name in new_names:
        path = os.path.join(artifacts_directory, name)
        paths.append(path)
        if name.endswith(".whl"):
            data = get_wheel_form_data(Path(path))
            project, version = data.get("name"), data.get("version")
        elif name.endswith(".tar.gz"):
            data = get_sdist_form_data(Path(path))
            project, version = data.get("name"), data.get("version")

    staging.write_build_record(
        final,
        generation,
        target,
        project=project,
        version=version,
        artifact_paths=paths,
    )
    return set(new_names)


def _build_with_frontend(app, project, targets, final_directory, *, session_id, clean):
    from hatch.index.publish import get_sdist_form_data, get_wheel_form_data
    from hatch.utils.fs import Path
    from hatchling.builders import staging

    final = str(final_directory)
    generation = staging.new_generation_id()
    artifacts_directory = Path(
        staging.begin_generation(final, generation=generation, session=session_id, targets=list(targets))
    )

    try:
        for target in targets:
            target_name, _, _ = target.partition(":")
            app.display_header(target_name)

            if target_name == "sdist":
                artifact_path = project.build_frontend.build_sdist(artifacts_directory)
                data = get_sdist_form_data(artifact_path)
            elif target_name == "wheel":
                artifact_path = project.build_frontend.build_wheel(artifacts_directory)
                data = get_wheel_form_data(artifact_path)
            else:
                app.abort(f"Target `{target_name}` is not supported by `{project.metadata.build.build_backend}`")
                return

            staging.write_build_record(
                final,
                generation,
                target_name,
                project=data.get("name"),
                version=data.get("version"),
                artifact_paths=[str(artifact_path)],
            )

            final_artifact_path = final_directory / artifact_path.name
            app.display_info(
                str(final_artifact_path.relative_to(project.location))
                if project.location in final_artifact_path.parents
                else str(final_artifact_path)
            )

        clean_rules = None
        if clean:
            clean_rules = {}
            for target in targets:
                target_name = target.partition(":")[0]
                if target_name == "sdist":
                    clean_rules[target] = {"suffixes": (".tar.gz",), "names": ()}
                elif target_name == "wheel":
                    clean_rules[target] = {"suffixes": (".whl",), "names": ()}
                else:
                    clean_rules[target] = {"suffixes": (), "names": ()}

        staging.commit_generation(final, generation, clean_rules=clean_rules)
    except BaseException:
        staging.abort_generation(final, generation)
        raise


def _build_legacy(
    app,
    project,
    location,
    targets,
    *,
    build_backend,
    hooks_only,
    no_hooks,
    clean,
    clean_hooks_after,
    clean_only,
    env_vars,
):
    from hatch.project.config import env_var_enabled
    from hatch.project.constants import BUILD_BACKEND, BuildEnvVars
    from hatch.utils.runner import ExecutionContext

    for target in targets:
        target_name, _, _ = target.partition(":")
        if not clean_only:
            app.display_header(target_name)

        if build_backend != BUILD_BACKEND:
            if target_name == "sdist":
                directory = _legacy_build_directory(project, location)
                directory.ensure_dir_exists()
                artifact_path = project.build_frontend.build_sdist(directory)
            elif target_name == "wheel":
                directory = _legacy_build_directory(project, location)
                directory.ensure_dir_exists()
                artifact_path = project.build_frontend.build_wheel(directory)
            else:
                app.abort(f"Target `{target_name}` is not supported by `{build_backend}`")
                return

            app.display_info(
                str(artifact_path.relative_to(project.location))
                if project.location in artifact_path.parents
                else str(artifact_path)
            )
            continue

        command = ["python", "-u", "-m", "hatchling", "build", "--target", target]

        # We deliberately pass the location unchanged so that absolute paths may be non-local
        # and reflect wherever builds actually take place
        if location:
            command.extend(("--directory", str(location)))

        if hooks_only or env_var_enabled(BuildEnvVars.HOOKS_ONLY):
            command.append("--hooks-only")

        if no_hooks or env_var_enabled(BuildEnvVars.NO_HOOKS):
            command.append("--no-hooks")

        if clean or env_var_enabled(BuildEnvVars.CLEAN):
            command.append("--clean")

        if clean_hooks_after or env_var_enabled(BuildEnvVars.CLEAN_HOOKS_AFTER):
            command.append("--clean-hooks-after")

        if clean_only:
            command.append("--clean-only")

        context = ExecutionContext(project.build_env)
        context.add_shell_command(command)
        context.env_vars.update(env_vars)
        app.execute_context(context)


def _legacy_build_directory(project, location):
    from hatch.project.constants import DEFAULT_BUILD_DIRECTORY
    from hatch.utils.fs import Path

    return Path(location).resolve() if location else project.location / DEFAULT_BUILD_DIRECTORY
