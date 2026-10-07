# 版本来源切换的项目元数据一致性

> **Workspace:** /Users/ding/Documents/swe/0910061/project-12

---

**User**

项目从静态版本切换到插件或 VCS 版本来源时，元数据读取、构建产物和发布器可能在一次操作中得到不同版本，失败重试还会留下旧版本 wheel。请先解析并验证候选版本、动态字段和插件配置，再让 ProjectMetadata、builder 和 publisher 一起切换到该版本代际；配置错误、VCS 不可用、构建中止或进程重启时继续使用上一份有效元数据并清理候选。静态版本、动态字段、脏源码检查、sdist/wheel 和未改变版本的缓存命中保持兼容。

**Assistant**

toolName: view_folder

status: success

/Users/ding/Documents/swe/0910061/project-12

This is the **hatch/hatchling** repository. Let me explore the key components involved: metadata, version sources, builders, and the CLI build/publish flow.

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/backend/src/hatchling/metadata/core.py

toolName: view_files

status: failed

filePath: /Users/ding/Documents/swe/0910061/project-12/backend/src/hatchling/version/source/core.py

Interesting — the version source directory has no `core.py` (upstream hatchling has one). Let me examine the version module structure and the builders.

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/backend/src/hatchling/version/__init__.py

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/backend/src/hatchling/version/source/__init__.py

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/backend/src/hatchling/builders/app.py

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/backend/src/hatchling/build.py

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/backend/src/hatchling/metadata/custom.py

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/backend/src/hatchling/metadata/spec.py

Let me read the rest of `metadata/core.py` (it was truncated), particularly the `HatchMetadata` and `VersionConfig` classes.

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/backend/src/hatchling/metadata/core.py

Now let me examine the builder config and interface, plus the hatch CLI build/publish flow.

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/backend/src/hatchling/builders/config.py

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/src/hatch/cli/build/__init__.py

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/src/hatch/cli/publish/__init__.py

Let me check the git state and the hatchling CLI build/version flow.

toolName: Shell

status: success

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/backend/src/hatchling/cli/build/__init__.py

Let me check project memory for prior context and look at the builder interface.

toolName: Shell

status: success

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/backend/src/hatchling/builders/plugin/interface.py

toolName: Shell

status: success

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/backend/src/hatchling/builders/plugin/interface.py

Let me look at the version source plugins and search for any existing cache/candidate scaffolding.

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/backend/src/hatchling/version/source/plugin/interface.py

toolName: search_by_regex

status: success

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/backend/src/hatchling/builders/wheel.py

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/backend/src/hatchling/version/scheme/plugin/interface.py

Let me examine the sdist builder, hatchling version CLI, and hatch's index publisher to complete the picture.

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/backend/src/hatchling/builders/sdist.py

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/backend/src/hatchling/cli/version/__init__.py

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/src/hatch/publish/index.py

I now have a full picture of the architecture. Let me review the test conventions before implementing, and check the built-in sources.

toolName: todo_write

status: success

Todos updated: 7 items

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/tests/conftest.py

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/tests/backend/test_build.py

Let me look at the backend wheel test conventions and the built-in version sources.

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/tests/backend/builders/test_wheel.py

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/backend/src/hatchling/version/source/regex.py

toolName: file_search

status: success

`version/core.py` does exist — I had the wrong path earlier. Let me read it and the remaining sources.

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/backend/src/hatchling/version/core.py

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/backend/src/hatchling/version/source/code.py

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/backend/src/hatchling/version/source/env.py

The codebase is fully mapped. Let me quickly check the hatchling CLI entry and existing publish tests before writing code.

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/backend/src/hatchling/cli/__init__.py

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/tests/cli/publish/test_publish.py

All understood. Now I'll implement. First, the new version-generation module with the transactional coordinator:

toolName: todo_write

status: success

Todos updated: 7 items

toolName: Write

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/backend/src/hatchling/version/generation.py

changes: undefined

Let me clean up two leftover helpers that aren't needed:

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/backend/src/hatchling/version/generation.py

