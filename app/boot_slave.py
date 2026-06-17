# Slave group standalone boot for split-flap multi-group system.
# Runs on each slave ESP32 to receive and display master broadcasts.
import sys


def main():
    """Initialize slave-only hardware and start listening for broadcasts."""
    print("[Slave] Standalone slave group boot...")

    try:
        from slave_group import SlaveGroupManager
    except ImportError:
        sys.exit(1)

    try:
        from settings import Settings
    except ImportError:
        Settings = None

    if Settings:
        settings = Settings()
        print("[Slave] Configuration loaded, modules:",
              display_num_modules(settings))

        mg_ctrl = SlaveGroupManager(
            display=None,
            settings=settings,
            mode="slave"
        )
        print("[Slave] Manager created, broadcasting...")

    else:
        mg_ctrl = SlaveGroupManager(
            display=None,
            mode="slave_minimal"
        )
        print("[Slave] Minimal manager awaiting frames...")

    try:
        if hasattr(mg_ctrl, "start_slave_loop"):
            mg_ctrl.start_slave_loop()
        else:
            mg_ctrl.handle_input(b"", b"")
    except KeyboardInterrupt:
        return True

    except Exception as exc:
        print("[Slave] BOOT FAILED:", str(exc))
        import time, gc
        gc.collect()
        while True:
            try:
                time.sleep_ms(500)
            except Exception:
                break

    return False


def display_num_modules(settings):
    """Return the number of modules from settings."""
    try:
        return int(settings.modules_per_group or 8)
    except (AttributeError, ValueError):
        return 8


if __name__ == "__main__":
    status = main()
    sys.exit(0 if status else 1)
