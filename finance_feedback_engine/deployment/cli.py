"""
CLI Interface with Rich

Beautiful command-line interface for deployment orchestration.
Uses Rich for styled terminal output and progress tracking.
"""

import sys

import click
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from .orchestrator import DeploymentError, DeploymentOrchestrator

console = Console()


def print_banner():
    """Print deployment banner."""
    banner = """
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║   Finance Feedback Engine 2.0 - Deployment Orchestrator  ║
║                                                           ║
║   Production-Ready Automated Deployment                  ║
║   Built with TDD, Tracing, and Comprehensive Logging     ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
    """
    console.print(banner, style="bold cyan")


def print_environment_info(environment: str):
    """Print environment information."""
    env_colors = {
        "production": "red",
        "staging": "yellow",
        "dev": "green",
    }

    table = Table(title="Deployment Configuration", box=box.ROUNDED)
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style=env_colors.get(environment, "white"))

    table.add_row("Environment", environment.upper())
    table.add_row("Target", "Docker Containers")
    table.add_row("Services", "Backend, Frontend, Prometheus, Grafana")

    console.print(table)


def print_success(message: str, details: dict = None):
    """Print success message."""
    console.print(f"\n✅ [bold green]{message}[/bold green]")

    if details:
        table = Table(show_header=False, box=box.SIMPLE)
        for key, value in details.items():
            table.add_row(f"  {key}:", str(value))
        console.print(table)


def print_error(message: str, error: Exception = None):
    """Print error message."""
    console.print(f"\n❌ [bold red]{message}[/bold red]")

    if error:
        console.print(f"   [red]{str(error)}[/red]")


def print_warning(message: str):
    """Print warning message."""
    console.print(f"\n⚠️  [bold yellow]{message}[/bold yellow]")


def confirm_deployment(environment: str) -> bool:
    """Confirm deployment with user."""
    if environment == "production":
        console.print("\n[bold red]⚠️  WARNING: Deploying to PRODUCTION[/bold red]")
        console.print("This will affect live trading operations.")

        return click.confirm("\nDo you want to continue?", default=False)

    return True


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """
    Finance Feedback Engine - Deployment Orchestrator

    A comprehensive, production-ready deployment tool with TDD,
    tracing, and logging built-in.
    """
    pass


@cli.command()
@click.argument("environment", type=click.Choice(["production", "staging", "dev"]))
@click.option("--no-cache", is_flag=True, help="Build without Docker cache")
@click.option("--skip-tests", is_flag=True, help="Skip test execution")
@click.option(
    "--project-root",
    type=click.Path(exists=True),
    default=".",
    help="Project root directory",
)
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompts")
def deploy(
    environment: str, no_cache: bool, skip_tests: bool, project_root: str, yes: bool
):
    """
    Deploy the Finance Feedback Engine to specified environment.

    \b
    Examples:
        ffe-deploy deploy production
        ffe-deploy deploy staging --no-cache
        ffe-deploy deploy dev --skip-tests
    """
    print_banner()
    print_environment_info(environment)

    # Confirmation
    if not yes:
        if not confirm_deployment(environment):
            console.print("\n[yellow]Deployment cancelled[/yellow]")
            sys.exit(0)

    # Initialize orchestrator
    console.print("\n[cyan]Initializing deployment orchestrator...[/cyan]")

    try:
        orchestrator = DeploymentOrchestrator(
            environment=environment,
            project_root=project_root,
            no_cache=no_cache,
            skip_tests=skip_tests,
        )

        # Execute deployment with progress tracking
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as progress:

            # Validation
            task = progress.add_task("[cyan]Validating environment...", total=None)
            try:
                orchestrator.run_validations()
                progress.update(task, description="[green]✓ Validation complete")
            except DeploymentError:
                progress.update(task, description="[red]✗ Validation failed")
                raise

            # Setup
            task = progress.add_task("[cyan]Setting up environment...", total=None)
            orchestrator.setup_environment()
            progress.update(task, description="[green]✓ Setup complete")

            # Pull images
            task = progress.add_task("[cyan]Pulling base Docker images...", total=None)
            orchestrator.pull_base_images()
            progress.update(task, description="[green]✓ Base images pulled")

            # Build
            task = progress.add_task("[cyan]Building Docker images...", total=None)
            orchestrator.build_images()
            progress.update(task, description="[green]✓ Images built")

            # Deploy
            task = progress.add_task("[cyan]Deploying services...", total=None)
            orchestrator.deploy_services()
            progress.update(task, description="[green]✓ Services deployed")

            # Verify
            task = progress.add_task("[cyan]Verifying deployment...", total=None)
            orchestrator.verify_deployment()
            progress.update(task, description="[green]✓ Deployment verified")

        # Success summary
        status = orchestrator.get_status()

        print_success(
            "Deployment completed successfully!",
            {
                "Deployment ID": status["deployment_id"],
                "Duration": f"{status['duration_seconds']:.1f}s",
                "Environment": environment,
            },
        )

        # Service URLs
        console.print("\n[bold cyan]Service URLs:[/bold cyan]")
        if environment == "dev":
            console.print("  Frontend (Vite):  http://localhost:5173")
            console.print("  Backend API:      http://localhost:8000")
        else:
            console.print("  Frontend:         http://localhost:80")
            console.print("  Backend API:      http://localhost:8000")
            console.print("  API Docs:         http://localhost:8000/docs")
            console.print("  Prometheus:       http://localhost:9090")
            console.print("  Grafana:          http://localhost:3001")

        console.print(
            f"\n[green]Logs: {project_root}/logs/deployment_{status['deployment_id']}.log[/green]\n"
        )

    except DeploymentError as e:
        print_error("Deployment failed", e)
        sys.exit(1)

    except KeyboardInterrupt:
        print_warning("Deployment cancelled by user")
        sys.exit(130)

    except Exception as e:
        print_error("Unexpected error", e)
        sys.exit(1)


