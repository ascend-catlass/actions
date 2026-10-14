# run-ci-tests

[中文手册](../../../docs/zh/actions/run-ci-tests.md) · [English guide](../../../docs/en/actions/run-ci-tests.md)

在已准备好的测试环境运行一个明确的测试阶段。DSL 测试按开发构建、IR、Lit 和设备测试拆分；非 DSL 测试按修改路径和头文件依赖选择测试组。

Runs one explicit stage in a prepared test environment. DSL testing separates development build, IR, Lit and device tests. Non-DSL testing selects groups from changed paths and reverse header dependencies.
