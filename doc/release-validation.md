# Operator release validation

The `1.0.0rc1` CI matrix builds and installs the package on Linux (Python 3.12 and 3.13), macOS (3.12), and Windows (3.12). Synthetic fixtures cover provider parsing, lookup, resolution, and the notebook-style consumer path. CI does **not** validate current licensed provider releases or publish an artifact.

## Run with locally installed datasets

The operator first accepts the applicable provider terms and installs or imports the current files using the [dataset lifecycle](dataset-lifecycle.md). The validation command reads selected active snapshots; it does not acquire, update, delete, or activate anything. Run it from a checkout of the exact release candidate:

```sh
uv sync --frozen --dev
uv run --frozen python scripts/validate_installed_datasets.py --provider ipinfo --provider ip2proxy --provider maxmind
```

Pass `--store /path/to/ipfacet-data` if the datasets are outside IPFacet's default data directory. Select only providers whose licensed files are installed. The command verifies each active hash and adapter schema, then performs offline IPv4 and IPv6 lookups using two fixed public sample addresses. It exits 2 for a missing/corrupt snapshot or lookup error. Its JSON output contains package version, provider/dataset/release, snapshot SHA-256, adapter version, freshness, license reference, and **counts** of field states per address family. It does not emit the sample addresses, matched values, or credentials. `not_found` is a valid field state, especially for free-tier coverage; these samples cannot establish coverage or accuracy for an entire dataset.

Review the output together with `ipfacet datasets status PROVIDER DATASET --verify` for each selected snapshot. Record the candidate commit, command results, source releases and hashes, terms/attribution review, and any observed stale data in the operator's release record. Do not attach provider files, credentials, or ordinary event rows to a PR or release.

## Remaining human decision

Before a final `1.0.0` tag/package publication, the operator should review the real-release results and packaging destination, validate the chosen provider files under their terms, and decide whether any actual-data performance comparison is required. MaxMind superseded GeoLite releases must be ceased and destroyed by the operator within the applicable provider deadline; IPFacet reports the obligation and does not delete those releases. A consumer dependency pin and Anomaly-Detections feature integration are separate changes after the artifact location is chosen.

The repository has no real provider snapshot in CI. Until the operator runs and reviews this command on current licensed files, the real-dataset gate remains **unverified**. A passing synthetic test or sample lookup does not convert it to a completed release approval.
