from __future__ import annotations

from dataclasses import dataclass
from json import load
from pathlib import Path
from typing import Dict, List, Literal, Optional

from backend.common.components.util import NetworkEntry, NetworkUrl

NodeKind = Literal["capital", "region", "infra"]


@dataclass(frozen=True)
class ClusterNodeInfo:
    name: str
    kind: NodeKind
    logical_name: str
    uri: str
    peers: List[str]
    infra_type: Optional[str] = None

    def to_network_entry(self) -> NetworkEntry:
        return NetworkEntry(
            name=self.name,
            address=NetworkUrl(url=self.uri),
        )


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _remote_registry_path() -> Path:
    return _repo_root() / "backend" / "runners" / "remote_registry.json"


def _fly_config_dir() -> Path:
    return _repo_root() / "configs" / "fly"


def _load_remote_registry() -> Dict[str, str]:
    path = _remote_registry_path()
    with path.open("r", encoding="utf-8") as fi:
        data = load(fi)
    return {str(k): str(v) for k, v in data.items()}


def _iter_config_files() -> List[Path]:
    cfg_dir = _fly_config_dir()
    if not cfg_dir.exists():
        return []
    return sorted(p for p in cfg_dir.glob("*.json") if p.is_file())


def _logical_name_from_node_name(name: str) -> str:
    if "-" not in name:
        return name
    base, suffix = name.rsplit("-", 1)
    return base if suffix.isdigit() else name


def build_cluster_topology() -> Dict[str, ClusterNodeInfo]:
    registry = _load_remote_registry()
    topology: Dict[str, ClusterNodeInfo] = {}

    for cfg_path in _iter_config_files():
        with cfg_path.open("r", encoding="utf-8") as fi:
            raw = load(fi)

        name = raw["name"]
        variant = raw["variant"]

        if name not in registry:
            continue

        if variant == "capital":
            capital_cfg = raw["capital"]
            logical_name = capital_cfg.get(
                "capital_name",
                _logical_name_from_node_name(name),
            )
            peers = list(capital_cfg.get("peers", []))
            topology[name] = ClusterNodeInfo(
                name=name,
                kind="capital",
                logical_name=logical_name,
                uri=registry[name],
                peers=peers,
                infra_type=None,
            )

        elif variant == "region":
            region_cfg = raw["region"]
            logical_name = region_cfg.get(
                "region_name",
                _logical_name_from_node_name(name),
            )
            peers = list(region_cfg.get("peers", []))
            topology[name] = ClusterNodeInfo(
                name=name,
                kind="region",
                logical_name=logical_name,
                uri=registry[name],
                peers=peers,
                infra_type=None,
            )

        elif variant == "infra":
            infra_cfg = raw["infra"]
            attached_regions = list(infra_cfg.get("regions", []))

            logical_name = (
                attached_regions[0].rsplit("-", 1)[0]
                if attached_regions and "-" in attached_regions[0]
                else (
                    attached_regions[0]
                    if attached_regions
                    else _logical_name_from_node_name(name)
                )
            )

            topology[name] = ClusterNodeInfo(
                name=name,
                kind="infra",
                logical_name=logical_name,
                uri=registry[name],
                peers=[],
                infra_type=infra_cfg.get("type"),
            )

    for name, uri in registry.items():
        if name in topology:
            continue

        logical_name = _logical_name_from_node_name(name)
        kind: NodeKind = "infra"
        if logical_name == "rm":
            kind = "capital"
        elif name.startswith("hospital"):
            kind = "infra"
        else:
            kind = "region"

        topology[name] = ClusterNodeInfo(
            name=name,
            kind=kind,
            logical_name=logical_name,
            uri=uri,
            peers=[],
            infra_type="hospital" if name.startswith("hospital") else None,
        )

    return topology