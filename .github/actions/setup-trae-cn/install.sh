#!/usr/bin/env bash
set -euo pipefail
cli_dir="${RUNNER_TEMP}/trae-cn-bin"
mkdir -p "$cli_dir"
base=https://lf-cdn.trae.com.cn/obj/trae-com-cn/trae-cli/v2/releases/0.209.1
curl -fsSL --retry 3 --connect-timeout 30 --max-time 300 "$base/traex-linux-x86_64.gz" -o "$cli_dir/traex.gz"
curl -fsSL --retry 3 --connect-timeout 30 --max-time 180 "$base/traex-code-mode-host-linux-x86_64.gz" -o "$cli_dir/host.gz"
echo "643cf93b876e89ea5c72c87d3448b26690c6b71e45b3a7756b914d2ca53c1405  $cli_dir/traex.gz" | sha256sum --check
echo "493c137bf1ec909aa565e4e8e534d694edf3d9b388449019fbe7e3ab189d6765  $cli_dir/host.gz" | sha256sum --check
gzip -dc "$cli_dir/traex.gz" > "$cli_dir/traex"
gzip -dc "$cli_dir/host.gz" > "$cli_dir/traex-code-mode-host"
chmod 755 "$cli_dir/traex" "$cli_dir/traex-code-mode-host"
ln -s traex "$cli_dir/traecli"
# Same delivery metadata as the official online ToB installer, with
# updates disabled so the verified binary cannot change during the job.
printf '%s\n' '{"channel":"public","release_channel":"stable","auto_update":false}' > "$cli_dir/trae-installation.json"
"$cli_dir/traecli" --version
if ! command -v bwrap >/dev/null; then
  sudo apt-get update -qq
  sudo apt-get install -y bubblewrap
fi
echo "$cli_dir" >> "$GITHUB_PATH"
