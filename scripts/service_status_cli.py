#!/usr/bin/env python3

import toml
import requests
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from rich.layout import Layout
from rich import box
import time
from datetime import datetime
import sys
from typing import Dict, Optional, TypedDict


class ServiceStatus(TypedDict):
    status: str
    description: str
    code: Optional[int]


class ServiceDict(TypedDict):
    services: Dict[str, str]


console = Console()


def load_urls_from_toml(file_path: str) -> Dict[str, str]:
    try:
        config: Dict[str, Dict[str, str]] = toml.load(file_path)
        return config.get("services", {})
    except FileNotFoundError:
        console.print("[red]Error:[/red] urls_config.toml not found")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error loading configuration:[/red] {str(e)}")
        sys.exit(1)


def check_service_status(url: str) -> ServiceStatus:
    try:
        response = requests.get(url, timeout=5)
        return {
            "status": "up" if response.status_code == 200 else "down",
            "description": f"HTTP {response.status_code}",
            "code": response.status_code,
        }
    except requests.RequestException as e:
        return {"status": "error", "description": str(e), "code": None}


def get_status_color(status: str) -> str:
    return {
        "ok": "green",
        "operational": "green",
        "critical": "red",
        "unknown": "yellow",
        "up": "green",
        "down": "red",
        "error": "red",
    }.get(status.lower(), "yellow")


def create_status_table(
    services: Dict[str, str], statuses: Dict[str, ServiceStatus]
) -> Table:
    table = Table(title="Service Status Dashboard", box=box.ROUNDED)

    table.add_column("Service", style="cyan", no_wrap=True)
    table.add_column("URL", style="blue")
    table.add_column("Status", justify="center")
    table.add_column("Response Code", justify="center")
    table.add_column("Description")

    for name, url in services.items():
        status: ServiceStatus = statuses.get(
            url, {"status": "unknown", "description": "Checking...", "code": None}
        )
        status_color = get_status_color(status.get("status", "unknown"))

        table.add_row(
            name,
            url,
            f"[{status_color}]{status.get('status', 'unknown')}[/{status_color}]",
            str(status.get("code", "N/A")),
            status.get("description", "Checking..."),
        )

    return table


def create_layout(
    services: Dict[str, str], statuses: Dict[str, ServiceStatus]
) -> Layout:
    layout = Layout()

    table = create_status_table(services, statuses)
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    stats_panel = Panel(
        f"Last Updated: {current_time}\n" f"Services Monitored: {len(services)}",
        title="Statistics",
        border_style="blue",
    )

    layout.split(Layout(table, ratio=4), Layout(stats_panel, ratio=1))

    return layout


def main() -> None:
    console.clear()
    console.print("[cyan]Loading service configuration...[/cyan]")

    services = load_urls_from_toml("urls_config.toml")
    statuses: Dict[str, ServiceStatus] = {}

    with Live(create_layout(services, statuses), refresh_per_second=1) as live:
        while True:
            for url in services.values():
                statuses[url] = check_service_status(url)
                live.update(create_layout(services, statuses))
            time.sleep(30)  # Update every 30 seconds


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down...[/yellow]")
        sys.exit(0)