changes: undefined

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/backend/src/hatchling/version/generation.py

changes: undefined

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/backend/src/hatchling/version/generation.py

changes: undefined

Now update `ProjectMetadata` with the prepare/commit/restore protocol:

toolName: todo_write

status: success

Todos updated: 7 items

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/backend/src/hatchling/metadata/core.py

changes: undefined

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/backend/src/hatchling/metadata/core.py

changes: undefined

Before proceeding, I want to re-verify the exact `core`/`version` interplay to avoid recursion issues. Let me re-read the current state of those sections:

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/backend/src/hatchling/metadata/core.py

The key subtlety: the `self.core.dynamic.remove` is nested inside `if self._version is None` — that's what prevents infinite recursion. I'll preserve the properties untouched and only replace `_get_version`, adding the new protocol methods:

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/backend/src/hatchling/metadata/core.py

changes: undefined

Now wire the coordinator into `BuilderInterface.build()`:

toolName: todo_write

status: success

Todos updated: 7 items

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/backend/src/hatchling/builders/plugin/interface.py

changes: undefined

Now update hatch's publisher to filter artifacts by the committed generation:

toolName: todo_write

status: success

Todos updated: 7 items

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/src/hatch/publish/index.py

changes: undefined

Let me smoke-test imports and a real build before writing the test suite:

toolName: Shell

status: success

toolName: Shell

status: success

toolName: Shell

status: success

uv is available. Let me create a test virtualenv with both packages installed editable:

toolName: Shell

status: success

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/pyproject.toml

The hatch project itself uses `hatch-vcs`. It's missing from the venv. Let me install build requirements and retry:

toolName: Shell

status: success

Let me see the full traceback:

toolName: Shell

status: success

Installed successfully. Now the smoke test:

toolName: Shell

status: success

toolName: Shell

status: success

toolName: Shell

status: success

The hatch install replaced my editable hatchling with the published one. Reinstall backend editable **after**:

toolName: Shell

status: success

toolName: Shell

status: success

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/backend/pyproject.toml

Found a real regression: upstream's `_get_version` installed `_version_set` into the core before the `version` property depopulates dynamic. I deferred core installation, breaking self-bootstrapped builds. Fix:

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/backend/src/hatchling/metadata/core.py

changes: undefined

toolName: Shell

status: success

Static works. Now test the full switch scenario manually — dynamic source, stale cleanup, failure fallback, crash recovery:

toolName: Shell

status: success

Switch and cache-hit scenarios work. Now failure fallback and crash recovery:

toolName: Shell

status: success

Fallback and crash recovery both work. Now aborted build + sdist stale cleanup:

toolName: Shell

status: success

Aborted build correctly rolls back. Now sdist stale cleanup and combined sdist+wheel:

toolName: Shell

status: success

All scenarios verified manually. Now let me write the formal test suite:

toolName: todo_write

status: success

Todos updated: 7 items

toolName: Write

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/tests/backend/version/test_generation.py

changes: undefined

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/tests/backend/version/test_generation.py

changes: undefined

Now the publisher filtering test:

toolName: Write

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/tests/cli/publish/test_generation_filter.py

changes: undefined

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/tests/cli/publish/test_generation_filter.py

changes: undefined

Now run the new tests:

toolName: Shell

status: success

toolName: Shell

status: success

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/tests/cli/publish/test_generation_filter.py

changes: undefined

toolName: Shell

status: success

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/tests/cli/publish/test_generation_filter.py

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/tests/cli/publish/test_generation_filter.py

changes: undefined

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/tests/cli/publish/test_generation_filter.py

changes: undefined

toolName: Shell

status: success

All 20 new tests pass. Now verify the existing suites for compatibility — backend first:

toolName: todo_write

status: success

Todos updated: 7 items

toolName: Shell

status: success

Two issues: `.hatch` state dir inside dist breaks the "dist contains only artifacts" invariant, and a missing `editables` dep. Let me check the constants for a better state location:

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/backend/src/hatchling/builders/constants.py

