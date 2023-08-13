#! /usr/bin/env python3

if __name__ == "__main__":
    import sys
    from app.main import app
    import uvicorn

    if sys.argv.pop() == "--reload":
        uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
    else:
        uvicorn.run(app, host="0.0.0.0", port=8000)
