try:
    import uasyncio as asyncio
except ImportError:
    import asyncio

import time

from controller import DisplayController
from display import SplitFlapDisplay
from mqtt_client import SplitFlapMqtt
from settings import Settings
from web_app import create_app
import wifi_manager


def test_display():
    settings = Settings()
    print("Testing display with settings:", settings.__dict__)
    display = SplitFlapDisplay(settings)
    display.init()
    
    display.home()
    display.test_all()
    # print("test")
    # display.home_to_string("123456")
    time.sleep_ms(250)
    display.write_string("#japan!")


async def main():
    settings = Settings()
    if not wifi_manager.state.get("configured"):
        wifi_manager.configure(settings)

    display = SplitFlapDisplay(settings)
    display.init()

    mqtt = SplitFlapMqtt(settings)
    mqtt.set_display(display)
    display.set_mqtt(mqtt)

    connected = wifi_manager.is_connected()
    if connected:
        mqtt.setup()
        display.home_to_string("OK")
        time.sleep_ms(250)
        display.write_string("")
    else:
        display.home_to_string("")
        if display.num_modules == 8:
            display.write_string("Wifi Err")
        else:
            display.write_char("X")

    controller = DisplayController(settings, display, mqtt)
    app = create_app(settings, controller, mqtt)

    asyncio.create_task(app.start_server(host="0.0.0.0", port=80, debug=False))
    await controller.run()


test_display()

# try:
#     asyncio.run(main())
# finally:
#     try:
#         asyncio.new_event_loop()
#     except AttributeError:
#         pass