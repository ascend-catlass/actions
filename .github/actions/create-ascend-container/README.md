# Create Ascend container

[中文手册](../../../docs/zh/actions/create-ascend-container.md) · [English guide](../../../docs/en/actions/create-ascend-container.md)

Host runners build a missing `ascend-catlass-dsl:ubuntu24-py312-weekly-v1` image immediately and reuse an existing image. Per-image locking prevents duplicate concurrent builds.

The container mounts weekly CANN, matching NPUIR and Ascend drivers read-only. Each test shell activates the mounted CANN environment. See the bilingual guides for inputs and cleanup.
