"""Notebook-style consumer contract using synthetic, manually installed snapshots."""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

from ipfacet import (
    CanonicalField,
    DatasetStore,
    FieldPrecedence,
    ResolutionPolicy,
    default_dataset_manager,
    enrich_frame,
    open_database,
)
from ipfacet.providers.ipinfo_lite import open_ipinfo_lite
from ipfacet.providers.maxmind_geolite2 import FILES, open_maxmind_geolite2


def test_offline_notebook_contract_with_two_installed_providers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_ipinfo = tmp_path / "ipinfo"
    source_ipinfo.mkdir()
    (source_ipinfo / "ipinfo_lite.csv").write_text(
        "network,country,country_code,continent,continent_code,asn,as_name,as_domain\n"
        "1.1.1.0/24,Australia,AU,Oceania,OC,AS13335,Example Edge,example.test\n"
        "2606:4700::/32,United States,US,North America,NA,AS13335,Example Edge,example.test\n",
        encoding="utf-8",
    )
    source_maxmind = tmp_path / "maxmind"
    source_maxmind.mkdir()
    header = "network,autonomous_system_number,autonomous_system_organization\n"
    (source_maxmind / FILES[0]).write_text(
        header + "1.1.1.0/24,64500,Alternative AS\n8.8.8.0/24,15169,Resolver AS\n",
        encoding="utf-8",
    )
    (source_maxmind / FILES[1]).write_text(
        header + "2606:4700::/32,64501,Alternative IPv6 AS\n",
        encoding="utf-8",
    )
    store = DatasetStore(tmp_path / "installed")
    manager = default_dataset_manager(store=store)
    manager.import_dataset("ipinfo", "ipinfo-lite", source_ipinfo, release="fixture-a")
    manager.import_dataset("maxmind", "geolite2-asn", source_maxmind, release="fixture-b")
    manager.verify("ipinfo", "ipinfo-lite")
    manager.verify("maxmind", "geolite2-asn")

    # Acquisition is over; a notebook lookup must never reach the network.
    def no_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("lookup attempted network access")

    monkeypatch.setattr("urllib.request.urlopen", no_network)
    providers = (open_ipinfo_lite(store), open_maxmind_geolite2(store))
    policy = ResolutionPolicy(
        tuple(
            FieldPrecedence(field, ("ipinfo", "maxmind"))
            for field in (
                CanonicalField.ASN,
                CanonicalField.AS_NAME,
                CanonicalField.NETWORK,
            )
        )
        + tuple(
            FieldPrecedence(field, ("ipinfo",))
            for field in (
                CanonicalField.AS_DOMAIN,
                CanonicalField.COUNTRY_CODE,
                CanonicalField.COUNTRY_NAME,
                CanonicalField.CONTINENT_CODE,
            )
        )
    )
    db = open_database(providers=providers, policy=policy)
    events = pl.DataFrame(
        {
            "actor": ["a", "a", "b", "c", "c"],
            "source_ip": ["1.1.1.1", "1.1.1.1", "8.8.8.8", "2606:4700::1", None],
        }
    )
    enriched = enrich_frame(
        db,
        events,
        ip_column="source_ip",
        fields=(CanonicalField.ASN, CanonicalField.COUNTRY_CODE),
        include_provenance=True,
        include_conflicts=True,
    )
    assert isinstance(enriched, pl.DataFrame)
    assert enriched.height == events.height
    assert enriched["ipfacet_asn"].to_list() == [13335, 13335, 15169, 13335, None]
    assert enriched["ipfacet_asn_state"].to_list() == [
        "conflict",
        "conflict",
        "present",
        "conflict",
        None,
    ]
    assert enriched["ipfacet_country_code"].to_list() == ["AU", "AU", None, "US", None]
    first = json.loads(enriched["ipfacet_conflicts"][0])
    assert {item["provenance"]["provider"] for item in first["asn"]} == {
        "ipinfo",
        "maxmind",
    }
    fallback = json.loads(enriched["ipfacet_provenance"][2])
    assert fallback["asn"]["provider"] == "maxmind"

    # Behavioral relationships are derived by the consumer, outside IPFacet.
    relationships = enriched.drop_nulls("ipfacet_asn").group_by("actor", "ipfacet_asn").len()
    assert relationships.height == 3
    assert relationships.filter(pl.col("actor") == "a")["len"].item() == 2
