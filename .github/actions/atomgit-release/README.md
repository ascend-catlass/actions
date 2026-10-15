# atomgit-release

[中文手册](../../../docs/zh/actions/atomgit-release.md) · [English guide](../../../docs/en/actions/atomgit-release.md)

把已经构建和验证的 wheel 发布包上传到 AtomGit Release。已有同名附件时先比对内容；内容相同则复用，内容冲突则失败。

Uploads an already built and validated wheel bundle to an AtomGit Release. Existing assets are compared by content: matching assets are reused and conflicting assets fail the run.
