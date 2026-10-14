"""File-oriented adapter for the official China TraeCode CLI 2.0, Linux only."""
from __future__ import annotations

import json
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import subprocess
import tempfile
import time
from urllib.parse import urlsplit
import uuid


class StageError(Exception):
    pass


def input_value(name: str, default: str = "") -> str:
    return os.environ.get(f"TRAE_STAGE_{name}", default)


def repository_file(root: Path, value: str) -> Path:
    path = (root / value).resolve(strict=True)
    if not path.is_relative_to(root) or not path.is_file():
        raise StageError("Prompt/schema must be a regular file inside working-directory")
    if path.stat().st_size > 1024 * 1024:
        raise StageError("Prompt/schema exceeds the 1 MiB input limit")
    return path


def prepare(workspace: Path) -> tuple[Path, str, str, dict | None, int]:
    workdir = (workspace / input_value("WORKDIR", ".")).resolve(strict=True)
    if not workdir.is_relative_to(workspace) or not workdir.is_dir():
        raise StageError("working-directory must be inside GITHUB_WORKSPACE")
    if not (workdir / ".git").exists():
        raise StageError("working-directory must be a checked-out Git repository")
    prompt = input_value("PROMPT")
    prompt_file = input_value("PROMPT_FILE")
    if bool(prompt) == bool(prompt_file):
        raise StageError("Provide exactly one of prompt or prompt-file")
    if prompt_file:
        prompt = repository_file(workdir, prompt_file).read_text(encoding="utf-8-sig")
    if not prompt.strip() or len(prompt.encode("utf-8")) > 1024 * 1024:
        raise StageError("Prompt must be nonempty UTF-8 text of at most 1 MiB")
    sandbox = input_value("SANDBOX", "read-only")
    if sandbox not in {"read-only", "workspace-write"}:
        raise StageError("sandbox must be read-only or workspace-write")
    raw_timeout = input_value("TIMEOUT", "900")
    if not re.fullmatch(r"[0-9]+", raw_timeout) or not 1 <= int(raw_timeout) <= 3600:
        raise StageError("timeout-seconds must be an integer between 1 and 3600")
    schema = None
    if input_value("SCHEMA"):
        schema = json.loads(repository_file(workdir, input_value("SCHEMA")).read_text(encoding="utf-8"))
        if not isinstance(schema, dict):
            raise StageError("output-schema-file must contain a JSON object")
    host = input_value("HOST")
    if host:
        parsed = urlsplit(host)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username
                or parsed.password or parsed.query or parsed.fragment):
            raise StageError("host must be an HTTPS URL without credentials, query or fragment")
    return workdir, prompt, sandbox, schema, int(raw_timeout)


def child_environment(home: Path) -> dict[str, str]:
    # Do not give the agent the parent step's GitHub tokens or arbitrary secrets.
    # Network proxy and certificate configuration are necessary on enterprise runners.
    names = {"PATH", "LANG", "LC_ALL", "LC_CTYPE", "TZ", "SSL_CERT_FILE",
             "SSL_CERT_DIR", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE",
             "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY",
             "http_proxy", "https_proxy", "all_proxy", "no_proxy"}
    env = {key: value for key, value in os.environ.items() if key in names}
    env.update(HOME=str(home), XDG_CONFIG_HOME=str(home / ".config"),
               XDG_DATA_HOME=str(home / ".local/share"),
               XDG_STATE_HOME=str(home / ".local/state"),
               XDG_CACHE_HOME=str(home / ".cache"), TMPDIR=str(home / "tmp"))
    (home / "tmp").mkdir()
    if input_value("HOST"):
        env["TRAECLI_HOST"] = input_value("HOST")
    return env


def invoke(argv: list[str], cwd: Path, env: dict[str, str], deadline: float,
           stdout: Path, stderr: Path, stdin: bytes | None = None) -> int:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise subprocess.TimeoutExpired(argv, 0)
    with stdout.open("wb") as out, stderr.open("wb") as err:
        process = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.PIPE,
                                   stdout=out, stderr=err, start_new_session=True)
        try:
            process.communicate(input=stdin, timeout=remaining)
            return process.returncode
        finally:
            # Terminate the entire process group, including tools left running by the CLI.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()


def emit_output(name: str, value: str) -> None:
    if os.environ.get("GITHUB_OUTPUT"):
        delimiter = "trae_" + uuid.uuid4().hex
        while delimiter in value.splitlines():
            delimiter = "trae_" + uuid.uuid4().hex
        with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as stream:
            stream.write(f"{name}<<{delimiter}\n{value}\n{delimiter}\n")


def redact_file(path: Path, secret: str) -> None:
    if secret and path.exists():
        # Stream to avoid holding an entire trajectory in memory. Carry enough bytes
        # across chunk boundaries to redact a token split between reads.
        needle = secret.encode("utf-8")
        temporary = path.with_suffix(path.suffix + ".redacted")
        with path.open("rb") as source, temporary.open("wb") as target:
            pending = b""
            while chunk := source.read(65536):
                pending += chunk
                while (offset := pending.find(needle)) >= 0:
                    target.write(pending[:offset] + b"[REDACTED]")
                    pending = pending[offset + len(needle):]
                keep = min(len(needle) - 1, len(pending))
                target.write(pending[:-keep] if keep else pending)
                pending = pending[-keep:] if keep else b""
            target.write(pending)
        temporary.replace(path)


