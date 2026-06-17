# Split-flap display main boot entry point with multi-group support.
try:
    import uasyncio as asyncio
except ImportError:
    import asyncio

import time
from controller import DisplayController
try:
    from multigroup_controller import MultiGroupDisplayController
except ImportError:
    MultiGroupDisplayController = None
from display import SplitFlapDisplay
from mqtt_client import SplitFlapMqtt
from settings import Settings
from web_app import create_app
import wifi_manager


def _test_display():
    settings = Settings()
    print("Settings:", str(settings.__dict__))
    display = SplitFlapDisplay(settings)
    display.init()     
    display.home()
    display.test_all()


async def main():
    settings = Settings()
    if not wifi_manager.state.get("configured"):
        try:
            import wifi_manager as wm
            wm.configure(settings)
        except Exception:
            pass

    display = SplitFlapDisplay(settings)
    display.init()

    mqtt = SplitFlapMqtt(settings)
    mqtt.set_display(display)
    display.set_mqtt(mqtt)

    connected = wifi_manager.is_connected()
    if connected:
        try:
            mqtt.setup()
            display.home_to_string("OK")
            time.sleep_ms(250)
            display.write_string("")
        except Exception as exc:
            print("[Boot] MQTT setup failed:", str(exc))
    else:
        display.home_to_string("")
        if display.num_modules == 8:
            display.write_string("Wifi Err")
        else:
            display.write_char("X")

    controller = DisplayController(settings, display, mqtt)

    # Wire in multi-group controller if slaves are configured
    mg_ctrl = None
    try:
        import settings as SettingsClass
        slaves_cfg = list(settings.get_list("slaves", default=[]))
        if len(slaves_cfg) > 0 and MultiGroupDisplayController is not None:
            mg_ctrl = MultiGroupDisplayController(
                display=display, settings=settings
            )
            mg_ctrl.set_group_config(slaves_cfg)
            controller.mg_ctrl = mg_ctrl   # wire it into the main controller
            print("[Boot] Multi-group mode:", len(slaves_cfg), "groups")
        else:
            print("[Boot] Single-group mode (no slaves configured)")
    except Exception as exc:
        print("[Boot] MultiGroup init failed:", str(exc))

    app = create_app(settings, controller, mqtt)

    asyncio.create_task(
        app.start_server(host="0.0.0.0", port=80, debug=False)
    )
    await controller.run()


# _test_display()

try:
    asyncio.run(main())
finally:
    try:
        print("[Boot] Exiting main loop")
    except AttributeError:
        pass
