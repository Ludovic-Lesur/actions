#!/usr/bin/env python3
#
# build_artifact_name.py
#
#  Created on: 03 jan. 2026
#      Author: Ludo & Copilot
#

import argparse

def sanitize(s: str) -> str:
    """
    Replace dots with hyphens and lowercase the string.
    """
    return s.replace('.', '-').lower() if s else ''

def build_artifact_name(project: str, configuration: str, tag: str) -> str:
    """
    Build artifact name.
    """
    project_s = sanitize(project)
    tag_s = sanitize(tag)
    parts = configuration.split('_') if configuration else []
    parts_s = [sanitize(p) for p in parts]

    for i, p in enumerate(parts_s):
        if p.startswith('hw'):
            new_parts = parts_s[:i+1] + [tag_s] + parts_s[i+1:]
            return f"{project_s}_{'_'.join(new_parts)}"
    # No hardware field found: prefix with the tag directly.
    if parts_s:
        return f"{project_s}_{tag_s}_{'_'.join(parts_s)}"
    else:
        return f"{project_s}_{tag_s}"

def main() -> None:
    parser = argparse.ArgumentParser(description="Build artifact name")
    parser.add_argument('-p', '--project', required=True, help="Project name")
    parser.add_argument('-c', '--config', required=True, help="Configuration name")
    parser.add_argument('-t', '--tag', required=True, help="GitHub tag name")
    args = parser.parse_args()

    print(build_artifact_name(args.project, args.config, args.tag))

if __name__ == "__main__":
    main()