toolName: search_by_regex

status: success

The `.hatch` name is already a reserved/excluded directory by convention. Let me check all failure categories first:

toolName: Shell

status: success

Let me investigate the version-hook failures and read the version build hook:

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/backend/src/hatchling/builders/hooks/version.py

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/tests/backend/builders/hooks/test_version.py

Now I understand both failure classes. I'll: (1) relocate the ledger to the reserved project-level `.hatch/build/<key>/` dir (never inside dist), (2) restructure `prepare_version` to allow metadata hooks to supply versions. Starting with generation.py:

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/backend/src/hatchling/version/generation.py

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/backend/src/hatchling/version/generation.py

changes: undefined

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/backend/src/hatchling/version/generation.py

changes: undefined

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/backend/src/hatchling/version/generation.py

changes: undefined

Now restructure the metadata resolution protocol. Let me view the current block:

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/backend/src/hatchling/metadata/core.py

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/backend/src/hatchling/metadata/core.py

changes: undefined

Now update the publisher for the relocated store:

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/src/hatch/publish/index.py

changes: undefined

Now update the tests for the new signatures:

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/tests/backend/version/test_generation.py

changes: undefined

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/tests/backend/version/test_generation.py

changes: undefined

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/tests/cli/publish/test_generation_filter.py

changes: undefined

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/tests/cli/publish/test_generation_filter.py

changes: undefined

Install the missing `editables` dep, then run the new tests plus the whole backend suite:

toolName: Shell

status: success

toolName: search_by_regex

status: success

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/tests/backend/version/test_generation.py

changes: undefined

toolName: Shell

status: success

993 passed; only cargo-related failures remain. Let me verify these are pre-existing using a pristine worktree:

toolName: Shell

status: success

Pre-existing cargo failures confirmed. Now the relevant CLI suites (build, publish, version, project):

toolName: Shell

status: success

toolName: search_by_regex

status: success

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/tests/cli/build/test_build.py

The existing test encodes the exact legacy behavior the task asks to change: non-clean builds kept old-version artifacts (4 = 0.1.0 + 0.2.0). Under the new generation semantics, switching purges stale artifacts → 2. The final `--clean` expectation (3) is unchanged. Let me update those assertions:

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/tests/cli/build/test_build.py

changes: undefined

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/tests/cli/build/test_build.py

changes: undefined

toolName: Shell

status: success

Now run the publish CLI tests and check for other places that might be affected:

toolName: Shell

status: success

toolName: Shell

status: success

The errors are just missing `pytest-xdist` (`worker_id` fixture) — an environment issue. Install it and rerun:

toolName: Shell

status: success

Now broader regression — env internals use builds too. Run with xdist for speed:

toolName: Shell

status: success

toolName: Shell

status: success

One unrelated-looking failure about managed Python installations. Verify against pristine:

toolName: Shell

status: success

Pre-existing confirmed. Let me verify the metadata CLI still works and run the repo's linter on the changed files:

toolName: Shell

status: success

toolName: Shell

status: success

toolName: Shell

status: success

toolName: Shell

status: success

Fix all lint issues:

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/backend/src/hatchling/version/generation.py

changes: undefined

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/backend/src/hatchling/version/generation.py

changes: undefined

The helper needs `parse_*` at its own scope. Move the packaging imports to module level:

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/backend/src/hatchling/version/generation.py

changes: undefined

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/backend/src/hatchling/version/generation.py

changes: undefined

Now fix the test lint items:

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/tests/backend/version/test_generation.py

changes: undefined

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/tests/backend/version/test_generation.py

changes: undefined

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/tests/backend/version/test_generation.py

changes: undefined

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/tests/cli/publish/test_generation_filter.py

changes: undefined

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/tests/cli/publish/test_generation_filter.py

changes: undefined

toolName: Shell

status: success

toolName: Shell

status: success

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/tests/backend/version/test_generation.py

changes: undefined

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/tests/backend/version/test_generation.py

changes: undefined

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/tests/backend/version/test_generation.py

