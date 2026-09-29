from __future__ import annotations

from ipaddress import ip_address
from typing import Any, cast

import pandas as pd
import polars as pl
import pyarrow as pa
import pytest

from ipfacet import (
    CanonicalField,
    FieldObservation,
    FieldProvenance,
    FieldState,
    IPEnrichment,
    IPScope,
    ResolvedField,
    enrich_frame,
    open_database,
)
from ipfacet.models import IPAddress


class CountingBackend:
    def __init__(self) -> None:
        self.calls: list[IPAddress] = []

    def lookup(self, ip: IPAddress) -> IPEnrichment | None:
        self.calls.append(ip)
        provenance = FieldProvenance("fixture", "synthetic", "2026-09")
        return IPEnrichment(
            ip=ip, scope=IPScope.GLOBAL, asn=ResolvedField(FieldState.PRESENT, 64500, provenance)
        )


@pytest.mark.parametrize("kind", ["polars", "pandas", "arrow"])
def test_frame_preserves_order_duplicates_nulls_and_details(kind: str) -> None:
    values = ["1.1.1.1", None, "2606:4700::1", "1.1.1.1", "8.8.8.8"]
    if kind == "polars":
        frame = pl.DataFrame({"actor": [1, 2, 3, 4, 5], "src": values})
    elif kind == "pandas":
        frame = pd.DataFrame({"actor": [1, 2, 3, 4, 5], "src": values}, index=[10, 11, 12, 13, 14])
    else:
        frame = pa.table({"actor": [1, 2, 3, 4, 5], "src": values})
    backend = CountingBackend()
    result = enrich_frame(
        open_database(backend=backend),
        frame,
        ip_column="src",
        fields=(CanonicalField.ASN,),
        include_provenance=True,
        include_conflicts=True,
    )
    assert isinstance(result, type(frame))
    rows: list[dict[str, Any]]
    if isinstance(result, pl.DataFrame):
        rows = result.to_dicts()
    elif isinstance(result, pd.DataFrame):
        assert list(result.index) == [10, 11, 12, 13, 14]
        rows = cast(list[dict[str, Any]], result.to_dict("records"))
    else:
        assert isinstance(result, pa.Table)
        rows = result.to_pylist()
    assert [row["actor"] for row in rows] == [1, 2, 3, 4, 5]
    assert rows[0]["ipfacet_asn"] == 64500
    assert rows[2]["ipfacet_asn"] == rows[3]["ipfacet_asn"] == rows[4]["ipfacet_asn"] == 64500
    assert rows[1]["ipfacet_asn"] is None or pd.isna(rows[1]["ipfacet_asn"])
    assert rows[0]["ipfacet_asn_state"] == "present"
    assert rows[1]["ipfacet_asn_state"] is None or pd.isna(rows[1]["ipfacet_asn_state"])
    assert '"provider": "fixture"' in rows[0]["ipfacet_provenance"]
    assert rows[0]["ipfacet_conflicts"] == "{}"
    assert len(backend.calls) == 3
    assert backend.calls.count(ip_address("1.1.1.1")) == 1


@pytest.mark.parametrize("kind", ["polars", "pandas", "arrow"])
def test_invalid_ip_and_column_collision(kind: str) -> None:
    data = {"ip": ["invalid"]}
    frame = (
        pl.DataFrame(data)
        if kind == "polars"
        else pd.DataFrame(data)
        if kind == "pandas"
        else pa.table(data)
    )
    with pytest.raises(ValueError):
        enrich_frame(open_database(), frame, ip_column="ip")
    data = {"ip": ["1.1.1.1"], "ipfacet_scope": ["existing"]}
    frame = (
        pl.DataFrame(data)
        if kind == "polars"
        else pd.DataFrame(data)
        if kind == "pandas"
        else pa.table(data)
    )
    with pytest.raises(ValueError, match="already exist"):
        enrich_frame(open_database(), frame, ip_column="ip")


@pytest.mark.parametrize("kind", ["polars", "pandas", "arrow"])
def test_empty_input(kind: str) -> None:
    frame = (
        pl.DataFrame({"ip": pl.Series([], dtype=pl.String)})
        if kind == "polars"
        else pd.DataFrame({"ip": pd.Series([], dtype="string")})
        if kind == "pandas"
        else pa.table({"ip": pa.array([], type=pa.string())})
    )
    result = enrich_frame(open_database(), frame, ip_column="ip", fields=(CanonicalField.ASN,))
    assert len(result) == 0


def test_polars_all_null_and_equivalent_ipv6_spellings() -> None:
    empty_values = pl.DataFrame({"ip": [None, None]})
    result = enrich_frame(open_database(), empty_values, ip_column="ip")
    assert isinstance(result, pl.DataFrame)
    assert result["ipfacet_scope"].to_list() == [None, None]

    backend = CountingBackend()
    frame = pl.DataFrame({"ip": ["2606:4700::1", "2606:4700:0:0:0:0:0:1"]})
    enriched = enrich_frame(open_database(backend=backend), frame, ip_column="ip")
    assert isinstance(enriched, pl.DataFrame)
    assert enriched["ipfacet_asn"].to_list() == [64500, 64500]
    assert len(backend.calls) == 1


def test_conflict_detail_retains_both_sources() -> None:
    class ConflictBackend:
        def lookup(self, ip: IPAddress) -> IPEnrichment:
            first = FieldProvenance("first", "one", "v1")
            second = FieldProvenance("second", "two", "v2")
            return IPEnrichment(
                ip=ip,
                scope=IPScope.GLOBAL,
                asn=ResolvedField(
                    FieldState.CONFLICT,
                    64500,
                    first,
                    (FieldObservation(64500, first), FieldObservation(64501, second)),
                ),
            )

    result = enrich_frame(
        open_database(backend=ConflictBackend()),
        pl.DataFrame({"ip": ["1.1.1.1"]}),
        ip_column="ip",
        fields=(CanonicalField.ASN,),
        include_conflicts=True,
    )
    assert isinstance(result, pl.DataFrame)
    assert result["ipfacet_asn_state"][0] == "conflict"
    assert '"provider": "first"' in result["ipfacet_conflicts"][0]
    assert '"provider": "second"' in result["ipfacet_conflicts"][0]
