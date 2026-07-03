r"""
This module migrates literature metadata YAML files across breaking
metadata-schema releases.

It is a thin wrapper around the migration engine shipped with the
`metadata-schema repository <https://github.com/echemdb/metadata-schema>`_
(``mdstools.schema.migrate``). The individual migration steps (e.g. the 0.8.0
move of ``system.electrolyte.temperature`` to
``experimental.operationParameters.temperature``) are declared in
``mdstools.schema.migrations``; this module only applies them to all input
YAML files in ``literature/``.

Files are rewritten with a comment-preserving YAML round-trip (ruamel), so
curator comments survive. Each migrated file is stamped with the target
schema version in ``echemdbSchemaVersion``, which future migrations use to
determine the pending steps.

EXAMPLES:

Preview the pending migrations without modifying any file::

    >>> migrate_metadata(dry_run=True)  # doctest: +SKIP

Apply them::

    >>> migrate_metadata()  # doctest: +SKIP

"""

# ********************************************************************
#  This file is part of electrochemistry-data.
#
#        Copyright (C) 2026 Albert Engstfeld
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

from echemdb_ecdata.validate import SCHEMA_VERSION

#: Input directories whose YAML files are migrated.
DATA_DIRS = ("literature/svgdigitizer", "literature/source_data")


def migrate_metadata(
    data_dirs=DATA_DIRS, target_version=None, dry_run=False, stamp_all=False
):
    r"""
    Migrate all input metadata YAML files to ``target_version``.

    Applies the migration steps registered in ``mdstools.schema.migrations``
    to every YAML file in ``data_dirs`` and stamps the rewritten files with
    ``echemdbSchemaVersion: <target_version>``. Files are rewritten in place
    with a comment-preserving YAML round-trip.

    By default only files whose content actually changes beyond the version
    stamp are rewritten: rewriting also renormalizes the YAML layout
    (indentation, line wrapping), so stamping otherwise-untouched files would
    reformat large parts of the repository for no structural gain.

    Parameters
    ----------
    data_dirs : iterable of str
        Directories to search recursively for ``*.yaml`` files.
    target_version : str or None
        Metadata-schema version to migrate to. Defaults to
        :data:`echemdb_ecdata.validate.SCHEMA_VERSION` when ``None``.
    dry_run : bool
        If ``True``, only report which files would change without modifying
        anything.
    stamp_all : bool
        If ``True``, also rewrite files that only gain the version stamp.

    Returns a list of the files that changed (or would change).

    EXAMPLES::

        >>> migrate_metadata(dry_run=True)  # doctest: +SKIP

    """
    # Imported lazily: mdstools requires Python >= 3.11 and is only installed
    # in the dev environment (see pyproject.toml).
    # pylint: disable=import-outside-toplevel
    from mdstools.schema.migrate import MetadataMigrator, migrate_file
    from mdstools.schema.validator import _load_data

    # pylint: enable=import-outside-toplevel

    if target_version is None:
        target_version = SCHEMA_VERSION

    yaml_files = sorted(
        f
        for data_dir in data_dirs
        for f in glob.glob(os.path.join(data_dir, "**/*.yaml"), recursive=True)
    )

    if not yaml_files:
        raise FileNotFoundError(f"No YAML files found in {', '.join(data_dirs)}")

    changed = []
    for yaml_file in yaml_files:
        data = _load_data(yaml_file)
        migrator = MetadataMigrator(data, target_version=target_version)
        migrated = migrator.migrated()
        if migrated == data:
            continue
        # Structural change: anything beyond (re)stamping the version field.
        if not stamp_all and migrated == {
            **data,
            "echemdbSchemaVersion": migrated["echemdbSchemaVersion"],
        }:
            continue
        changed.append(yaml_file)
        steps = ", ".join(m.description for m in migrator.pending()) or "version stamp"
        print(f"{'[DRY RUN] ' if dry_run else ''}MIGRATE: {yaml_file} ({steps})")
        if not dry_run:
            migrate_file(yaml_file, target_version=target_version, in_place=True)

    print(
        f"\n{len(changed)} file(s) {'would change' if dry_run else 'changed'} "
        f"out of {len(yaml_files)} checked; target version {target_version}."
    )
    return changed
