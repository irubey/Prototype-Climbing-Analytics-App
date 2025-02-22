import uvicorn
import os
import sys
from app.core.config import settings


def run_app(reload_mode: bool = False):
    """
    Run the FastAPI application with configurable reload mode.
    
    Args:
        reload_mode: Whether to run with auto-reload enabled
    """
    #build config from settings
    config = {
        "app": settings.APP_IMPORT, # e.g. defined as "app.main:app" in config
        "host": settings.HOST if hasattr(settings, "HOST") else "0.0.0.0",
        "port": settings.PORT if hasattr(settings, "PORT") else 8000,
        "log_level": "info",
        "workers": 1
    }
    
    if reload_mode:
        config["reload"] = True
    else:
        # If not in reload mode, always set the flag (for subsequent runs)
        models_imported = True

    
    uvicorn.run(**config) #unpack config dictionary

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--no-reload",
        action="store_true",
        help="Disable auto-reload (recommended for debugging import issues)"
    )
    args = parser.parse_args()
    
    run_app(reload_mode=not args.no_reload) 