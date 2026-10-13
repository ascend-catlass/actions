#!/usr/bin/env bash
# Host only. Arguments: mirror build, full weekly version, expected CPU.
set -euo pipefail
build=${1:?}; version=${2:?}; expected_cpu=${3:?}
[[ $EUID == 0 ]] || { echo 'Root or passwordless sudo is required' >&2; exit 1; }
[[ "$build" =~ ^[0-9]{17}$ ]]
[[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+~weekly\.([0-9]{8})\.[0-9]+$ ]]
day=${BASH_REMATCH[1]}
[[ "$day" == "${build:0:8}" && $(date -d "$day" +%Y%m%d) == "$day" ]]
cpu=$(uname -m)
[[ "$cpu" == "$expected_cpu" && "$cpu" =~ ^(x86_64|aarch64)$ ]]
pci=$(lspci -n -D | grep -o '19e5:d[0-9a-f]\{3\}' | head -n1 | cut -d: -f2)
case "$pci" in
  d802) chip=910b ;;
  d803) chip=A3 ;;
  d806) chip=950 ;;
  *) echo "Unsupported NPU PCI ID: $pci" >&2; exit 1 ;;
esac
root=/opt/cann_weekly
target=$root/$day
downloads=$root/packages/$build/$cpu
stamp="$build $version $cpu $pci"
echo "Host $(hostname): CPU=$cpu NPU=$chip PCI=$pci CANN=$version path=$target"
[[ ! -L "$root" && ! -L "$target" ]]
mkdir -p "$root"
if [[ -f "$target/installed-version.txt" ]]; then
  [[ $(cat "$target/installed-version.txt") == "$stamp" ]] || { echo 'Conflicting build in this date directory' >&2; exit 1; }
  [[ -f "$target/cann/set_env.sh" || -f "$target/ascend-toolkit/set_env.sh" ]]
  ln -sfnT "$target" "$root/latest"
  echo "Already installed: $target ($version)"
  exit 0
fi
retry=()
[[ ! -e "$target" ]] || retry=(--force)
[[ $(df -Pk "$root" | awk 'END {print $4}') -gt 31457280 ]] || { echo 'Need 30 GiB free' >&2; exit 1; }
mkdir -p "$downloads"
mirror=https://ascend.devcloud.huaweicloud.com/artifactory/cann-run-mirror/software/master
for package in toolkit "$chip-ops"; do
  file="Ascend-cann-${package}_${version}_linux-${cpu}.run"
  if [[ ! -f "$downloads/$file" ]]; then
    curl -fSL --proto '=https' --proto-redir '=https' --retry 4 --connect-timeout 30 --max-time 3600 \
      "$mirror/$build/$file" -o "$downloads/$file.part"
    mv "$downloads/$file.part" "$downloads/$file"
  fi
  bash "$downloads/$file" --check
done
mkdir -p "$target" "$downloads/extract"
# Install directly at the final path; installed packages may contain absolute paths.
for package in toolkit "$chip-ops"; do
  file="Ascend-cann-${package}_${version}_linux-${cpu}.run"
  TMPDIR="$downloads/extract" bash "$downloads/$file" --install --quiet --install-for-all \
    --install-path="$target" "${retry[@]}"
done
(
  unset ASCEND_HOME_PATH ASCEND_OPP_PATH LD_LIBRARY_PATH PYTHONPATH
  env_file=$target/cann/set_env.sh
  [[ -f "$env_file" ]] || env_file=$target/ascend-toolkit/set_env.sh
  set +u
  source "$env_file"
  set -u
  actual_target=$(readlink -f "$target")
  echo "CANN home: $ASCEND_HOME_PATH; OPP: $ASCEND_OPP_PATH"
  [[ $(readlink -f "$ASCEND_HOME_PATH") == "$actual_target/"* && $(readlink -f "$ASCEND_OPP_PATH") == "$actual_target/"* ]]
  [[ -d "$ASCEND_OPP_PATH" && $(readlink -f "$(command -v bisheng)") == "$actual_target/"* ]]
  bisheng --version
)
printf '%s\n' "$stamp" > "$target/installed-version.txt"
ln -sfnT "$target" "$root/latest"
echo "Installed: $target ($version, $cpu, $chip); latest -> $(readlink "$root/latest")"
