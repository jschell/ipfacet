# V1 compatibility and release policy

IPFacet uses semantic versioning for its public Python and CLI contracts. Python distribution version `1.0.0rc1` corresponds to release candidate tag `v1.0.0rc1`; it is a prerelease for validation, not a final V1 release. A V1 final release will use `1.0.0` after the candidate is reviewed and accepted. The project does not publish a package or tag as part of this plan.

## Public contract

Public imports in `ipfacet.__all__`, `ipfacet.providers.__all__`, the canonical model's `to_dict()` representation, `enrich_frame` column names and states, CLI commands and JSON keys, manifest schema, and field-resolution semantics are compatibility surfaces. Provider-specific modules and dataset formats also have documented adapter contracts. Private names beginning with `_` are implementation details.

- Patch: fixes without intentional change to documented public behavior or stored interpretation.
- Minor: additive, compatible fields/providers/CLI options; consumers must tolerate additional JSON keys and new optional columns only when explicitly requested.
- Major: removed or renamed public names, changed column or canonical field meaning, changed serialization shape, or changed precedence/retention defaults.
- Release candidates can be revised before 1.0.0; record differences in the changelog and migration notes.

An existing canonical field's meaning cannot be silently reinterpreted. For a schema change, document the old and new semantics, add migration guidance, and test both behavior and provenance. Manifests have an explicit `schema_version`; unsupported versions fail clearly. Provider dataset releases are immutable; updates never mix versions or silently fill gaps from an older release. Consumers should pin a package version and persist provider/version/hash provenance where permitted, then review changelog and licensing before upgrading.

`DatasetStore` paths and private CSV offset indexes are not public persistence APIs. Avoid assuming a specific file format from the canonical result. Third-party datasets are not redistributed by this package. MaxMind GeoLite destruction is operator-managed under its terms; a version identifier can remain after the database is removed.

## Reproduce the release candidate

From a clean checkout of the candidate commit or tag, with Python 3.12+ and uv:

```sh
uv sync --frozen --dev
uv lock --check
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pyright
uv run --frozen pytest
uv build
```

The wheel and source distribution are built from the same `pyproject.toml` and locked development environment. CI additionally installs the wheel into a fresh environment and imports the installed package from outside the repository. Dataset acquisition and real-provider integration checks remain separate, opt-in operations that require the operator's credentials and acceptance of provider terms.
