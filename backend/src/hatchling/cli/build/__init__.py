from __future__ import annotations

import argparse
from typing import Any


def build_impl(
    *,
    called_by_app: bool,  # noqa: ARG001
    directory: str,
    targets: list[str],
    hooks_only: bool,
    no_hooks: bool,
    clean: bool,
    clean_hooks_after: bool,
    clean_only: bool,
    show_dynamic_deps: bool,
) -> None:
    import os

    from hatchling.bridge.app import Application
    from hatchling.builders.constants import BuildEnvVars
    from hatchling.metadata.core import ProjectMetadata
    from hatchling.plugin.manager import PluginManager

    app = Application()

    if hooks_only and no_hooks:
        app.abort("Cannot use both --hooks-only and --no-hooks together")

    root = os.getcwd()
    plugin_manager = PluginManager()
    metadata = ProjectMetadata(root, plugin_manager)

    # One entry per `--target` argument: (raw value, target name, requested versions)
    if targets:
        target_specs = [_parse_target_spec(data) for data in targets]
    else:  # no cov
        target_specs = [("sdist", "sdist", []), ("wheel", "wheel", [])]

    # Grouped view preserving the historical de-duplication of target names
    target_data: dict[str, list[str]] = {}
    for _raw, target_name, versions in target_specs:
        target_data.setdefault(target_name, []).extend(versions)

    builders = {}
    unknown_targets = []
    for target_name in target_data:
        builder_class = plugin_manager.builder.get(target_name)
        if builder_class is None:
            unknown_targets.append(target_name)
        else:
            builders[target_name] = builder_class

    if unknown_targets:
        app.abort(f"Unknown build targets: {', '.join(sorted(unknown_targets))}")

    # We guarantee that builds occur within the project directory
    root = os.getcwd()

    if no_hooks:
        os.environ[BuildEnvVars.NO_HOOKS] = "true"

    if show_dynamic_deps:
        _show_dynamic_deps(app, builders, target_data, root, plugin_manager, metadata)
        return

    # The application coordinates the transaction when it drives builds one target at a time
    if not (hooks_only or clean_only) and BuildEnvVars.GENERATION in os.environ:
        _build_as_participant(
            app,
            builders,
            target_specs,
            root=root,
            plugin_manager=plugin_manager,
            metadata=metadata,
            hooks_only=hooks_only,
            clean=clean,
            clean_hooks_after=clean_hooks_after,
            clean_only=clean_only,
        )
        return

    if hooks_only or clean_only:
        _build_directly(
            app,
            builders,
            target_data,
            root=root,
            plugin_manager=plugin_manager,
            metadata=metadata,
            directory=directory,
            hooks_only=hooks_only,
            clean=clean,
            clean_hooks_after=clean_hooks_after,
            clean_only=clean_only,
        )
        return

    _build_transactional(
        app,
        builders,
        target_specs,
        root=root,
        plugin_manager=plugin_manager,
        metadata=metadata,
        directory=directory,
        clean=clean,
        clean_hooks_after=clean_hooks_after,
    )


def _parse_target_spec(data: str) -> tuple[str, str, list[str]]:
    target_name, _, version_data = data.partition(":")
    versions = version_data.split(",") if version_data else []
    return data, target_name, versions


def _resolve_directory(builder, directory, root):
    import os

    from hatchling.builders.constants import BuildEnvVars

    if directory:
        return os.path.normpath(directory if os.path.isabs(directory) else os.path.join(root, directory))
    if BuildEnvVars.LOCATION in os.environ:
        return builder.config.normalize_build_directory(os.environ[BuildEnvVars.LOCATION])
    return builder.config.directory


def _display_artifact(app, artifact, root, display_directory=None):
    import os

    if display_directory is not None:
        # The artifact still resides in the isolated directory at this point, so existence is
        # checked against it while the displayed path is where it will end up after commit
        if not os.path.isfile(artifact):
            app.display_info(os.path.join(display_directory, os.path.basename(artifact)))
            return

        display_path = os.path.join(display_directory, os.path.basename(artifact))
    else:
        display_path = artifact
        if not os.path.isfile(display_path):  # no cov
            app.display_info(display_path)
            return

    if display_path == root or display_path.startswith(root + os.sep):
        app.display_info(os.path.relpath(display_path, root))
    else:
        app.display_info(display_path)


def _clean_rules(target_name, artifact_names):
    if target_name == "sdist":
        return {"suffixes": (".tar.gz",), "names": ()}
    if target_name == "wheel":
        return {"suffixes": (".whl",), "names": ()}
    return {"suffixes": (), "names": tuple(artifact_names)}


def _show_dynamic_deps(app, builders, target_data, root, plugin_manager, metadata):
    dynamic_dependencies: dict[str, None] = {}
    for target_name in target_data:
        builder = builders[target_name](
            root, plugin_manager=plugin_manager, metadata=metadata, app=app.get_safe_application()
        )
        for dependency in builder.config.dynamic_dependencies:
            dynamic_dependencies[dependency] = None

    app.display(str(list(dynamic_dependencies)))


