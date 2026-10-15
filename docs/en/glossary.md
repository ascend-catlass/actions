# Glossary

[中文](../zh/glossary.md) · [English](../en/glossary.md)

| Term | Plain-language meaning |
| --- | --- |
| Action | A step reusable across workflows, such as “read PR metadata” |
| Workflow | A complete automation process with triggers, jobs and steps |
| Job | A group of workflow steps executed on a runner |
| Runner | The machine executing automation: GitHub-hosted or a self-hosted Ascend machine |
| PR | Pull Request: a proposed code change waiting to be merged |
| Issue | A problem report or discussion about a project need |
| CI | Automated builds and tests; this repository reports PR test results back to AtomGit |
| RDV | The name used for this repository's PR test flow, with `RDV-RUNNING`, `RDV-SUCC` and `RDV-FAIL` labels |
| Committer / Maintainer | Roles declared in community configuration; the role Action reads the corresponding platform accounts |
| SIG | Special Interest Group responsible for a technical area |
| SHA / gitlink | SHA identifies an exact commit; a gitlink records a submodule commit required by the parent repository |
| CANN / NPU | CANN is the Ascend computing software environment; an NPU runs device tests |
| DSL / NPUIR | DSL is CATLASS's domain-specific language component; NPUIR here means its AscendNPU-IR compiler dependency |
| wheel | A Python package file ending in `.whl` |
| Artifact | A file saved by a workflow, such as a package, log or analysis response, downloadable during its retention period |
| Secret / Token / PAT | A Secret stores credentials; a token or personal access token authorizes automation to access a service |
| Dry run | Preparation or analysis without a particular publication operation, according to the switch supported by that workflow |
