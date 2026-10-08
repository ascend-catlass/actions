# Vendored NPU selector

`detect_npu.sh` is copied without changes from:

- Repository: https://github.com/MinghuasLab/flash-attention-npu
- File: `ci/detect_npu.sh`
- Revision: `5e45d4dc449bcc7da829891bec3a2dcb1ca84be2`
- Source: https://github.com/MinghuasLab/flash-attention-npu/blob/5e45d4dc449bcc7da829891bec3a2dcb1ca84be2/ci/detect_npu.sh
- License: BSD 3-Clause; see `LICENSE.flash-attention-npu` in this directory.

The action calls `--env`, validates its single numeric assignment without
`eval`, and forwards `NPU_SELECTED_DEVICE` as `DEVICE_ID`. It preserves the
upstream selection criteria and uses only local files at runtime.
