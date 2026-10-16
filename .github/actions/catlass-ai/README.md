# CATLASS AI execution policy

[中文手册](../../../docs/zh/actions/catlass-ai.md) · [English guide](../../../docs/en/actions/catlass-ai.md)

All four AI entry points share the model, host, read-only sandbox and public CLI
setup/execution components here. Callers supply task files and a budget. Publishers
consume the returned result directory instead of configuring the model again.
