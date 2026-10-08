"""Select an Ascend runtime device using npu-smi's mapping and process tables.

References:
https://www.hiascend.com/doc_center/source/en/CANNCommunityEdition/910/devaids/Profiling/atlasprofiling_16_0016.html
https://docs.vllm.ai/projects/ascend/en/v0.23.0/developer_guide/Design_Documents/cpu_binding.html
"""

import os
import re
import subprocess
import sys


def device_mapping(text):
    devices = {}
    for line in text.splitlines():
        row = re.match(r"^\s*(\d+)\s+(\d+)\s+(?:(\d+|-)\s+)?(.+?)\s*$", line)
        if not row:
            continue
        npu, chip, logical, name = row.groups()
        if "ascend" not in name.lower():
            continue
        if logical is None or logical == "-":
            # Ascend 950 omits Chip Logic ID; its NPU ID is the logical ID.
            if "950" not in name:
                raise ValueError(f"Missing logical ID for NPU {npu}, chip {chip}")
            logical = npu
        key = (int(npu), int(chip))
        devices[key] = int(logical)
    if not devices or len(set(devices.values())) != len(devices):
        raise ValueError("No unambiguous Ascend device mapping in npu-smi info -m")
    return devices


def process_counts(text, devices):
    processes = {key: set() for key in devices}
    observed = set()
    in_process_table = False
    for line in text.splitlines():
        if "Process id" in line and "NPU" in line:
            in_process_table = True
            continue
        if not in_process_table:
            continue
        idle = re.search(r"No running processes found in NPU\s+(\d+)\b", line)
        if idle:
            observed.update(key for key in devices if key[0] == int(idle[1]))
            continue
        fields = [field.strip() for field in line.strip().strip("|").split("|")]
        if len(fields) < 3 or not fields[1].isdigit():
            continue
        identifiers = fields[0].split()
        if len(identifiers) not in (1, 2) or not all(part.isdigit() for part in identifiers):
            raise ValueError(f"Unknown NPU process row: {line}")
        key = (int(identifiers[0]), int(identifiers[1]) if len(identifiers) == 2 else 0)
        if key in processes:
            observed.add(key)
            processes[key].add(int(fields[1]))
    if not in_process_table or observed != set(devices):
        raise ValueError("Incomplete NPU process table; refusing to treat missing data as idle")
    return {key: len(pids) for key, pids in processes.items()}


def select_device(mapping_text, info_text, visible=None):
    devices = device_mapping(mapping_text)
    # Runtime visibility renumbers the listed logical IDs to indices 0..N-1.
    indices = {logical: logical for logical in devices.values()}
    if visible is not None:
        if not re.fullmatch(r"\d+(,\d+)*", visible):
            raise ValueError("Unsupported ASCEND_RT_VISIBLE_DEVICES value")
        visible_ids = [int(value) for value in visible.split(",")]
        if len(set(visible_ids)) != len(visible_ids):
            raise ValueError("Duplicate ASCEND_RT_VISIBLE_DEVICES IDs")
        indices = {logical: index for index, logical in enumerate(visible_ids)}
    candidates = [key for key, logical in devices.items() if logical in indices]
    if not candidates:
        raise ValueError("No visible NPU candidates")
    counts = process_counts(info_text, {key: devices[key] for key in candidates})
    for key in sorted(candidates, key=lambda key: devices[key]):
        print(f"NPU {key[0]}, chip {key[1]}, logical {devices[key]}: {counts[key]} processes", file=sys.stderr)
    selected = min(candidates, key=lambda key: (counts[key], devices[key]))
    device_id = indices[devices[selected]]
    print(f"Selected NPU {selected[0]}, chip {selected[1]}: DEVICE_ID={device_id}", file=sys.stderr)
    return device_id


def query(*args):
    return subprocess.run(["npu-smi", "info", *args], check=True, capture_output=True, text=True, timeout=30).stdout


if __name__ == "__main__":
    try:
        print(select_device(query("-m"), query(), os.environ.get("ASCEND_RT_VISIBLE_DEVICES")))
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(f"NPU selection failed: {error}", file=sys.stderr)
        sys.exit(1)