def main() -> int:
    result_dir = Path(tempfile.mkdtemp(prefix="trae-cn-result-", dir=os.environ.get("RUNNER_TEMP")))
    files = {"response-file": result_dir / "response.md",
             "events-file": result_dir / "events.jsonl",
             "stderr-file": result_dir / "stderr.log",
             "result-file": result_dir / "result.json"}
    emit_output("result-directory", str(result_dir))
    for name, path in files.items():
        emit_output(name, str(path))
    status, code, message, version = "failed", 1, "", ""
    secret = input_value("PAT")

    def cancelled(signum: int, frame: object) -> None:
        raise KeyboardInterrupt

    previous_handler = signal.signal(signal.SIGTERM, cancelled)
    try:
        if platform.system() != "Linux":
            raise StageError("This stage currently supports Linux runners only")
        workspace = Path(os.environ["GITHUB_WORKSPACE"]).resolve(strict=True)
        workdir, prompt, sandbox, schema, timeout = prepare(workspace)
        if not secret.strip():
            raise StageError("trae-pat is required; configure the TRAE_CN_PAT Actions secret")
        cli = shutil.which(input_value("CLI", "traecli"))
        if not cli:
            raise StageError("Official China traecli 2.0 is not installed on this runner")
        cli = str(Path(cli).resolve(strict=True))
        deadline = time.monotonic() + timeout
        # Separate HOME/XDG directories per invocation; never log into the runner's
        # persistent account. Login stdout/stderr and credentials are deleted together.
        with tempfile.TemporaryDirectory(prefix="trae-cn-auth-", dir=os.environ.get("RUNNER_TEMP")) as auth:
            private = Path(auth)
            env = child_environment(private)
            probe = private / "version.txt"
            if invoke([cli, "--version"], private, env, deadline, probe, private / "version.err"):
                raise StageError("Unable to obtain CLI version")
            raw_version = probe.read_text(encoding="utf-8", errors="replace")
            match = re.search(r"\b([0-9]+\.[0-9]+\.[0-9]+)\b", raw_version)
            if not match:
                raise StageError("CLI did not report a numeric version")
            version = match.group(1)
            if input_value("VERSION") and version != input_value("VERSION"):
                raise StageError("Installed CLI does not match expected-version")
            help_file = private / "exec-help.txt"
            help_code = invoke([cli, "exec", "--help"], private, env, deadline,
                               help_file, private / "exec-help.err")
            help_text = help_file.read_text(encoding="utf-8", errors="replace")
            if help_code or any(flag not in help_text for flag in (
                    "--json", "--output-last-message", "--ephemeral", "--ignore-user-config")):
                raise StageError("Installed CLI lacks the required 2.0 exec interface; upgrade the China CLI")
            login_env = dict(env, TRAECLI_PERSONAL_ACCESS_TOKEN=secret)
            if invoke([cli, "login", "--with-trae-pat"], private, login_env, deadline,
                      private / "login.out", private / "login.err"):
                raise StageError("Trae PAT login failed; check enterprise CLI entitlement and host")
            argv = [cli, "exec", "--json", "--color", "never", "--ephemeral",
                    "--ignore-user-config", "--sandbox", sandbox, "--ask-for-approval", "never",
                    "--output-last-message", str(files["response-file"])]
            if input_value("MODEL"):
                argv.extend(["--model", input_value("MODEL")])
            if schema is not None:
                schema_path = private / "schema.json"
                schema_path.write_text(json.dumps(schema), encoding="utf-8")
                argv.extend(["--output-schema", str(schema_path)])
            argv.append("-")
            code = invoke(argv, workdir, env, deadline, files["events-file"],
                          files["stderr-file"], prompt.encode("utf-8"))
            if code:
                message = "Trae execution failed; inspect stderr.log and events.jsonl"
            elif not files["response-file"].is_file() or files["response-file"].stat().st_size == 0:
                code, message = 1, "CLI succeeded without a nonempty final response"
            elif files["response-file"].stat().st_size > 10 * 1024 * 1024:
                code, message = 1, "Final response exceeds the 10 MiB limit"
            else:
                answer = files["response-file"].read_text(encoding="utf-8")
                if not answer.strip():
                    raise StageError("CLI succeeded without a nonempty final response")
                if schema is not None:
                    json.loads(answer)
                status = "success"
    except subprocess.TimeoutExpired:
        status, code, message = "timeout", 124, "Trae stage exceeded timeout-seconds"
    except KeyboardInterrupt:
        status, code, message = "cancelled", 130, "Trae stage was cancelled"
    except (StageError, OSError, ValueError, KeyError) as error:
        code = 1
        # File paths / OS error strings can contain arbitrary input. Keep the public
        # error one-line and redact the PAT; CLI login output is never published.
        message = str(error).replace(secret, "[REDACTED]") if secret else str(error)
        message = " ".join(message.splitlines())
    finally:
        signal.signal(signal.SIGTERM, previous_handler)
        for path in files.values():
            redact_file(path, secret)
        files["result-file"].write_text(json.dumps({
            "status": status, "exit_code": code, "cli_version": version,
            "message": message, "response_file": str(files["response-file"]),
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        emit_output("status", status)
        emit_output("exit-code", str(code))
    print(f"Trae China stage: {status}; result directory: {result_dir}")
    if message:
        print(f"Stage detail: {message}")
    return code if code >= 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
