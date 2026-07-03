r"""
This module contains utilities that fix identifiers, filenames, and SVG
labels in the electrochemistry-data repository database.

The utilities enforce the identifier naming convention (see
:mod:`echemdb_ecdata.validate`) by lowercasing SVG labels and filenames and
by renaming directories and files whose names do not match the
``citationKey`` in the YAML metadata.

EXAMPLES:

Preview lowercase fixes for svgdigitizer SVG labels and filenames::

    >>> lowercase_svgdigitizer_files(dry_run=True)  # doctest: +SKIP

Preview identifier fixes (directory name != YAML citationKey)::

    >>> fix_identifiers(dry_run=True)  # doctest: +SKIP

"""

# ********************************************************************
#  This file is part of electrochemistry-data.
#
#        Copyright (C) 2025-2026 Albert Engstfeld
#
#  electrochemistry-data is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  electrochemistry-data is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with electrochemistry-data. If not, see <https://www.gnu.org/licenses/>.
# ********************************************************************

import glob
import os
import re
import subprocess
from pathlib import Path

from echemdb_ecdata.validate import _read_yaml_metadata


def _lowercase_svg_labels(svg_path):
    r"""
    Lowercase the figure and curve text labels inside an SVG file.

    Modifies the SVG in place. Only changes ``<text>`` elements
    matching ``figure: ...`` or ``curve: ...`` patterns.

    EXAMPLES::

        >>> import tempfile, os
        >>> svg = '<svg><text>figure: 1Cs</text><text>curve: Au_solid</text></svg>'
        >>> kw = dict(mode='w', suffix='.svg',
        ...     delete=False, encoding='utf-8')
        >>> with tempfile.NamedTemporaryFile(**kw) as f:
        ...     _ = f.write(svg)
        ...     name = f.name
        >>> _lowercase_svg_labels(name)
        True
        >>> with open(name, encoding='utf-8') as f:
        ...     print(f.read())
        <svg><text>figure: 1cs</text><text>curve: au_solid</text></svg>
        >>> os.unlink(name)

    Returns ``False`` if nothing changed::

        >>> import tempfile, os
        >>> svg = '<svg><text>figure: 1a</text><text>curve: solid</text></svg>'
        >>> with tempfile.NamedTemporaryFile(**kw) as f:
        ...     _ = f.write(svg)
        ...     name = f.name
        >>> _lowercase_svg_labels(name)
        False
        >>> os.unlink(name)

    """
    with open(svg_path, encoding="utf-8") as f:
        content = f.read()

    def _lower_label(match):
        return match.group(1) + match.group(2).lower()

    new_content = re.sub(r"((?:figure|curve):\s*)([^<]+)", _lower_label, content)

    if new_content != content:
        with open(svg_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        return True
    return False


def _git_mv_lowercase(file_path):
    r"""
    Rename a file to its lowercase version using ``git mv``.

    On Windows, case-only renames require a two-step process
    (file → temp → lowercase) because the filesystem is
    case-insensitive.

    Returns ``True`` if the file was renamed, ``False`` if already
    lowercase.
    """
    path = Path(file_path)
    lower_name = path.name.lower()

    if path.name == lower_name:
        return False

    # Two-step rename for Windows case-insensitive filesystem
    tmp_path = path.with_name(path.name + "_tmp_rename")
    target_path = path.with_name(lower_name)

    subprocess.run(
        ["git", "mv", str(path), str(tmp_path)],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "mv", str(tmp_path), str(target_path)],
        check=True,
        capture_output=True,
    )
    return True


def lowercase_svgdigitizer_files(  # pylint: disable=too-many-locals,too-many-branches
    data_dir="literature/svgdigitizer",
    dry_run=False,
):
    r"""
    Fix uppercase in svgdigitizer SVG labels and filenames.

    This function:

    1. Lowercases ``figure:`` and ``curve:`` text labels inside SVG files.
    2. Renames files (both ``.svg`` and ``.yaml``) to lowercase using
       ``git mv`` (two-step for Windows compatibility).

    Use ``dry_run=True`` to preview changes without modifying anything.

    EXAMPLES::

        >>> lowercase_svgdigitizer_files(dry_run=True)  # doctest: +SKIP

    """
    yaml_files = sorted(glob.glob(os.path.join(data_dir, "**/*.yaml"), recursive=True))
    changes = []

    for yaml_file in yaml_files:
        yaml_path = Path(yaml_file)
        svg_path = yaml_path.with_suffix(".svg")

        if not svg_path.exists():
            continue

        stem = yaml_path.stem
        lower_stem = stem.lower()
        needs_rename = stem != lower_stem

        # Check SVG labels
        with open(svg_path, encoding="utf-8") as f:
            content = f.read()
        svg_has_upper = bool(re.search(r"(?:figure|curve):\s*[^<]*[A-Z]", content))

        if not needs_rename and not svg_has_upper:
            continue

        if svg_has_upper:
            changes.append(f"SVG LABELS: {svg_path}")
        if needs_rename:
            changes.append(f"RENAME: {stem}.yaml -> {lower_stem}.yaml")
            changes.append(f"RENAME: {stem}.svg -> {lower_stem}.svg")

        if dry_run:
            continue

        # Fix SVG labels first (before rename)
        if svg_has_upper:
            _lowercase_svg_labels(svg_path)
            print(f"Fixed SVG labels: {svg_path}")

        # Rename files
        if needs_rename:
            for ext in [".yaml", ".svg"]:
                filepath = yaml_path.with_suffix(ext)
                if filepath.exists():
                    renamed = _git_mv_lowercase(filepath)
                    if renamed:
                        print(f"Renamed: {filepath.name} -> {filepath.name.lower()}")

    if dry_run:
        if changes:
            print(f"Dry run: {len(changes)} changes needed:")
            for c in changes:
                print(f"  {c}")
        else:
            print("Dry run: no changes needed.")

    return changes


