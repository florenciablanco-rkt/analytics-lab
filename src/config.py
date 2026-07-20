"""Carga de configuración de clientes desde config/clients/*.yaml."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config" / "clients"


@dataclass
class App:
    app_id: str
    label: str
    platform: str = ""


@dataclass
class ClientConfig:
    slug: str                         # nombre del archivo sin extensión (ej. "vix")
    name: str
    apps: list[App]
    purchase_event: str
    install_event: str = "install"
    rocket_channels: list[str] = field(default_factory=lambda: ["rocket"])
    rocket_channel_patterns: list[str] = field(default_factory=list)
    rocket_label: str = "Rocket Lab"
    organic_channels: list[str] = field(default_factory=list)
    channel_groups: dict[str, str] = field(default_factory=dict)
    data_source: dict = field(default_factory=dict)

    @property
    def app_ids(self) -> list[str]:
        return [a.app_id for a in self.apps]

    def app_label(self, app_id: str) -> str:
        for a in self.apps:
            if a.app_id == app_id:
                return a.label
        return app_id

    def group_of(self, canal: str) -> str:
        """Grupo legible de un canal crudo. Lo no mapeado cae en 'Otros'."""
        return self.channel_groups.get(canal, "Otros")

    def is_rocket(self, canal: str) -> bool:
        c = str(canal).lower()
        if any(p.lower() in c for p in self.rocket_channel_patterns):
            return True
        return canal in self.rocket_channels

    def display_channel(self, canal: str) -> str:
        """Nombre a mostrar: los canales de Rocket se colapsan en rocket_label."""
        return self.rocket_label if self.is_rocket(canal) else str(canal)

    def is_organic(self, canal: str) -> bool:
        return canal in self.organic_channels


def load_client(slug: str) -> ClientConfig:
    path = CONFIG_DIR / f"{slug}.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    apps = [App(**a) for a in data.get("apps", [])]
    return ClientConfig(
        slug=slug,
        name=data["name"],
        apps=apps,
        purchase_event=data["purchase_event"],
        install_event=data.get("install_event", "install"),
        rocket_channels=data.get("rocket_channels", ["rocket"]),
        rocket_channel_patterns=data.get("rocket_channel_patterns", []),
        rocket_label=data.get("rocket_label", "Rocket Lab"),
        organic_channels=data.get("organic_channels", []),
        channel_groups=data.get("channel_groups", {}),
        data_source=data.get("data_source", {}),
    )


def list_clients() -> list[tuple[str, str]]:
    """(slug, name) de cada cliente configurado, ordenado por nombre."""
    out = []
    for path in sorted(CONFIG_DIR.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        out.append((path.stem, data.get("name", path.stem)))
    return sorted(out, key=lambda x: x[1])
