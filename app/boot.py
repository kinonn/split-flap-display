from settings import Settings
import wifi_manager


try:
    wifi_manager.configure(Settings())
except Exception as exc:
    print("Boot Wi-Fi setup failed:", exc)
