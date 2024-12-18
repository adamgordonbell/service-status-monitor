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

console = Console()

def load_urls_from_toml(file_path):
    try:
        config = toml.load(file_path)
        return config.get("services", {})
    except FileNotFoundError:
        console.print("[red]Error:[/red] urls_config.toml not found")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error loading configuration:[/red] {str(e)}")
        sys.exit(1)

def check_url_status(url):
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json() if "json" in response.headers.get("Content-Type", "") else {}
            return {
                "status": data.get("status", {}).get("indicator", "ok"),
                "description": data.get("status", {}).get("description", "Operational"),
                "code": response.status_code
            }
        else:
            return {
                "status": "critical",
                "description": f"HTTP {response.status_code}",
                "code": response.status_code
            }
    except requests.exceptions.RequestException as e:
        return {
            "status": "critical",
            "description": str(e),
            "code": None
        }

def get_status_color(status):
    return {
        "ok": "green",
        "operational": "green",
        "critical": "red",
        "unknown": "yellow"
    }.get(status.lower(), "yellow")

def create_status_table(services, statuses):
    table = Table(title="Service Status Dashboard", box=box.ROUNDED)
    
    table.add_column("Service", style="cyan", no_wrap=True)
    table.add_column("URL", style="blue")
    table.add_column("Status", justify="center")
    table.add_column("Response Code", justify="center")
    table.add_column("Description")

    for name, url in services.items():
        status = statuses.get(url, {})
        status_color = get_status_color(status.get("status", "unknown"))
        
        table.add_row(
            name,
            url,
            f"[{status_color}]{status.get('status', 'unknown')}[/{status_color}]",
            str(status.get("code", "N/A")),
            status.get("description", "Checking...")
        )
    
    return table

def create_layout(services, statuses):
    layout = Layout()
    
    table = create_status_table(services, statuses)
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    stats_panel = Panel(
        f"Last Updated: {current_time}\n"
        f"Services Monitored: {len(services)}",
        title="Statistics",
        border_style="blue"
    )
    
    layout.split(
        Layout(table, ratio=4),
        Layout(stats_panel, ratio=1)
    )
    
    return layout

def main():
    console.clear()
    console.print("[cyan]Loading service configuration...[/cyan]")
    
    services = load_urls_from_toml("urls_config.toml")
    statuses = {}
    
    with Live(create_layout(services, statuses), refresh_per_second=1) as live:
        while True:
            for url in services.values():
                statuses[url] = check_url_status(url)
                live.update(create_layout(services, statuses))
            time.sleep(30)  # Update every 30 seconds

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down...[/yellow]")
        sys.exit(0)
