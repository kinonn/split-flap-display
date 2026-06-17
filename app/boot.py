import time as _time
from settings import Settings
def start_wifi():
    try:
        import wifi_manager
        wifi_manager.configure(Settings())
        return True
    except Exception as exc:
        print("NoWifi:", str(exc))
        return False

def init_multigroup_mgr(settings_ref):
    try:
        slaves_cfg = list(settings_ref.get_list("slaves", default=[]))
        if not slaves_cfg:
            return None
        from multigroup_controller import MultiGroupDisplayController
        mg_ctrl = MultiGroupDisplayController(display=None, settings=settings_ref)
        mg_ctrl.set_group_config(slaves_cfg)
        print("[Boot] MultiGroup initialized:", len(slaves_cfg), "groups")
        return mg_ctrl
    except Exception as exc:
        print("[Boot] MultiGroup init failed:", str(exc))
        return None

def main():
    import gc; gc.collect()
    print("Booting split-flap display system...")
    mg_mgr = init_multigroup_mgr(Settings())
    started_wifi = start_wifi()
    if mg_mgr is None:
        print("[Boot] Running in SINGLE-GROUP mode")
        while True:
            _time.sleep_ms(1000)
            print("Single mode active (no slave groups configured)")
    else:
        print("[Boot] Running in MULTI-GROUP mode:", mg_mgr.num_groups, "groups")
        mg_ctrl = mg_mgr
        while True:
            _time.sleep_ms(1000)
            try:
                for i in range(mg_ctrl.num_groups):
                    pass  
            except Exception as exc:
                print("[Loop] Error:", str(exc))
    gc.collect()
    _time.sleep_ms(1000)

if __name__ == "__main__":
    main();
