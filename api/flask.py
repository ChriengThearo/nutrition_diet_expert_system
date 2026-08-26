import traceback

try:
    from run import app
except Exception:
    print("=== VERCEL FLASK STARTUP FAILURE ===")
    traceback.print_exc()
    raise

__all__ = ["app"]
