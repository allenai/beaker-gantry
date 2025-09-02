# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## [v2.8.6](https://github.com/allenai/beaker-gantry/releases/tag/v2.8.6) - 2025-09-02

### Fixed

- Fixed the error message when cluster constraints can't be satisfied.

## [v2.8.5](https://github.com/allenai/beaker-gantry/releases/tag/v2.8.5) - 2025-07-17

### Added

- Added support for choosing clusters based on tags (e.g. `gantry run --tag='storage:weka' ...`).

### Changed

- Gantry will automatically apply a `--tag='storage:weka'` cluster filter rule when you use a `--weka` option.

### Fixed

- Fixed bug with attempting to accept TOS on older versions of conda.

## [v2.8.4](https://github.com/allenai/beaker-gantry/releases/tag/v2.8.4) - 2025-07-16

### Fixed

- Added work-around for webi `gh` bug (https://github.com/webinstall/webi-installers/issues/1003).

## [v2.8.3](https://github.com/allenai/beaker-gantry/releases/tag/v2.8.3) - 2025-07-15

### Fixed

- Fixed matching clusters based on aliases.

## [v2.8.2](https://github.com/allenai/beaker-gantry/releases/tag/v2.8.2) - 2025-07-15

### Fixed

- Ensure conda TOS are accepted for default channels.

## [v2.8.1](https://github.com/allenai/beaker-gantry/releases/tag/v2.8.1) - 2025-07-08

### Changed

 - Added `cmake` to the default docker image.

## [v2.8.0](https://github.com/allenai/beaker-gantry/releases/tag/v2.8.0) - 2025-07-07

### Added

- Added `-f/--follow` option to `gantry logs`.
- Added `--python-version` option to `gantry run` for overriding the default Python version to use.

### Changed

- Changed default beaker image to [`petew/gantry`](https://beaker.allen.ai/orgs/ai2/workspaces/gantry-testing/images) which includes all required gantry tools to reduce start-up time. It also includes `uv`.

### Fixed

- Made installing/upgrading the `pip` package manager more robust, and added a check to ensure the pip version being used is in the active virtual environment.

## [v2.7.1](https://github.com/allenai/beaker-gantry/releases/tag/v2.7.1) - 2025-06-25

### Fixed

- Fixed error handling / automatic retries of downloads in entrypoint script.

## [v2.7.0](https://github.com/allenai/beaker-gantry/releases/tag/v2.7.0) - 2025-06-24

### Added

- Added `--run` option to `gantry logs` for specifying a run number.

## [v2.6.2](https://github.com/allenai/beaker-gantry/releases/tag/v2.6.2) - 2025-06-11

### Added

- Added task status information for each replica when a workload fails.

## [v2.6.1](https://github.com/allenai/beaker-gantry/releases/tag/v2.6.1) - 2025-06-10

### Fixed

- Also set LL128 env vars for NCCL.

## [v2.6.0](https://github.com/allenai/beaker-gantry/releases/tag/v2.6.0) - 2025-06-04

### Changed

- When `--install` option is a shell script, it will now be `source`-ed instead `eval`-ed so that environment variables set from the script will be set in the main process.
- Gantry will automatically configure NCCL for TCPXO when running multi-node jobs on Augusta so you don't have to set all of the environment variables document here: https://beaker-docs.apps.allenai.org/compute/augusta.html#distributed-workloads. You can skip this in case you want to configure TCPXO differently by using the flag `--skip-tcpxo-setup`.

## [v2.5.0](https://github.com/allenai/beaker-gantry/releases/tag/v2.5.0) - 2025-06-03

### Added

- Added `launch_experiment` function to public `gantry.api` module.

## [v2.4.0](https://github.com/allenai/beaker-gantry/releases/tag/v2.4.0) - 2025-06-02

### Added

- Added a public Python API `gantry.api` with some useful methods.
- Added `--gpu-type` option to `gantry run`.

### Fixed

- Added work-around for when `ensurepip` package is not installed.

## [v2.3.0](https://github.com/allenai/beaker-gantry/releases/tag/v2.3.0) - 2025-05-15

### Added

- Added prompt to cancel experiment on keyboard interrupt.
- Added `--branch` argument to `gantry run` for overriding the branch to use.
- Added `--group` argument to `gantry run` for adding the experiment to a group, and to `gantry list` for listing experiments within a group.

### Fixed

- (performance) Made entrypoint script more robust to transient errors.
- (performance) Avoid creating new conda environments when default Python version matches target Python version.
- Made git ref/remote/branch resolution more robust, and provide better error messages.
- Format creation time in local time from `gantry list`.

## [v2.2.0](https://github.com/allenai/beaker-gantry/releases/tag/v2.2.0) - 2025-05-13

### Added

- Added `gantry open` command for opening Beaker resources in your browser.

### Changed

- Gantry will now continue to follow experiments after their main job gets preempted.

### Fixed

- (bug) Fixed filtering with `--all` in `gantry list` command.
- (performance) Made `gantry list` much faster by using a thread pool to query for task status.
- (performance) Made setup steps much faster by using webi to install the GitHub CLI, when needed, instead of conda.

## [v2.1.1](https://github.com/allenai/beaker-gantry/releases/tag/v2.1.1) - 2025-05-09

### Fixed

- (optimization) Gantry will only clone the target branch at runtime instead of all branches on the remote.

## [v2.1.0](https://github.com/allenai/beaker-gantry/releases/tag/v2.1.0) - 2025-05-08

### Added

- Added `--all` flag to `gantry list` to search all experiments, not just ones submitted through Gantry.
- Added `gantry find-gpus` command to list clusters with free GPUs.

## [v2.0.2](https://github.com/allenai/beaker-gantry/releases/tag/v2.0.2) - 2025-05-05

### Fixed

- Fixed bug when specifying multiple clusters.

## [v2.0.1](https://github.com/allenai/beaker-gantry/releases/tag/v2.0.1) - 2025-05-02

### Added

- Added color to Gantry messages from the entrypoint script.
- Added `--log-level` global option.

### Fixed

- Fixed how task status is rendered from the `gantry list` command.

## [v2.0.0](https://github.com/allenai/beaker-gantry/releases/tag/v2.0.0) - 2025-05-01

### Changed

- Python >= 3.10 required.
- (internal) Switched to the new RPC-based beaker-py client (https://github.com/allenai/beaker/pull/6478).

### Removed

- Removed `gantry cluster` commands.

### Fixed

- Don't prompt for budget when workspace has a default budget associate with it.

## [v1.17.0](https://github.com/allenai/beaker-gantry/releases/tag/v1.17.0) - 2025-04-28

### Added

- Added `--results` option to `gantry run` for changing the default results path.

## [v1.16.0](https://github.com/allenai/beaker-gantry/releases/tag/v1.16.0) - 2025-04-23

### Changed

- Gantry now uses the new RPC interface to follow experiments / stream logs.

## [v1.15.0](https://github.com/allenai/beaker-gantry/releases/tag/v1.15.0) - 2025-04-14

### Added

- Added `--secret-env` as an alias for the `--env-secret` option to the `gantry run` command to be consistent with the corresponding flag in `beaker session create`.

## [v1.14.1](https://github.com/allenai/beaker-gantry/releases/tag/v1.14.1) - 2025-03-24

### Fixed

- Made args parsing more robust to catch the scenario where a value is accidentally provided to a flag option.

## [v1.14.0](https://github.com/allenai/beaker-gantry/releases/tag/v1.14.0) - 2025-03-19

### Added

- Added `--not-preemptible` option to `gantry run` to force a job to not be preemptible.

## [v1.13.0](https://github.com/allenai/beaker-gantry/releases/tag/v1.13.0) - 2025-02-25

### Added

- Added `--task-timeout` option to `gantry run` command.

## [v1.12.2](https://github.com/allenai/beaker-gantry/releases/tag/v1.12.2) - 2025-02-21

### Removed

- Removed NFS option.

## [v1.12.1](https://github.com/allenai/beaker-gantry/releases/tag/v1.12.1) - 2025-01-27

### Added

- Added an additional check at runtime which will raise an error if the current ref doesn't exist on the remote.

## [v1.12.0](https://github.com/allenai/beaker-gantry/releases/tag/v1.12.0) - 2025-01-15

### Added

- Added `--dataset-secret` option for mounting secrets to files as Beaker datasets.

## [v1.11.3](https://github.com/allenai/beaker-gantry/releases/tag/v1.11.3) - 2025-01-09

## [v1.11.0](https://github.com/allenai/beaker-gantry/releases/tag/v1.11.0) - 2025-01-09

### Added

- Added `--no-conda` flag to avoid creating Python environments with conda.

## [v1.10.1](https://github.com/allenai/beaker-gantry/releases/tag/v1.10.1) - 2025-01-09

### Fixed

- Don't install conda when it's not needed.

## [v1.10.0](https://github.com/allenai/beaker-gantry/releases/tag/v1.10.0) - 2024-11-21

### Added

- Added `--ref` command-line argument to `gantry run` for overriding the target git ref (commit/branch/tag) to use.

## [v1.9.1](https://github.com/allenai/beaker-gantry/releases/tag/v1.9.1) - 2024-11-20

### Fixed

- Use Beaker image ID instead of assigned name.

## [v1.9.0](https://github.com/allenai/beaker-gantry/releases/tag/v1.9.0) - 2024-11-01

### Added

- Added `--retries` option to `gantry run` command.

## [v1.8.4](https://github.com/allenai/beaker-gantry/releases/tag/v1.8.4) - 2024-10-06

### Fixed

- Exclude saturn and neptune clusters from auto NFS

## [v1.8.3](https://github.com/allenai/beaker-gantry/releases/tag/v1.8.3) - 2024-08-02

### Fixed

- Fixed a bug where `--docker-image` was raising an error due to default value assigned to `--beaker-image`.

## [v1.8.2](https://github.com/allenai/beaker-gantry/releases/tag/v1.8.2) - 2024-07-17

### Fixed

- Fixed a bug with displaying experiment results when there are replicas.

## [v1.8.1](https://github.com/allenai/beaker-gantry/releases/tag/v1.8.1) - 2024-07-17

### Fixed

- Made parsing env vars, secrets, and mounts more robust.

## [v1.8.0](https://github.com/allenai/beaker-gantry/releases/tag/v1.8.0) - 2024-07-14

### Added

- Added `gantry logs` command.

## [v1.7.1](https://github.com/allenai/beaker-gantry/releases/tag/v1.7.1) - 2024-07-10

### Fixed

- Fixed bug where successful experiments would exit with non-zero exit code due to `tee`-ing the output to a logs file that wasn't used anyway.

## [v1.7.0](https://github.com/allenai/beaker-gantry/releases/tag/v1.7.0) - 2024-06-21

### Added

- Added `--propagate-preemption` flag to `gantry run`.

## [v1.6.0](https://github.com/allenai/beaker-gantry/releases/tag/v1.6.0) - 2024-06-14

### Added

- Added `-l/--latest`, `-w/--workspace`, `-a/--author` options to `gantry follow` command.
- Added a confirmation prompt to `gantry stop` command.
- Added `--weka` option to `gantry run` for mounting weka buckets.

### Fixed

- Only check for upgrades once every 12 hours by default.

## [v1.5.1](https://github.com/allenai/beaker-gantry/releases/tag/v1.5.1) - 2024-06-13

### Added

- Added a breakdown of jobs by priority in `gantry cluster util` command.

## [v1.5.0](https://github.com/allenai/beaker-gantry/releases/tag/v1.5.0) - 2024-06-10

### Added

- Git submodules of your repo will be automatically cloned.
- Added `-l/--latest`, `-w/--workspace`, and `--dry-run` options to `gantry stop` command.

### Fixed

- Don't automatically attach NFS to "jupiter 2" cluster.

## [v1.4.0](https://github.com/allenai/beaker-gantry/releases/tag/v1.4.0) - 2024-05-31

### Added

- Added `gantry completion ...` commands for configuring `gantry` shell autocompletion.

## [v1.3.0](https://github.com/allenai/beaker-gantry/releases/tag/v1.3.0) - 2024-05-31

### Added

- Added `--tail` option to `gantry follow` to only tail the logs as opposed to dumping the entire history.

## [v1.2.0](https://github.com/allenai/beaker-gantry/releases/tag/v1.2.0) - 2024-05-30

### Changed

- Changed what info is displayed by default from `gantry cluster util`. Now only a succinct summary is shown by default, but you can still get node details by adding the flag `--nodes`.
- Allow multiple `--status` options with `gantry list` command.

## [v1.1.0](https://github.com/allenai/beaker-gantry/releases/tag/v1.1.0) - 2024-05-29

### Added

- Added `gantry list` command for listing gantry experiments.

### Fixed

- Improve handling of jobs that fail without an exit code.
- Improved output format of `gantry cluster *` commands.

### Removed

- Removed `gantry cluster allow-preemptible` and `gantry cluster disallow-preemptible` commands.

## [v1.0.1](https://github.com/allenai/beaker-gantry/releases/tag/v1.0.1) - 2024-05-24

### Fixed

- Fixed formatting in `gantry cluster` and `gantry config` commands.

## [v1.0.0](https://github.com/allenai/beaker-gantry/releases/tag/v1.0.0) - 2024-05-24

### Added

- Added `gantry stop` command.

## [v0.24.0](https://github.com/allenai/beaker-gantry/releases/tag/v0.24.0) - 2024-05-21

### Added

- Added `--no-python` flag to skip setting up a Python environment entirely.
- Added `GANTRY_TASK_NAME` runtime environment variable, which will always match the `--task-name` argument.

### Changed

- Gantry no longer cancels an experiment on keyboard interrupt.

## [v0.23.2](https://github.com/allenai/beaker-gantry/releases/tag/v0.23.2) - 2024-05-16

### Fixed

- Don't automatically attach NFS to "jupiter" cluster.

## [v0.23.1](https://github.com/allenai/beaker-gantry/releases/tag/v0.23.1) - 2024-05-14

### Changed

- Retry `git clone` a few times in the entrypoint script to be more robust to issues on the Jupiter cluster.

## [v0.23.0](https://github.com/allenai/beaker-gantry/releases/tag/v0.23.0) - 2024-05-10

### Added

- Added `--preemptible` flag.

## [v0.22.4](https://github.com/allenai/beaker-gantry/releases/tag/v0.22.4) - 2024-04-30

### Added

- Added `--synchronized-start-timeout` option.

## [v0.22.3](https://github.com/allenai/beaker-gantry/releases/tag/v0.22.3) - 2024-04-24

### Added

- Added `--propagate-failure` flag.

## [v0.22.2](https://github.com/allenai/beaker-gantry/releases/tag/v0.22.2) - 2024-03-01

### Fixed

- Warn instead of fail when we can't preempt jobs.

## [v0.22.1](https://github.com/allenai/beaker-gantry/releases/tag/v0.22.1) - 2024-02-28

### Fixed

- Don't consider default "ai2" account a workspace contributor.

## [v0.22.0](https://github.com/allenai/beaker-gantry/releases/tag/v0.22.0) - 2024-02-28

### Added

- Added flag `--stop-preemptible` to `gantry run` for stopping all preemptible jobs on the cluster. This requires that your job is not preemptible and you've specified a single cluster.
- Added subcommands `gantry cluster allow-preemptible [CLUSTER]` and `gantry cluster disallow-preemptible [CLUSTER]`.

### Changed

- Won't prompt for name if `--yes` flag is given.

## [v0.21.0](https://github.com/allenai/beaker-gantry/releases/tag/v0.21.0) - 2024-01-30

### Added

- Added `--budget` option (required).

## [v0.20.1](https://github.com/allenai/beaker-gantry/releases/tag/v0.20.1) - 2023-12-15

### Fixed

- Changed how unique names are generated so always 2 characters plus 2 digits.

## [v0.20.0](https://github.com/allenai/beaker-gantry/releases/tag/v0.20.0) - 2023-12-15

### Changed

- When you try to launch an experiment through `gantry` with a `--name` that already exists on Beaker, `gantry` will now add a few random characters to the end of the name instead of throwing an error.

## [v0.19.0](https://github.com/allenai/beaker-gantry/releases/tag/v0.19.0) - 2023-09-08

### Added

- Added commands `gantry cluster list` and `gantry cluster util` for listing clusters and showing cluster utilization, respectively.

## [v0.18.0](https://github.com/allenai/beaker-gantry/releases/tag/v0.18.0) - 2023-08-23

### Added

- Added `gantry follow [EXPERIMENT]` command for following the logs of a running experiment.

## [v0.17.2](https://github.com/allenai/beaker-gantry/releases/tag/v0.17.2) - 2023-07-21

### Fixed

- Provide a more useful error message when you pass a path to `--venv` and that path doesn't exist.

## [v0.17.1](https://github.com/allenai/beaker-gantry/releases/tag/v0.17.1) - 2023-07-12

### Fixed

- Fixed bug when workspace permissions are `None`.

## [v0.17.0](https://github.com/allenai/beaker-gantry/releases/tag/v0.17.0) - 2023-06-23

### Added

- Added `--hostname` constraint option.

## [v0.16.0](https://github.com/allenai/beaker-gantry/releases/tag/v0.16.0) - 2023-05-22

### Added

- Added support for subpaths when attaching datasets. For example: `--dataset 'dataset-name:sub/path:/mount/location'`.

## [v0.15.1](https://github.com/allenai/beaker-gantry/releases/tag/v0.15.1) - 2023-05-08

### Fixed

- Don't override existing `PYTHONPATH` entries.

## [v0.15.0](https://github.com/allenai/beaker-gantry/releases/tag/v0.15.0) - 2023-05-08

### Added

- Added the `-m/--mount` option for mounting a host directory to experiments.

## [v0.14.1](https://github.com/allenai/beaker-gantry/releases/tag/v0.14.1) - 2023-04-17

### Fixed

- Fixed a bug where some dependencies were not actually installed.

## [v0.14.0](https://github.com/allenai/beaker-gantry/releases/tag/v0.14.0) - 2023-04-17

### Added

- Added automatic support for `pyproject.toml` and `setup.cfg` files in addition to `setup.py`.

## [v0.13.1](https://github.com/allenai/beaker-gantry/releases/tag/v0.13.1) - 2023-03-20

### Fixed

- Fixed issue where certain characters (like brackets) wouldn't be displayed in the logs output
  when following the experiment with `--timeout -1`.

## [v0.13.0](https://github.com/allenai/beaker-gantry/releases/tag/v0.13.0) - 2023-03-09

### Changed

- A GitHub personal access token is no-longer required for public repos.

## [v0.12.0](https://github.com/allenai/beaker-gantry/releases/tag/v0.12.0) - 2023-03-08

### Added

- Added three options: `--replicas` (int), `--leader-selection` (flag), and `--host-networking` (flag) that give you the ability to run [distributed batch jobs](https://beaker-docs.apps.allenai.org/distributed-training.html#batch-jobs).

### Changed

- You can now use any image as long as it comes with `bash`. `conda` is no longer a requirement.

## [v0.11.0](https://github.com/allenai/beaker-gantry/releases/tag/v0.11.0) - 2023-03-07

### Added

- Added the ability to override how packages/dependencies are installed via
  the option `--install`.

## [v0.10.0](https://github.com/allenai/beaker-gantry/releases/tag/v0.10.0) - 2023-03-07

### Changed

- You can now specify the `--cluster` option as a wildcard, e.g. `--cluster ai2/*-cirrascale`.

## [v0.9.4](https://github.com/allenai/beaker-gantry/releases/tag/v0.9.4) - 2023-03-07

### Fixed

- Improved how `--beaker-image` option is resolved.

## [v0.9.3](https://github.com/allenai/beaker-gantry/releases/tag/v0.9.3) - 2023-03-02

### Fixed

- Fixed issue where cirrascale NFS would be potentially be attached to non-cirrascale machines when `--clusters` is left unspecified.
- Fixed issue where Gantry would not use a conda `environment.yaml` file by default (only found file with `.yml` extension).

## [v0.9.2](https://github.com/allenai/beaker-gantry/releases/tag/v0.9.2) - 2023-03-02

### Changed

- Loosened version requirements on some dependencies.

## [v0.9.1](https://github.com/allenai/beaker-gantry/releases/tag/v0.9.1) - 2023-02-13

### Changed

- Fix NFS location issue.

## [v0.9.0](https://github.com/allenai/beaker-gantry/releases/tag/v0.9.0) - 2023-02-10

### Changed

- You can now set the priority of your jobs via `--priority`.
- By default if you don't specify a cluster and priority, jobs will be submitted to all clusters under preemptible priority.

## [v0.8.2](https://github.com/allenai/beaker-gantry/releases/tag/v0.8.2) - 2023-01-19

### Added

- Added `--env` and `--env-secret` options for adding environment variables to your Beaker experiments.

## [v0.8.1](https://github.com/allenai/beaker-gantry/releases/tag/v0.8.1) - 2022-09-30

### Fixed

- Fixed an issue when using a custom Docker image where Gantry would fail if the working directory of the image was non-empty.

## [v0.8.0](https://github.com/allenai/beaker-gantry/releases/tag/v0.8.0) - 2022-09-16

### Fixed

- Fixed issue where Python version was too specific for Conda. Now we only specify the major and minor version.

## [v0.7.0](https://github.com/allenai/beaker-gantry/releases/tag/v0.7.0) - 2022-06-16

### Changed

- `gantry run` will now live stream the logs for the experiment when `--timeout` is not 0.

## [v0.6.0](https://github.com/allenai/beaker-gantry/releases/tag/v0.6.0) - 2022-06-10

### Added

- Added `--dataset` option for attaching input datasets to an experiment.
  For example: `gantry run --dataset 'petew/squad-train:/input-data' -- ls /input-data`

## [v0.5.2](https://github.com/allenai/beaker-gantry/releases/tag/v0.5.2) - 2022-06-10

### Changed

- `beaker-py` v1.4.1 or newer now required.

## [v0.5.1](https://github.com/allenai/beaker-gantry/releases/tag/v0.5.1) - 2022-06-09

### Changed

- `beaker-py` v1.4 or newer now required to make use of `Beaker.session()` for performance.

## [v0.5.0](https://github.com/allenai/beaker-gantry/releases/tag/v0.5.0) - 2022-06-03

### Added

- Added a command `gantry config set-gh-token` for setting or updating your GitHub personal access token for a Beaker workspace.

## [v0.4.0](https://github.com/allenai/beaker-gantry/releases/tag/v0.4.0) - 2022-05-23

### Added

- Added the `--venv` option. Use this to specify an existing conda environment on your image to use.

## [v0.3.1](https://github.com/allenai/beaker-gantry/releases/tag/v0.3.1) - 2022-05-20

### Changed

- You can now overwrite an existing file with the `--save-spec` option. Pass `--yes` to avoid the confirmation prompt.

## [v0.3.0](https://github.com/allenai/beaker-gantry/releases/tag/v0.3.0) - 2022-05-18

### Added

- NFS drive automatically attached when using cirrascale clusters.
- Added `--save-spec PATH` option to `beaker run` for saving the generated experiment spec to a YAML file.
- Added automatic upgrade checks. You'll get a warning message if your installation of gantry is out-of-date.
- Entrypoint now shows useful Python environment info from the entrypoint script.

## [v0.2.1](https://github.com/allenai/beaker-gantry/releases/tag/v0.2.1) - 2022-05-16

### Changed

- Runtime, results, and metrics now printed at the end.

### Fixed

- Fixed the potential for a race condition when `gantry run` is called on the same workspace from multiple processes when creating a new entrypoint dataset, resulting in a `DatasetConflict` error.

## [v0.2.0](https://github.com/allenai/beaker-gantry/releases/tag/v0.2.0) - 2022-05-16

### Added

- Added additional `--dry-run` output.
- Added `--yes` flag for skipping confirmation prompts.

### Changed

- Public workspaces are now allowed.
- Workspaces with multiple contributors are now allowed, but you'll be asked to confirm
  that it's okay.

## [v0.1.0](https://github.com/allenai/beaker-gantry/releases/tag/v0.1.0) - 2022-05-13

### Added

- Added `gantry` CLI.
