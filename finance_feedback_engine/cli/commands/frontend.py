"""
Frontend management commands for Finance Feedback Engine.

Manages the React frontend lifecycle: development server, production build, and serving.
"""

import os
import subprocess
import sys
from pathlib import Path

import click


@click.group()
def frontend():
    """Manage the React frontend (dev, build, serve)."""
    pass


@frontend.command()
@click.option(
    "--port", default=5173, type=int, help="Development server port (default: 5173)"
)
def dev(port: int):
    """Start frontend development server with hot reload."""
    frontend_dir = Path(__file__).parent.parent.parent.parent / "frontend"

    if not frontend_dir.exists():
        click.echo(
            click.style("❌ Frontend directory not found at frontend/", fg="red")
        )
        sys.exit(1)

    # Check if node_modules exists
    node_modules = frontend_dir / "node_modules"
    if not node_modules.exists():
        click.echo(click.style("📦 Installing frontend dependencies...", fg="yellow"))
        try:
            subprocess.run(["npm", "install"], cwd=frontend_dir, check=True)
        except subprocess.CalledProcessError as e:
            click.echo(click.style(f"❌ npm install failed: {e}", fg="red"))
            sys.exit(1)

    click.echo(
        click.style(f"🚀 Starting frontend dev server on port {port}...", fg="green")
    )
    click.echo(click.style(f"   Frontend URL: http://localhost:{port}", fg="cyan"))
    click.echo(
        click.style(
            f"   Backend API: http://localhost:8000 (start with 'python main.py serve')",
            fg="cyan",
        )
    )

    try:
        subprocess.run(
            ["npm", "run", "dev", "--", "--port", str(port)],
            cwd=frontend_dir,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        click.echo(click.style(f"❌ Frontend dev server failed: {e}", fg="red"))
        sys.exit(1)
    except KeyboardInterrupt:
        click.echo(click.style("\n👋 Frontend dev server stopped", fg="yellow"))


@frontend.command()
@click.option(
    "--output-dir", default="dist", help="Build output directory (default: dist)"
)
def build(output_dir: str):
    """Build frontend for production."""
    frontend_dir = Path(__file__).parent.parent.parent.parent / "frontend"

    if not frontend_dir.exists():
        click.echo(
            click.style("❌ Frontend directory not found at frontend/", fg="red")
        )
        sys.exit(1)

    # Check if node_modules exists
    node_modules = frontend_dir / "node_modules"
    if not node_modules.exists():
        click.echo(click.style("📦 Installing frontend dependencies...", fg="yellow"))
        try:
            subprocess.run(["npm", "install"], cwd=frontend_dir, check=True)
        except subprocess.CalledProcessError as e:
            click.echo(click.style(f"❌ npm install failed: {e}", fg="red"))
            sys.exit(1)

    click.echo(click.style("🔨 Building frontend for production...", fg="green"))

    try:
        subprocess.run(
            ["npm", "run", "build"],
            cwd=frontend_dir,
            check=True,
            env={**os.environ, "VITE_OUTPUT_DIR": output_dir},
        )

        dist_dir = frontend_dir / output_dir
        if dist_dir.exists():
            click.echo(
                click.style(f"✅ Frontend build complete: {dist_dir}", fg="green")
            )
            click.echo(
                click.style(f"   Serve with: python main.py frontend serve", fg="cyan")
            )
        else:
            click.echo(
                click.style(
                    f"⚠️  Build completed but {output_dir}/ not found", fg="yellow"
                )
            )

    except subprocess.CalledProcessError as e:
        click.echo(click.style(f"❌ Frontend build failed: {e}", fg="red"))
        sys.exit(1)


@frontend.command()
@click.option(
    "--port", default=8080, type=int, help="Static file server port (default: 8080)"
)
@click.option(
    "--dist-dir", default="dist", help="Distribution directory to serve (default: dist)"
)
def serve(port: int, dist_dir: str):
    """Serve built frontend (production mode)."""
    frontend_dir = Path(__file__).parent.parent.parent.parent / "frontend"
    dist_path = frontend_dir / dist_dir

    if not dist_path.exists():
        click.echo(click.style(f"❌ Build directory not found: {dist_path}", fg="red"))
        click.echo(
            click.style(f"   Run 'python main.py frontend build' first", fg="yellow")
        )
        sys.exit(1)

    click.echo(
        click.style(f"🌐 Serving frontend on http://localhost:{port}", fg="green")
    )
    click.echo(
        click.style(
            f"   Backend API: http://localhost:8000 (start with 'python main.py serve')",
            fg="cyan",
        )
    )

    try:
        # Use Python's built-in HTTP server for simplicity
        subprocess.run(
            [sys.executable, "-m", "http.server", str(port)], cwd=dist_path, check=True
        )
    except subprocess.CalledProcessError as e:
        click.echo(click.style(f"❌ Failed to serve frontend: {e}", fg="red"))
        sys.exit(1)
    except KeyboardInterrupt:
        click.echo(click.style("\n👋 Frontend server stopped", fg="yellow"))


@frontend.command()
def install():
    """Install frontend dependencies (npm install)."""
    frontend_dir = Path(__file__).parent.parent.parent.parent / "frontend"

    if not frontend_dir.exists():
        click.echo(
            click.style("❌ Frontend directory not found at frontend/", fg="red")
        )
        sys.exit(1)

    click.echo(click.style("📦 Installing frontend dependencies...", fg="green"))

    try:
        subprocess.run(["npm", "install"], cwd=frontend_dir, check=True)
        click.echo(click.style("✅ Frontend dependencies installed", fg="green"))
    except subprocess.CalledProcessError as e:
        click.echo(click.style(f"❌ npm install failed: {e}", fg="red"))
        sys.exit(1)


@frontend.command()
def status():
    """Check frontend build status and dependencies."""
    frontend_dir = Path(__file__).parent.parent.parent.parent / "frontend"

    if not frontend_dir.exists():
        click.echo(click.style("❌ Frontend directory not found", fg="red"))
        return

    click.echo(click.style("📊 Frontend Status", fg="cyan", bold=True))
    click.echo()

    # Check node_modules
    node_modules = frontend_dir / "node_modules"
    if node_modules.exists():
        click.echo(click.style("✅ Dependencies installed (node_modules/)", fg="green"))
    else:
        click.echo(click.style("❌ Dependencies not installed", fg="red"))
        click.echo(click.style("   Run: python main.py frontend install", fg="yellow"))

    # Check dist
    dist_dir = frontend_dir / "dist"
    if dist_dir.exists():
        click.echo(click.style("✅ Production build exists (dist/)", fg="green"))
    else:
        click.echo(click.style("⚠️  No production build found", fg="yellow"))
        click.echo(click.style("   Run: python main.py frontend build", fg="yellow"))

    # Check package.json
    package_json = frontend_dir / "package.json"
    if package_json.exists():
        import json

        with open(package_json) as f:
            pkg = json.load(f)
        click.echo()
        click.echo(f"   Name: {pkg.get('name', 'unknown')}")
        click.echo(f"   Version: {pkg.get('version', 'unknown')}")
        deps = pkg.get("dependencies", {})
        click.echo(f"   Framework: react={deps.get('react', 'unknown')}")
