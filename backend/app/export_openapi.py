"""OpenAPI YAML exporter for FlagOps FastAPI backend."""

import sys
import yaml

if hasattr(sys.stdout, "reconfigure") and sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

from app.main import app


def export_openapi() -> str:
    """Generate OpenAPI schema and dump it to YAML format."""
    openapi_schema = app.openapi()
    return yaml.dump(openapi_schema, sort_keys=False, allow_unicode=True)


if __name__ == "__main__":
    content = export_openapi()
    sys.stdout.write(content + "\n")

