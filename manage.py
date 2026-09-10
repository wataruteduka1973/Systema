import logging
import os
import re
import sys
import time
import webbrowser
from threading import Thread

import requests
from django.conf import settings

logger = logging.getLogger("server_logger")


def management_command_name(argv):
    if len(argv) < 2 or re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", argv[1]) is None:
        return "unknown"
    return argv[1]


def execute_management_command(executor, argv):
    command = management_command_name(argv)
    try:
        return executor(argv)
    except SystemExit as error:
        if error.code not in (None, 0):
            logger.error("management_command_failed command=%s failure=SystemExit", command)
        raise
    except BaseException as error:
        logger.error(
            "management_command_failed command=%s failure=%s",
            command,
            type(error).__name__,
        )
        raise


def check_server_and_open(port=8000, max_attempts=10, delay=1.0):
    """サーバーが起動するまで待機し、応答したらブラウザを開く"""
    attempt = 0
    while attempt < max_attempts:
        try:
            response = requests.get(f"http://127.0.0.1:{port}/taskle/", timeout=5)
            if response.status_code == 200:
                environment = "Debug" if settings.DEBUG else "Production"
                logger.info(
                    f"Server started successfully on port {port} in {environment} environment."
                )
                webbrowser.open_new(f"http://127.0.0.1:{port}/taskle/")
                break
        except requests.Timeout:
            logger.warning(f"Attempt {attempt + 1}: Timeout while connecting to server.")
        except requests.ConnectionError:
            logger.warning(f"Attempt {attempt + 1}: Connection refused. Server may not be ready.")
        except Exception as e:
            logger.warning(f"Attempt {attempt + 1}: Unexpected error: {str(e)}")
        attempt += 1
        time.sleep(delay)
    else:
        logger.warning(
            f"Could not connect to server after {max_attempts} attempts. Please open http://127.0.0.1:{port}/taskle/ manually."
        )


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "System_Config.settings")

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc

    if "runserver" in sys.argv:
        port = 8000  # デフォルトポート
        for arg in sys.argv:
            if arg.startswith("0.0.0.0:") or arg.startswith("127.0.0.1:"):
                port = int(arg.split(":")[1])
        if (
            port == 8000
            and not any(arg.startswith("open") for arg in sys.argv)
            and os.environ.get("RUN_MAIN") != "true"
            and os.environ.get("DJANGO_RUN_MAIN") != "true"
        ):
            # サーバー起動後にブラウザを開くスレッドを起動
            thread = Thread(target=check_server_and_open, args=(port,), daemon=True)
            thread.start()

    execute_management_command(execute_from_command_line, sys.argv)


if __name__ == "__main__":
    main()
