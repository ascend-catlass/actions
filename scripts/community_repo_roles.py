"""Read repository role declarations from a CANN community checkout."""
import argparse
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

import yaml


def normalize_repository(value):
    value = value.strip()
    if "://" in value:
        url = urlsplit(value)
        if (url.scheme != "https" or url.hostname not in {"gitcode.com", "atomgit.com"}
                or url.username or url.password or url.port or url.query or url.fragment):
            raise ValueError("repository URL must be an HTTPS GitCode or AtomGit repository URL")
        value = url.path.strip("/")
    if value.endswith(".git"):
        value = value[:-4]
    if (not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", value)
            or any(part in {".", ".."} for part in value.split("/"))):
        raise ValueError("repository must be owner/repo or an HTTPS repository URL")
    return value.casefold()


def read_config(path):
    data = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"expected a YAML mapping: {path}")
    return data


def records(value, label):
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError(f"{label} must be a list of mappings")
    return value


def merge_people(*groups):
    people = {}
    for group in groups:
        for person in records(group, "people"):
            identity = person.get("gitcode_id")
            if not isinstance(identity, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", identity):
                raise ValueError("every person must have a valid gitcode_id")
            target = people.setdefault(identity.casefold(), {"gitcode_id": identity})
            for field in ("name", "email"):
                if person.get(field):
                    if not isinstance(person[field], str):
                        raise ValueError(f"{field} must be a string for {identity}")
                    target.setdefault(field, person[field])
    return list(people.values())


def lookup_roles(community_path, repository):
    root = Path(community_path).resolve()
    repository = normalize_repository(repository)
    org_path = root / "CANN/org-info.yaml"
    org = read_config(org_path)
    sigs_root = root / "CANN/sigs"
    configs = sorted(sigs_root.glob("*/sig-info.yaml"))
    if not configs:
        raise ValueError(f"no SIG configurations found in {sigs_root}")
    org_sigs = records(org.get("sigs"), "sigs")
    maintainers, committers, matches, sources, scoped = [], [], [], [], []
    for path in configs:
        sig = read_config(path)
        name = sig.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError(f"missing SIG name: {path}")
        for group in records(sig.get("repositories"), "repositories"):
            repos = group.get("repo") or []
            if not isinstance(repos, list) or any(not isinstance(repo, str) for repo in repos):
                raise ValueError(f"repo must be a list of repository names: {path}")
            if repository not in [normalize_repository(repo) for repo in repos]:
                continue
            owners = [item for item in org_sigs if item.get("sig_name") == name]
            if len(owners) != 1:
                raise ValueError(f"SIG {name!r} must have exactly one entry in org-info.yaml")
            maintainers = merge_people(maintainers, owners[0].get("maintainers"))
            committers = merge_people(committers, sig.get("committers"), group.get("committers"))
            if name not in matches:
                matches.append(name)
                sources.append(path.relative_to(root).as_posix())
            scoped.append({
                "sig": name,
                "entry_configs": records(group.get("entry_configs"), "entry_configs"),
                "branch_configs": records(group.get("branch_configs"), "branch_configs"),
            })
    if not matches:
        raise ValueError(f"repository {repository!r} is not declared in community SIG configurations")
    shared_path = sigs_root / "shared_config.yaml"
    shared = read_config(shared_path) if shared_path.exists() else {}
    return {
        "repository": repository,
        "sigs": matches,
        "maintainers": maintainers,
        "committers": committers,
        "maintainer_ids": [p["gitcode_id"] for p in maintainers],
        "committer_ids": [p["gitcode_id"] for p in committers],
        "scoped_configs": scoped,
        "shared_config": shared,
        "source_files": ["CANN/org-info.yaml", *sources]
        + (["CANN/sigs/shared_config.yaml"] if shared_path.exists() else []),
    }


def compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--community-path", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--output-file", required=True)
    args = parser.parse_args(argv)
    try:
        result = lookup_roles(args.community_path, args.repository)
        output_path = Path(args.output_file).resolve()
        if any(character in str(output_path) for character in "\r\n"):
            raise ValueError("output path must not contain newlines")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if os.environ.get("GITHUB_OUTPUT"):
            outputs = {
                "maintainers": result["maintainer_ids"],
                "committers": result["committer_ids"],
                "sigs": result["sigs"],
                "result": result,
            }
            with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as handle:
                for key, value in outputs.items():
                    handle.write(f"{key}={compact(value)}\n")
                handle.write(f"result-file={output_path}\n")
        print(compact(result))
        return 0
    except (ValueError, OSError, yaml.YAMLError) as error:
        print(f"community role lookup failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
