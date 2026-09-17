"""Seed entrypoint delegator for Makefile / backward compatibility."""

from app.seed import main, run_seed

__all__ = ["main", "run_seed"]

if __name__ == "__main__":
    main()