def _rename_directory(old_dir, new_dir, old_name, new_name, dry_run=False):
    r"""
    Rename a directory and all files whose names contain ``old_name``.

    Tracked files are renamed with ``git mv`` (two-step for Windows
    case-insensitive filesystem).  Untracked files are renamed with
    plain ``os.rename``.

    Returns a list of human-readable change descriptions.
    """
    changes = []
    old_path = Path(old_dir)
    new_path = Path(new_dir)

    if not old_path.exists():
        return changes

    # Rename files inside the directory first
    for filepath in sorted(old_path.iterdir()):
        old_basename = filepath.name
        new_basename = old_basename.replace(old_name, new_name)
        if old_basename == new_basename:
            continue

        changes.append(f"  FILE: {old_basename} -> {new_basename}")
        if dry_run:
            continue

        # Check if file is tracked by git
        result = subprocess.run(
            ["git", "ls-files", "--error-unmatch", str(filepath)],
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            # Two-step rename for Windows case-insensitive filesystem
            tmp = filepath.with_name(old_basename + ".tmp_rename")
            subprocess.run(
                ["git", "mv", str(filepath), str(tmp)],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "mv", str(tmp), str(old_path / new_basename)],
                check=True,
                capture_output=True,
            )
        else:
            os.rename(filepath, old_path / new_basename)

    # Rename the directory itself
    changes.append(f"  DIR:  {old_path.name}/ -> {new_path.name}/")
    if not dry_run:
        # Check if directory has tracked files
        result = subprocess.run(
            ["git", "ls-files", str(old_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.stdout.strip():
            tmp_dir = old_path.with_name(old_path.name + ".tmp_rename")
            subprocess.run(
                ["git", "mv", str(old_path), str(tmp_dir)],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "mv", str(tmp_dir), str(new_path)],
                check=True,
                capture_output=True,
            )
        else:
            os.rename(old_path, new_path)

    return changes


def fix_identifiers(  # pylint: disable=too-many-locals,too-many-branches
    data_dir="literature/svgdigitizer",
    generated_dir="data/generated/svgdigitizer",
    dry_run=False,
):
    r"""
    Automatically detect and fix directory/file name mismatches.

    Scans all YAML files in ``data_dir``, reads each ``citationKey``,
    and compares it to the parent directory name.  When they differ,
    renames the directory and all contained files (in both the input
    and generated trees) to match the ``citationKey``.

    Uses ``git mv`` with a two-step rename for Windows compatibility.
    Untracked files (e.g. PDFs) are renamed with plain ``os.rename``.

    Use ``dry_run=True`` to preview changes without modifying anything.

    EXAMPLES::

        >>> fix_identifiers(dry_run=True)  # doctest: +SKIP

    """
    yaml_files = sorted(glob.glob(os.path.join(data_dir, "**/*.yaml"), recursive=True))

    if not yaml_files:
        raise FileNotFoundError(f"No YAML files found in {data_dir}")

    # Collect unique directory-level mismatches (one per directory)
    mismatches = {}  # old_dir_name -> new_dir_name (citationKey)
    for yaml_file in yaml_files:
        yaml_path = Path(yaml_file)
        citation_key = (
            _read_yaml_metadata(yaml_path).get("source", {}).get("citationKey", "")
        )
        if not citation_key:
            continue
        dir_name = yaml_path.parent.name
        if dir_name != citation_key and dir_name not in mismatches:
            mismatches[dir_name] = citation_key

    if not mismatches:
        print("No identifier mismatches found. Everything is up to date.")
        return []

    all_changes = []
    for old_name, new_name in sorted(mismatches.items()):
        print(f"{'[DRY RUN] ' if dry_run else ''}RENAME: {old_name} -> {new_name}")

        # Rename in literature/svgdigitizer/
        old_dir = os.path.join(data_dir, old_name)
        new_dir = os.path.join(data_dir, new_name)
        changes = _rename_directory(old_dir, new_dir, old_name, new_name, dry_run)
        for c in changes:
            print(c)
        all_changes.extend(changes)

        # Rename in data/generated/svgdigitizer/
        old_gen = os.path.join(generated_dir, old_name)
        new_gen = os.path.join(generated_dir, new_name)
        if Path(old_gen).exists():
            changes = _rename_directory(
                old_gen,
                new_gen,
                old_name,
                new_name,
                dry_run,
            )
            for c in changes:
                print(c)
            all_changes.extend(changes)

    action = "would rename" if dry_run else "renamed"
    n = len(mismatches)
    print(f"\n{n} director{'y' if n == 1 else 'ies'} {action}.")
    return all_changes
