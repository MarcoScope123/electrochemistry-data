**Added:**

* Added ``mdstools`` (the tooling shipped with the
  `metadata-schema repository <https://github.com/echemdb/metadata-schema>`_,
  pinned to the release matching ``echemdb_ecdata.validate.SCHEMA_VERSION``)
  as a dev-environment dependency.
* Added ``migrate-metadata`` and ``migrate-metadata-dry-run`` tasks
  (``echemdb_ecdata.migrate``) that upgrade the input YAML metadata in
  ``literature/`` across breaking metadata-schema releases using the
  migration engine of the metadata-schema repository. Rewritten files are
  stamped with ``echemdbSchemaVersion``.

**Changed:**

* Changed the metadata-schema version to 0.8.0 and migrated all input YAML
  files accordingly: ``system.electrolyte.temperature`` moved to
  ``experimental.operationParameters.temperature``.
* Changed schema validation to use the validation tools of the
  metadata-schema repository (``mdstools``) instead of ``check-jsonschema``:
  the JSON Schema is fetched once per run and all files are validated
  in-process, now also including the instrument-reference check for
  ``experimental.operationParameters`` control blocks.
* Changed the ``--version`` argument of the validation tasks to take a plain
  metadata-schema release tag (e.g. ``0.8.0``) or branch name (e.g. ``main``)
  instead of ``tags/X.Y.Z`` / ``head/branch-name``.

**Removed:**

* Removed the ``check-jsonschema`` dependency.