def _build_directly(
    app,
    builders,
    target_data,
    *,
    root,
    plugin_manager,
    metadata,
    directory,
    hooks_only,
    clean,
    clean_hooks_after,
    clean_only,
):
    import os

    for i, (target_name, versions) in enumerate(target_data.items()):
        # Separate targets with a blank line
        if not clean_only and i != 0:  # no cov
            app.display_info()

        # Display name before instantiation in case of errors
        if not clean_only and len(target_data) > 1:
            app.display_mini_header(target_name)

        builder = builders[target_name](
            root, plugin_manager=plugin_manager, metadata=metadata, app=app.get_safe_application()
        )

        for artifact in builder.build(
            directory=directory,
            versions=versions,
            hooks_only=hooks_only,
            clean=clean,
            clean_hooks_after=clean_hooks_after,
            clean_only=clean_only,
        ):
            if os.path.isfile(artifact) and artifact.startswith(root):
                app.display_info(os.path.relpath(artifact, root))
            else:  # no cov
                app.display_info(artifact)


def _build_as_participant(
    app,
    builders,
    target_specs,
    *,
    root,
    plugin_manager,
    metadata,
    hooks_only,
    clean,
    clean_hooks_after,
    clean_only,
):
    import os

    from hatchling.builders import staging
    from hatchling.builders.constants import BuildEnvVars

    final_directory = os.environ[BuildEnvVars.FINAL_LOCATION]
    generation = os.environ[BuildEnvVars.GENERATION]
    isolated_directory = staging.artifacts_directory(final_directory, generation)

    for index, (_raw, target_name, versions) in enumerate(target_specs):
        # Separate targets with a blank line
        if not clean_only and index != 0:  # no cov
            app.display_info()

        # Display name before instantiation in case of errors
        if not clean_only and len(target_specs) > 1:
            app.display_mini_header(target_name)

        builder = builders[target_name](
            root, plugin_manager=plugin_manager, metadata=metadata, app=app.get_safe_application()
        )

        produced = []
        for artifact in builder.build(
            directory=isolated_directory,
            versions=versions,
            hooks_only=hooks_only,
            clean=clean,
            clean_hooks_after=clean_hooks_after,
            clean_only=clean_only,
        ):
            produced.append(artifact)
            _display_artifact(app, artifact, root, display_directory=final_directory)

        if produced and not hooks_only:
            staging.write_build_record(
                final_directory,
                generation,
                _raw,
                project=builder.metadata.core.name,
                version=builder.metadata.version,
                artifact_paths=produced,
            )


def _build_transactional(
    app,
    builders,
    target_specs,
    *,
    root,
    plugin_manager,
    metadata,
    directory,
    clean,
    clean_hooks_after,
):
    import os

    from hatchling.builders import staging

    instances = {
        target_name: builders[target_name](
            root, plugin_manager=plugin_manager, metadata=metadata, app=app.get_safe_application()
        )
        for _raw, target_name, _versions in target_specs
    }

    # Group targets by the final directory they report so that, even when every target uses a
    # custom directory, each directory is replaced as a single validated set
    groups: dict[str, list[tuple[str, str, list[str]]]] = {}
    for raw, target_name, versions in target_specs:
        final_directory = _resolve_directory(instances[target_name], directory, root)
        groups.setdefault(final_directory, []).append((raw, target_name, versions))

    target_index = 0
    for final_directory, specs in groups.items():
        generation = staging.new_generation_id()
        isolated_directory = staging.begin_generation(
            final_directory,
            generation=generation,
            session=generation,
            targets=[raw for raw, _name, _versions in specs],
        )

        try:
            produced: dict[str, list[str]] = {}
            for raw, target_name, versions in specs:
                if target_index != 0:  # no cov
                    app.display_info()
                target_index += 1

                if len(target_specs) > 1:
                    app.display_mini_header(target_name)

                builder = instances[target_name]
                artifacts = list(
                    builder.build(
                        directory=isolated_directory,
                        versions=versions,
                        clean=clean,
                        clean_hooks_after=clean_hooks_after,
                    )
                )
                produced[raw] = artifacts

                for artifact in artifacts:
                    _display_artifact(app, artifact, root, display_directory=final_directory)

                staging.write_build_record(
                    final_directory,
                    generation,
                    raw,
                    project=builder.metadata.core.name,
                    version=builder.metadata.version,
                    artifact_paths=artifacts,
                )

            clean_rules = {}
            if clean:
                for raw, target_name, _versions in specs:
                    clean_rules[raw] = _clean_rules(
                        target_name, [os.path.basename(path) for path in produced[raw]]
                    )

            staging.commit_generation(final_directory, generation, clean_rules=clean_rules)
        except BaseException:
            staging.abort_generation(final_directory, generation)
            raise


def build_command(subparsers: argparse._SubParsersAction, defaults: Any) -> None:
    parser = subparsers.add_parser("build")
    parser.add_argument(
        "-d", "--directory", dest="directory", help="The directory in which to build artifacts", **defaults
    )
    parser.add_argument(
        "-t",
        "--target",
        dest="targets",
        action="append",
        help="Comma-separated list of targets to build, overriding project defaults",
        **defaults,
    )
    parser.add_argument("--hooks-only", dest="hooks_only", action="store_true", default=None)
    parser.add_argument("--no-hooks", dest="no_hooks", action="store_true", default=None)
    parser.add_argument("-c", "--clean", dest="clean", action="store_true", default=None)
    parser.add_argument("--clean-hooks-after", dest="clean_hooks_after", action="store_true", default=None)
    parser.add_argument("--clean-only", dest="clean_only", action="store_true")
    parser.add_argument("--show-dynamic-deps", dest="show_dynamic_deps", action="store_true")
    parser.add_argument("--app", dest="called_by_app", action="store_true", help=argparse.SUPPRESS)
    parser.set_defaults(func=build_impl)