@cli.command()
@click.argument("environment", type=click.Choice(["production", "staging", "dev"]))
@click.option("--project-root", type=click.Path(exists=True), default=".")
def validate(environment: str, project_root: str):
    """
    Validate environment without deploying.

    \b
    Examples:
        ffe-deploy validate production
        ffe-deploy validate staging
    """
    console.print(f"[cyan]Validating {environment} environment...[/cyan]\n")

    try:
        orchestrator = DeploymentOrchestrator(
            environment=environment, project_root=project_root
        )

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("[cyan]Running validations...", total=None)
            orchestrator.run_validations()
            progress.update(task, description="[green]✓ All validations passed")

        print_success("Environment validation successful!")

    except DeploymentError as e:
        print_error("Validation failed", e)
        sys.exit(1)


@cli.command()
@click.option("--project-root", type=click.Path(exists=True), default=".")
def status(project_root: str):
    """
    Check deployment status.

    \b
    Examples:
        ffe-deploy status
    """
    from .docker import DockerOperations
    from .health import HealthChecker

    console.print("[cyan]Checking deployment status...[/cyan]\n")

    docker_ops = DockerOperations(project_root)
    health_checker = HealthChecker()

    # Container status
    status_table = Table(title="Container Status", box=box.ROUNDED)
    status_table.add_column("Container", style="cyan")
    status_table.add_column("Status", style="green")

    container_status = docker_ops.get_container_status()
    for container, status in container_status.items():
        status_table.add_row(container, status)

    console.print(status_table)

    # Health checks
    console.print("\n[cyan]Running health checks...[/cyan]")

    health_status = health_checker.check_all(skip_optional=True)

    health_table = Table(title="Service Health", box=box.ROUNDED)
    health_table.add_column("Service", style="cyan")
    health_table.add_column("Health", style="green")

    for service, healthy in health_status.items():
        if service != "overall":
            health_icon = "✓" if healthy else "✗"
            health_color = "green" if healthy else "red"
            health_table.add_row(
                service.capitalize(),
                f"[{health_color}]{health_icon} {'Healthy' if healthy else 'Unhealthy'}[/{health_color}]",
            )

    console.print(health_table)


@cli.command()
def help_guide():
    """
    Show comprehensive deployment guide.
    """
    guide = """
[bold cyan]Finance Feedback Engine - Deployment Guide[/bold cyan]

[yellow]Quick Start:[/yellow]

  1. Validate environment:
     $ ffe-deploy validate production

  2. Deploy to environment:
     $ ffe-deploy deploy production

  3. Check status:
     $ ffe-deploy status

[yellow]Deployment Stages:[/yellow]

  1. [cyan]Validation[/cyan]  - Check Docker, config, and system resources
  2. [cyan]Setup[/cyan]        - Create directories and initialize databases
  3. [cyan]Pull Images[/cyan]  - Pull base Docker images
  4. [cyan]Build[/cyan]        - Build backend and frontend images
  5. [cyan]Deploy[/cyan]       - Start all services with docker-compose
  6. [cyan]Verify[/cyan]       - Health check all services

[yellow]Environments:[/yellow]

  • [green]dev[/green]        - Local development with hot reload
  • [yellow]staging[/yellow]   - Testing with sandbox APIs
  • [red]production[/red] - Live trading (requires confirmation)

[yellow]Features:[/yellow]

  ✓ TDD-built with comprehensive test coverage
  ✓ Distributed tracing for all operations
  ✓ Structured JSON logging
  ✓ Automated health checks
  ✓ Beautiful terminal UI with Rich
  ✓ Comprehensive error handling

[yellow]Documentation:[/yellow]

  Full guide: docs/DEPLOYMENT.md
  README:     README.md

[yellow]Troubleshooting:[/yellow]

  Check logs:     logs/deployment_<id>.log
  Container logs: docker-compose logs -f
  Status:         ffe-deploy status
    """

    console.print(Panel(guide, border_style="cyan", title="Deployment Guide"))


if __name__ == "__main__":
    cli()
