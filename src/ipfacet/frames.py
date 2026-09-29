"""Optional Polars, Pandas, and PyArrow batch boundaries."""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING

from ipfacet.api import Database
from ipfacet.models import CanonicalField, IPEnrichment
from ipfacet.scope import parse_ip

if TYPE_CHECKING:
    import pandas as pd
    import polars as pl
    import pyarrow as pa

ALL_FIELDS = tuple(CanonicalField)


def _columns(
    prefix: str,
    fields: Sequence[CanonicalField],
    *,
    include_provenance: bool,
    include_conflicts: bool,
) -> tuple[str, ...]:
    names = [f"{prefix}scope", f"{prefix}traits"]
    for field in fields:
        names.extend((f"{prefix}{field.value}", f"{prefix}{field.value}_state"))
    if include_provenance:
        names.append(f"{prefix}provenance")
    if include_conflicts:
        names.append(f"{prefix}conflicts")
    return tuple(names)


def _row(
    result: IPEnrichment,
    prefix: str,
    fields: Sequence[CanonicalField],
    *,
    include_provenance: bool,
    include_conflicts: bool,
) -> dict[str, str | int | None]:
    row: dict[str, str | int | None] = {
        f"{prefix}scope": result.scope.value,
        f"{prefix}traits": json.dumps(sorted(trait.value for trait in result.traits)),
    }
    provenance: dict[str, object] = {}
    conflicts: dict[str, object] = {}
    for field in fields:
        resolved = getattr(result, field.value)
        row[f"{prefix}{field.value}"] = resolved.value
        row[f"{prefix}{field.value}_state"] = resolved.state.value
        if include_provenance and resolved.provenance is not None:
            provenance[field.value] = resolved.provenance.to_dict()
        if include_conflicts and resolved.conflict:
            conflicts[field.value] = [item.to_dict() for item in resolved.observations]
    if include_provenance:
        row[f"{prefix}provenance"] = json.dumps(provenance, sort_keys=True)
    if include_conflicts:
        row[f"{prefix}conflicts"] = json.dumps(conflicts, sort_keys=True)
    return row


def _mapping(
    db: Database,
    keys: Iterable[object],
    prefix: str,
    fields: Sequence[CanonicalField],
    *,
    include_provenance: bool,
    include_conflicts: bool,
) -> dict[str, dict[str, str | int | None]]:
    unique: dict[str, None] = {}
    for key in keys:
        if key is None:
            continue
        if not isinstance(key, str):
            raise TypeError("IP column must contain strings or nulls")
        unique[key] = None
    parsed = {raw: parse_ip(raw) for raw in unique}
    results = db.lookup_many(parsed.values())
    return {
        raw: _row(
            results[ip],
            prefix,
            fields,
            include_provenance=include_provenance,
            include_conflicts=include_conflicts,
        )
        for raw, ip in parsed.items()
    }


def enrich_frame(
    db: Database,
    frame: pl.DataFrame | pd.DataFrame | pa.Table,
    *,
    ip_column: str,
    fields: Sequence[CanonicalField] = ALL_FIELDS,
    prefix: str = "ipfacet_",
    include_provenance: bool = False,
    include_conflicts: bool = False,
) -> pl.DataFrame | pd.DataFrame | pa.Table:
    """Enrich unique IPs, then join columns back without per-event provider searches.

    Null IPs produce null enrichment columns. Invalid non-null IPs raise ValueError.
    Existing output column names are rejected rather than silently overwritten.
    The input and output share the same DataFrame/Table type and row order.
    """
    try:
        import polars as polars
    except ImportError:
        polars = None  # type: ignore[assignment]
    try:
        import pandas as pandas
    except ImportError:
        pandas = None  # type: ignore[assignment]
    try:
        import pyarrow as arrow
    except ImportError:
        arrow = None  # type: ignore[assignment]

    selected = tuple(fields)
    if len(set(selected)) != len(selected):
        raise ValueError("fields must be distinct CanonicalField values")
    if not prefix:
        raise ValueError("prefix cannot be empty")
    output = _columns(
        prefix, selected, include_provenance=include_provenance, include_conflicts=include_conflicts
    )
    if polars is not None and isinstance(frame, polars.DataFrame):
        if ip_column not in frame.columns:
            raise KeyError(ip_column)
        if set(output) & set(frame.columns):
            raise ValueError("enrichment columns already exist")
        keys = frame[ip_column].unique().to_list()
        mapped = _mapping(
            db,
            keys,
            prefix,
            selected,
            include_provenance=include_provenance,
            include_conflicts=include_conflicts,
        )
        if not mapped:
            return frame.with_columns(
                polars.lit(None)
                .cast(polars.Int64 if column == f"{prefix}asn" else polars.String)
                .alias(column)
                for column in output
            )
        values: dict[str, list[str | int | None]] = {ip_column: list(mapped)}
        for column in output:
            values[column] = [mapped[key][column] for key in mapped]
        schema = {
            name: polars.Int64 if name == f"{prefix}asn" else polars.String for name in output
        }
        schema[ip_column] = polars.String
        lookup = polars.DataFrame(values, schema_overrides=schema)
        return frame.join(
            lookup,
            on=ip_column,
            how="left",
            validate="m:1",
            maintain_order="left",
        )
    if pandas is not None and isinstance(frame, pandas.DataFrame):
        if ip_column not in frame.columns:
            raise KeyError(ip_column)
        if set(output) & set(frame.columns):
            raise ValueError("enrichment columns already exist")
        keys = frame[ip_column].unique().tolist()
        # Pandas missing values can be NaN/pd.NA rather than None.
        keys = [None if pandas.isna(key) else key for key in keys]
        mapped = _mapping(
            db,
            keys,
            prefix,
            selected,
            include_provenance=include_provenance,
            include_conflicts=include_conflicts,
        )
        result = frame.copy()
        for column in output:
            result[column] = frame[ip_column].map({key: row[column] for key, row in mapped.items()})
            if column == f"{prefix}asn":
                result[column] = result[column].astype("Int64")
        return result
    if arrow is not None and isinstance(frame, arrow.Table):
        import pyarrow.compute as pc

        if ip_column not in frame.column_names:
            raise KeyError(ip_column)
        if set(output) & set(frame.column_names):
            raise ValueError("enrichment columns already exist")
        if not (
            arrow.types.is_string(frame[ip_column].type)
            or arrow.types.is_large_string(frame[ip_column].type)
            or arrow.types.is_null(frame[ip_column].type)
        ):
            raise TypeError("IP column must be strings or nulls")
        keys = pc.unique(frame[ip_column]).to_pylist()
        mapped = _mapping(
            db,
            keys,
            prefix,
            selected,
            include_provenance=include_provenance,
            include_conflicts=include_conflicts,
        )
        key_array = arrow.array(
            list(mapped),
            type=frame[ip_column].type
            if not arrow.types.is_null(frame[ip_column].type)
            else arrow.string(),
        )
        positions = pc.index_in(frame[ip_column], value_set=key_array)  # pyright: ignore[reportUnknownMemberType]
        result = frame
        for column in output:
            dtype = arrow.int64() if column == f"{prefix}asn" else arrow.string()
            array_values = arrow.array((row[column] for row in mapped.values()), type=dtype)
            result = result.append_column(column, pc.take(array_values, positions))
        return result
    raise TypeError(
        "frame must be a Polars DataFrame, Pandas DataFrame, or PyArrow Table; "
        "install the corresponding ipfacet extra"
    )