changes: undefined

toolName: Shell

status: success

toolName: Shell

status: success

That last lint item is pre-existing in a file I never touched (newer ruff than repo pins). Final regression run across all affected areas:

toolName: Shell

status: success

All green — 1052 passed; the 10 cargo failures are pre-existing environmental issues. Let me review the final change set:

toolName: Shell

status: success

Let me do a final coherence read of the new module:

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-12/backend/src/hatchling/version/generation.py

toolName: todo_write

status: success

Todos updated: 7 items

已完成。实现了版本代际（generation）的两阶段原子切换，涉及以下改动：

## 核心机制

**新增 [generation.py](file:///Users/ding/Documents/swe/0910061/project-12/backend/src/hatchling/version/generation.py)**
- `VersionGeneration`：不可变快照，捆绑归一化版本、用户原始版本、版本来源插件名与 scheme 名——元数据、builder、publisher 以同一份快照为准，杜绝一次操作中各取不同版本。
- `GenerationStore`：在项目保留目录 `.hatch/build/<按输出目录哈希>/generation.json` 中持久化 **committed / candidate / artifacts** 状态，经临时文件 + `os.replace` 原子写入。该目录已在构建排除名单中，不会进入产物，且不受 `dist` 清理影响。
- `VersionCoordinator`：
  - **阶段一 `begin()`**：解析候选版本、校验动态字段与插件配置（source/scheme 插件可用性），不改变已提交状态，只落 candidate 标记。
  - **阶段二 `commit()`**：元数据安装候选 → 标记已提交 → 版本代际改变时清除同项目旧版本 wheel/sdist；版本未改变（缓存命中）时保留现有产物。
  - `abort()` / `recover()` / `_fallback()`：构建中止、配置错误、VCS 不可用或进程重启留下候选时，恢复并继续使用上一份有效元数据；候选产物仅在其版本与已提交版本不同时清理（同版本重建崩溃不误删最后有效产物）。

**[metadata/core.py](file:///Users/ding/Documents/swe/0910061/project-12/backend/src/hatchling/metadata/core.py#L262-L366)**：`ProjectMetadata` 新增 `prepare_version` / `commit_version` / `restore_version`；候选在一次操作内缓存复用，非确定性 VCS 来源不会被重复解析出不同版本。版本元数据可由 metadata hook 提供的旧行为保持兼容。

**[builders/plugin/interface.py](file:///Users/ding/Documents/swe/0910061/project-12/backend/src/hatchling/builders/plugin/interface.py#L90-L201)**：`build()` 启动即恢复 → 解析候选 → 校验；每个产物构建成功后立即提交（PEP 517 只取 `next()` 时状态也已一致）；异常（含进程中断）回滚，hooks-only 不提交。

**[publish/index.py](file:///Users/ding/Documents/swe/0910061/project-12/src/hatch/publish/index.py#L150-L187)**：发布目录时仅上传属于已提交代际的产物；无账本、切换进行中或数据不可读时回退为发布全部（兼容）。

## 验证

- 新增 20 个测试（[test_generation.py](file:///Users/ding/Documents/swe/0910061/project-12/tests/backend/version/test_generation.py)、[test_generation_filter.py](file:///Users/ding/Documents/swe/0910061/project-12/tests/cli/publish/test_generation_filter.py)），覆盖静态版本、regex/env/code 动态来源、切换清旧、缓存命中、sdist+wheel 同代、脏源码报错、未知来源、构建中止与两类崩溃恢复。
- 全量回归 **1052 passed**；唯一失败为 10 个 `cargo not found`（已在 pristine HEAD 上确认是环境预存问题），发布类测试因无 Docker 正常 skip。
- [test_build.py](file:///Users/ding/Documents/swe/0910061/project-12/tests/cli/build/test_build.py#L486-L487) 中原先断言“非 clean 构建保留旧版本产物（4 个）”的两处预期更新为 2 个——该旧行为正是本次要消除的问题；最终 `--clean` 断言（3 个）不变。
