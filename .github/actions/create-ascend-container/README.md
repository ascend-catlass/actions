# Create Ascend container

This composite action checks `/.dockerenv` before using Docker. Inside a
container, it returns the input source path and an empty `container-name`.
On a host, it creates a container with the image's own runtime environment.

| Input | Default / requirement |
| --- | --- |
| `image-repository` | `swr.cn-south-1.myhuaweicloud.com/ascendhub/cann` (`CANN_REPO`) |
| `image-tag` | `9.1.1-910b-ubuntu22.04-py3.12` (`CANN_TAG`) |
| `name` | Required, unique Docker name (`NAME`) |
| `worktree` | Required, existing absolute host source directory |
| `container-worktree` | `/workspace/catlass` |

Docker uses an existing local image when available. The PR workflow supplies
`ascend-catlass-dsl` and `9.1.0-950-ubuntu22.04-py3.12` for the current local CI
image. The container keeps the image entrypoint, runs with `--privileged` and
`--init`, and mounts only the source directory and these required driver paths:

- `/usr/local/dcmi`
- `/usr/local/bin/npu-smi`
- `/usr/local/Ascend/driver/lib64`
- `/usr/local/Ascend/driver/version.info`
- `/etc/ascend_install.info`

Driver mounts are read-only. Image contents under `/root`, CANN, Conda, and
AscendNPU-IR remain available. Tests use the image environment without host
activation scripts. An existing container with the same name is rejected.

Use the `worktree` and `container-name` outputs as the corresponding inputs to
`run-ci-tests`. The calling workflow owns cleanup: after all consumers, an
`always()` step must remove `container-name` when it is nonempty. The action
publishes this name before Docker starts the container, so cleanup also handles
a failed start. It leaves the existing runner container alone.
