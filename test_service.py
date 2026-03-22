"""Manual smoke-test script (not a pytest test).

This file is named `test_service.py`, but it's intended to be run directly.
To avoid side effects during `pytest` collection, all logic is behind a
`__main__` guard and pytest collection is disabled via `__test__ = False`.
"""

__test__ = False


def main() -> None:
    # Local import so pytest collection doesn't require these deps/paths.
    import sys
    from pathlib import Path

    backend_dir = Path(__file__).resolve().parent / "backend"
    sys.path.insert(0, str(backend_dir))

    from app.services.user_card_service import UserCardManagementService  # type: ignore
    from app.services.errors import ServiceError  # type: ignore

    print("=" * 60)
    print("Testing UserCardManagementService (manual script)")
    print("=" * 60)

    try:
        print("\nThis script is no longer kept in sync with the SQLAlchemy-backed service.")
        print("Run the real test suite via: python -m pytest")
        _ = UserCardManagementService  # silence unused import
    except ServiceError as e:
        print(f"✗ ServiceError: {e.status_code} {e.code} - {e.message}")
        print(f"   Details: {e.details}")
    except Exception as e:
        print(f"✗ Exception: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
