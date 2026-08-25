#!/usr/bin/env python
"""
pkanban server management script.

Usage:
    python manage.py init                         # Initialize database
    python manage.py wipe                         # Wipe database (destructive)
    python manage.py user-create <user> <pass>    # Create a user
    python manage.py server                       # Run the server
    python manage.py migrate                      # Apply pending migrations
    python manage.py status                       # Show database status
"""
import argparse
import sys
import os
import subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.database import db
from backend.models import ALL_MODELS, User


# Read from backend.models rather than maintaining a second list. The old
# hand-written copy here fell three tables behind (ApiKey, BetaSignup,
# OrganizationInvite), so `init` built an incomplete schema and `status`
# under-reported. This only ever went unnoticed because init_db() creates the
# missing tables when the server next starts.
TABLES = ALL_MODELS


def cmd_init(args=None):
    """Create all database tables."""
    db.connect()
    db.create_tables(TABLES)
    db.close()
    print("Database initialized. Tables created:")
    for model in TABLES:
        print(f"  - {model.__name__}")


def cmd_wipe(args=None):
    """Drop all tables and recreate them. DESTROYS ALL DATA."""
    print("WARNING: This will delete ALL data in the database.")
    confirm = input("Type 'yes' to continue: ")
    if confirm != "yes":
        print("Aborted.")
        sys.exit(1)

    db.connect()
    db.drop_tables(TABLES)
    print("Tables dropped.")
    db.create_tables(TABLES)
    db.close()
    print("Database wiped and recreated. Tables created:")
    for model in TABLES:
        print(f"  - {model.__name__}")


def cmd_user_create(args):
    """Create a new user."""
    db.connect()
    try:
        user = User.create_user(args.username, args.password, email=args.email, admin=args.admin)
        print(f"User '{args.username}' created successfully with id={user.id}")
    except Exception as e:
        print(f"Error creating user: {e}")
        sys.exit(1)
    finally:
        db.close()


def cmd_server(args):
    """Run the development server."""
    cmd = [sys.executable, "-m", "uvicorn", "backend.main:app"]

    cmd.extend(["--host", args.host])
    cmd.extend(["--port", str(args.port)])

    if args.reload:
        cmd.append("--reload")

    if args.log_level:
        cmd.extend(["--log-level", args.log_level])

    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.dirname(os.path.abspath(__file__))

    print(f"Starting server at http://{args.host}:{args.port}")
    if args.reload:
        print("Reload enabled.")

    try:
        subprocess.run(cmd, env=env)
    except KeyboardInterrupt:
        print("\nServer stopped.")


MIGRATIONS_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "backend", "migrations"
)


def _router():
    import logging
    from peewee_migrate import Router

    # peewee-migrate reports what it applies through this logger; without a
    # handler the deploy log would show nothing but our own prints.
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    db.connect(reuse_if_open=True)
    return Router(db, migrate_dir=MIGRATIONS_DIR)


def cmd_migrate(args):
    """Apply any migrations this database has not seen yet.

    Safe to run on every deploy: peewee-migrate records applied migrations in
    a migratehistory table and skips them next time. Each migration runs in a
    transaction, so a failure rolls back rather than leaving a half-migrated
    schema.
    """
    router = _router()

    if args.list:
        done = router.done
        todo = [name for name in router.todo if name not in done]
        print(f"Database: {db.database}")
        print("Applied:")
        for name in done or ["  (none)"]:
            print(f"  {name}" if done else name)
        print("Pending:")
        for name in todo or ["  (none)"]:
            print(f"  {name}" if todo else name)
        return

    # Always name the database. There is more than one plausible path on a
    # deployed box, and "which file did that actually touch" is the first
    # question when a migration appears to have done nothing.
    print(f"Database: {db.database}")

    pending = [name for name in router.todo if name not in router.done]
    if not pending:
        print("No pending migrations.")
        return

    print(f"Applying {len(pending)} migration(s): {', '.join(pending)}")
    try:
        applied = router.run(fake=args.fake)
    except Exception as e:
        # Non-zero exit matters: deploy.sh runs under `set -e`, and a deploy
        # that restarts the service against an unmigrated database is an
        # outage, not a warning.
        print(f"\nMigration failed: {e}", file=sys.stderr)
        sys.exit(1)

    for name in applied:
        print(f"  applied {name}")
    print("Migrations complete.")


def cmd_status(args=None):
    """Show database status."""
    db.connect()
    print("Database status:")
    print(f"  Path: {db.database}")
    print("  Tables:")
    for model in TABLES:
        count = model.select().count()
        print(f"    - {model.__name__}: {count} records")
    db.close()


def main():
    parser = argparse.ArgumentParser(
        prog="python manage.py",
        description="pkanban server management"
    )
    parser.add_argument(
        "--log-level",
        choices=["debug", "info", "warning", "error"],
        help="Set logging level"
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    sp_init = subparsers.add_parser("init", help="Initialize database (create all tables)")
    sp_init.set_defaults(func=cmd_init)

    sp_wipe = subparsers.add_parser("wipe", help="Drop and recreate all tables (destructive)")
    sp_wipe.set_defaults(func=cmd_wipe)

    sp_user = subparsers.add_parser("user-create", help="Create a new user")
    sp_user.add_argument("username", help="Username")
    sp_user.add_argument("password", help="Password")
    sp_user.add_argument("--email", default=None, help="User email")
    sp_user.add_argument("--admin", action="store_true", help="Make user a platform admin")
    sp_user.set_defaults(func=cmd_user_create)

    sp_server = subparsers.add_parser("server", help="Run the development server")
    sp_server.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    sp_server.add_argument("--port", type=int, default=8080, help="Port to bind to")
    sp_server.add_argument("--reload", action="store_true", default=True, help="Enable auto-reload (default)")
    sp_server.add_argument("--no-reload", dest="reload", action="store_false", help="Disable auto-reload")
    sp_server.set_defaults(func=cmd_server)

    sp_migrate = subparsers.add_parser("migrate", help="Apply pending database migrations")
    sp_migrate.add_argument("--list", action="store_true", help="Show applied and pending migrations without running any")
    sp_migrate.add_argument("--fake", action="store_true", help="Record migrations as applied without running them")
    sp_migrate.set_defaults(func=cmd_migrate)

    sp_status = subparsers.add_parser("status", help="Show database status")
    sp_status.set_defaults(func=cmd_status)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        print("\nCommands:")
        print("  init               Initialize database")
        print("  wipe               Wipe database (destructive)")
        print("  user-create        Create a new user")
        print("  server             Run the development server")
        print("  migrate            Apply pending database migrations")
        print("  status             Show database status")
        print("\nServer options:")
        print("  --host HOST        Host to bind to (default: 0.0.0.0)")
        print("  --port PORT        Port to bind to (default: 8080)")
        print("  --reload           Enable auto-reload (default)")
        print("  --no-reload        Disable auto-reload")
        print("  --log-level LEVEL  Set logging level (debug, info, warning, error)")
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
