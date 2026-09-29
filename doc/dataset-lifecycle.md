# Dataset Lifecycle

IPFacet keeps dataset acquisition separate from offline lookup. The lifecycle layer manages immutable local snapshots; provider lookup adapters consume only an explicitly selected installed snapshot.

## Storage layout

The default per-user data root is platform appropriate:

- Linux: `$XDG_DATA_HOME/ipfacet` or `~/.local/share/ipfacet`
- macOS: `~/Library/Application Support/IPFacet`
- Windows: `%LOCALAPPDATA%\\IPFacet` with a user-profile fallback

Snapshots use:

```text
<root>/datasets/<provider>/<dataset>/
├── active.json
├── staging/
└── versions/
    ├── <release-a>/
    │   ├── manifest.json
    │   └── provider data...
    └── <release-b>/
        ├── manifest.json
        └── provider data...
```

A release directory is immutable. New content is acquired or copied into a temporary staging directory, hashed, schema/smoke validated, moved into `versions/`, and only then activated. `active.json` is replaced atomically with `os.replace()`. A failed update does not replace the previous pointer.

## Manifest

Every installed snapshot records:

- provider and dataset,
- exact release/version,
- source/acquisition method,
- acquired and activated timestamps,
- dataset format,
- local SHA-256 snapshot integrity,
- provider/source checksum metadata when the acquisition helper has verified it,
- adapter/schema version,
- license reference and attribution,
- provider retention constraints,
- staleness threshold when defined.

Provider-published archive/source checksums are distinct from the installed-tree SHA-256. A provider acquisition helper must verify a published checksum before returning it as source-integrity metadata; the generic manager never assumes an archive hash equals the normalized installed snapshot hash.\n\nManifests intentionally contain no credentials. Provider acquisition helpers receive credentials through external mechanisms such as environment variables; the generic manager has no credential persistence API.

## Retention and rollback

Provider restrictions are part of `DatasetDefinition`. They are enforced after activation:

- `retain_previous_versions=False` destroys superseded snapshots and disables rollback.
- `max_retained_versions=N` caps retained immutable snapshots.
- unrestricted providers may retain prior versions.

Generic behavior cannot relax those provider rules. Rollback first verifies the retained snapshot's hash and provider validator, then atomically changes the active pointer.

## Air-gapped import

Manual import does not require a registered acquisition helper:

```bash
ipfacet datasets import provider dataset /media/dataset \
  --release 2026-09
```

The provider/dataset definition must already be registered, even when no download acquirer is registered. This makes manual-only support possible while ensuring license, attribution, staleness, and retention rules come from provider code rather than user-supplied generic CLI flags. The imported directory then goes through the same staging, hashing, validation, manifest, and activation path as downloaded data.

## CLI

```text
ipfacet datasets available
ipfacet datasets list
ipfacet datasets status <provider> <dataset>
ipfacet datasets install <provider> <dataset>
ipfacet datasets import <provider> <dataset> <directory> ...
ipfacet datasets update <provider> <dataset>
ipfacet datasets verify <provider> <dataset> [--release VERSION]
ipfacet datasets rollback <provider> <dataset> [--release VERSION]
```

`install` and `update` require a registered provider acquisition helper. The IPinfo Lite, IP2Proxy LITE, and GeoLite2 ASN adapters now provide explicit acquisition helpers; ordinary lookup remains offline.

## Real-provider research gate

Acquisition helpers are enabled only after the provider-specific implementation documents and tests:

1. authentication mechanism,
2. whether automated download/update is permitted,
3. download/rate limits,
4. required attribution,
5. redistribution restrictions,
6. retention/destruction requirements,
7. whether older snapshots may legally be retained.

If any of those terms are unclear, the provider plan must support manual import first and leave automated acquisition disabled.

This gate applies independently to IPinfo, IP2Proxy, MaxMind, and any future provider.
