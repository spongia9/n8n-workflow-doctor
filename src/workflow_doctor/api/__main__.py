"""One-process loopback-only development entry point."""
import argparse


def main(argv=None):
    parser = argparse.ArgumentParser(prog="workflow-doctor-api")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    if not 0 <= args.port <= 65535:
        parser.error("port must be between 0 and 65535")
    import uvicorn
    uvicorn.run("workflow_doctor.api.app:app", host="127.0.0.1", port=args.port, workers=1,
                access_log=False, proxy_headers=False, limit_concurrency=4, backlog=4, timeout_keep_alive=5)


if __name__ == "__main__":
    main()
