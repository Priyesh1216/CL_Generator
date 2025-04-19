from chainlit.cli import run_chainlit
import os
import sys


def main():
    try:
        APP_ROOT = os.getcwd()
        app_dir = os.path.join(APP_ROOT, "app.py")
        run_chainlit(app_dir)

    except Exception as e:
        print(f"Command failed with return code: {str(e)}")


if __name__ == "__main__":
    sys.exit(main())
