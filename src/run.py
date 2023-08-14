#! /usr/bin/env python3

if __name__ == "__main__":
    import sys
    import uvicorn
    from app.main import create_app

    if sys.argv.pop() == "--reload":
        uvicorn.run(
            "app.main:create_app", host="0.0.0.0", port=8000, reload=True, factory=True
        )
    else:
        app = create_app()
        uvicorn.run(app, host="0.0.0.0", port=8000)
