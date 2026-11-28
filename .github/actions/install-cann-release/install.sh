#!/usr/bin/env bash
# Host only. Arguments: pinned release version, expected CPU.
set -euo pipefail
version=${1:?}; expected_cpu=${2:?}
versions=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/versions.py
python3 "$versions" validate "$version"
[[ $EUID == 0 ]] || { echo 'Root or passwordless sudo is required' >&2; exit 1; }
cpu=$(uname -m)
[[ "$cpu" == "$expected_cpu" && "$cpu" =~ ^(x86_64|aarch64)$ ]]
pci=$(lspci -n -D | grep -o '19e5:d[0-9a-f]\{3\}' | head -n1 | cut -d: -f2)
case "$pci" in
  d802) chip=910b ;;
  d803) chip=A3 ;;
  d806) chip=950 ;;
  *) echo "Unsupported NPU PCI ID: $pci" >&2; exit 1 ;;
esac
root=/opt/cann
target=$root/$version
downloads=$root/packages/$version/$cpu
stamp="$version $cpu $pci"
echo "Host $(hostname): CPU=$cpu NPU=$chip PCI=$pci CANN=$version path=$target"
[[ ! -L "$root" && ! -L "$target" ]]
mkdir -p "$root"
update_latest() {
  if [[ -L "$root/latest" ]]; then
    old_target=$(readlink -f "$root/latest")
    [[ $(dirname "$old_target") == "$(readlink -f "$root")" ]] || {
      echo 'latest points outside the release root' >&2; return 1;
    }
    previous=$(basename "$old_target")
    python3 "$versions" validate "$previous"
    if [[ "$version" != "$previous" ]] && ! python3 "$versions" newer "$version" "$previous"; then
      echo "Keeping newer latest: $previous"
      return
    fi
  elif [[ -e "$root/latest" ]]; then
    echo 'latest exists and is not a symlink' >&2; return 1
  fi
  ln -sfnT "$target" "$root/latest"
}
if [[ -f "$target/installed-version.txt" ]]; then
  [[ $(cat "$target/installed-version.txt") == "$stamp" ]] || { echo 'Conflicting version or hardware' >&2; exit 1; }
  [[ -f "$target/cann/set_env.sh" || -f "$target/ascend-toolkit/set_env.sh" ]]
  update_latest
  echo "Already installed: $target; latest -> $(readlink "$root/latest")"
  exit 0
fi
retry=()
[[ ! -e "$target" ]] || retry=(--force)
[[ $(df -Pk "$root" | awk 'END {print $4}') -gt 31457280 ]] || { echo 'Need 30 GiB free' >&2; exit 1; }
mkdir -p "$downloads"
mirror=https://ascend.devcloud.huaweicloud.com/artifactory/cann-run/software
for package in toolkit "$chip-ops"; do
  file="Ascend-cann-${package}_${version}_linux-${cpu}.run"
  if [[ ! -f "$downloads/$file" ]]; then
    curl -fSL --proto '=https' --proto-redir '=https' --retry 4 --connect-timeout 30 --max-time 3600 \
      "$mirror/$version/$cpu/$file" -o "$downloads/$file.part"
    mv "$downloads/$file.part" "$downloads/$file"
  fi
  bash "$downloads/$file" --check
done
mkdir -p "$target" "$downloads/extract"
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
  [[ $(readlink -f "$ASCEND_HOME_PATH") == "$actual_target/"* && $(readlink -f "$ASCEND_OPP_PATH") == "$actual_target/"* ]]
  [[ -d "$ASCEND_OPP_PATH" && $(readlink -f "$(command -v bisheng)") == "$actual_target/"* ]]
  bisheng --version
)
printf '%s\n' "$stamp" > "$target/installed-version.txt"
update_latest
echo "Installed: $target ($version, $cpu, $chip); latest -> $(readlink "$root/latest")"
