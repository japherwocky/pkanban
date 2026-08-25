import os
import yaml
from pathlib import Path

DEFAULT_CONFIG_FILE = Path.home() / ".pkanban.yaml"


def config_file():
    """Where the config lives, resolved per call rather than at import.

    This used to be a module-level constant, which made KANBAN_CONFIG_PATH
    effective only if it was set before kanban.config was first imported.
    Anything importing the CLI earlier than that -- a test module doing so at
    collection time, before its fixture sets the variable -- silently bound
    the real ~/.kanban.yaml instead, and every later write landed on the
    developer's own credentials.
    """
    return Path(os.environ.get("KANBAN_CONFIG_PATH", DEFAULT_CONFIG_FILE))


# Most installs talk to the hosted service, so default there rather than to a
# localhost nobody is running -- a fresh `pip install` should reach a real
# server on the first command, not a connection error. Self-hosters point
# elsewhere with `kanban config --url http://localhost:8000`.
DEFAULT_SERVER_URL = "https://pkanban.pearachute.com"


def ensure_config_dir():
    config_file().parent.mkdir(parents=True, exist_ok=True)


def load_config():
    ensure_config_dir()
    path = config_file()
    if not path.exists():
        return {"server": {"url": DEFAULT_SERVER_URL}, "auth": {}}
    with open(path) as f:
        return yaml.safe_load(f) or {
            "server": {"url": DEFAULT_SERVER_URL},
            "auth": {},
        }


def save_config(config):
    ensure_config_dir()
    with open(config_file(), "w") as f:
        yaml.dump(config, f)


def get_server_url():
    config = load_config()
    return config.get("server", {}).get("url", DEFAULT_SERVER_URL)


def set_server_url(url):
    config = load_config()
    config["server"] = {"url": url}
    save_config(config)


def get_token():
    config = load_config()
    return config.get("auth", {}).get("token")


def set_token(token):
    config = load_config()
    config.setdefault("auth", {})["token"] = token
    save_config(config)


def clear_token():
    config = load_config()
    if "auth" in config:
        config["auth"].pop("token", None)
        save_config(config)


def get_api_key():
    """Get the preferred API key from config."""
    config = load_config()
    return config.get("auth", {}).get("api_key")


def set_api_key(api_key):
    """Set the preferred API key in config."""
    config = load_config()
    if "auth" not in config:
        config["auth"] = {}
    config["auth"]["api_key"] = api_key
    save_config(config)


def clear_api_key():
    """Clear the API key from config."""
    config = load_config()
    if "auth" in config:
        config["auth"].pop("api_key", None)
        save_config(config)


# In-memory only, for `--api-key`/`-k` passed on a single command line. Must
# never touch disk -- persisting it would silently overwrite the user's saved
# token/API key just because they authenticated one command that way.
_runtime_api_key = None


def set_runtime_api_key(api_key):
    global _runtime_api_key
    _runtime_api_key = api_key


def get_runtime_api_key():
    return _runtime_api_key
