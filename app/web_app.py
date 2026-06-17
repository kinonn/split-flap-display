"""Split-flap display web API built on microdot framework."""


def create_app(settings, controller, mqtt):
    from microdot import Microdot
    app = Microdot()

    @app.before_request
    def collect_gc(request):
        import gc
        gc.collect()

    @app.get("/")
    async def root(request):
        return Microdot.redirect("/static/index.html")

    @app.post("/api/display")
    async def api_display(request):
        try:
            payload = request.json or {}
            text = str(payload.get("text", ""))
            mode = str(payload.get("mode", "single"))
            if text == "" or mode == "clear":
                controller.display.write_string("")
                settings.set("text", "")
                return Microdot(text='{"ok":true,"type":"cleared"}')
            if mode == "multi_group":
                mg = getattr(controller, "mg_ctrl", None)
                if mg is not None:
                    ack_ids = mg.broadcast_text(text)
                    settings.set("text", text[:48])
                    return Microdot(
                        text='{"ok":true,"type":"multi_group","acks":["'
                        + ','.join(str(a) for a in ack_ids) + '"]}'
                    )
            controller.set_single_text(text)
            settings.set("text", text)
            return Microdot(text='{"ok":true,"type":"single"}')
        except Exception as exc:
            print("[WebAPI] Display error:", str(exc))
            return Microdot(
                text='{"error":"' + str(exc).replace('"', "'") + '"}',
            )

    @app.post("/api/slaves")
    async def api_add_slave(request):
        try:
            payload = request.json or {}
            mac = str(payload.get("mac", ""))
            modules = int(str(payload.get("modules", 1)))
            if not mac or len(mac) != 17:
                return Microdot(text='{"error":"bad_mac"}')
            slaves_list = settings.get_list("slaves", default=[])
            entry = {"mac": mac, "modules": modules}
            slaves_list.append(entry)
            settings.set("slaves", slaves_list)
            print("[WebAPI] Added slave:", mac)
            return Microdot(
                text='{"ok":true,"count":' + str(len(slaves_list)) + '}'
            )
        except Exception as exc:
            return Microdot(text='{"error":"' + str(exc).replace('"', "'") + '"}')

    @app.delete("/api/slaves")
    async def api_remove_slave(request):
        try:
            payload = request.json or {}
            idx = int(str(payload.get("index", -1)))
            slaves_list = settings.get_list("slaves", default=[])
            if 0 <= idx < len(slaves_list):
                del slaves_list[idx]
            else:
                slaves_list.clear()
            settings.set("slaves", slaves_list)
            print("[WebAPI] Cleared slaves:", str(len(slaves_list)))
            return Microdot(
                text='{"ok":true,"count":' + str(len(slaves_list)) + '}'
            )
        except Exception as exc:
            return Microdot(text='{"error":"' + str(exc).replace('"', "'") + '"}')

    @app.get("/api/slaves")
    async def api_get_slaves(request):
        slaves_list = settings.get_list("slaves", default=[])
        jstr = '{"ok":true,"slaves":[' + ",".join(
            '{"mac":"' + s["mac"] + '","modules":' + str(s["modules"]) + "}"
            for s in slaves_list
        ) + ']}'
        return Microdot(text=jstr)

    @app.post("/api/commands")
    async def api_commands(request):
        try:
            payload = request.json or {}
            action = str(payload.get("cmd", ""))
            if action == "home":
                controller.display.home()
                return Microdot(text='{"ok":true}')
            elif action == "clear":
                controller.display.write_string("")
                return Microdot(text='{"ok":true}')
            else:
                return Microdot(text='{"error":"unknown_cmd"}')
        except Exception as exc:
            print("[WebAPI] Cmd error:", str(exc))
            return Microdot(text='{"error":"' + str(exc) + '"}')

    @app.patch("/settings")
    async def patch_settings(request):
        try:
            payload = request.json or {}
            if not isinstance(payload, dict):
                return Microdot(text='{"error":"not_json"}')
            for key, value in payload.items():
                settings.set(key, value)
            print("[WebAPI] Settings patched:", str(len(payload)))
            return Microdot(text='{"ok":true}')
        except Exception as exc:
            print("[WebAPI] Patch error:", str(exc))
            return Microdot(text='{"error":"' + str(exc).replace('"', "'") + '"}')

    @app.get("/static/<file_path:path>")
    def serve_static(request, file_path):
        try:
            import microdot
            return microdot.send_from_directory(
                "static/", str(file_path)
            )
        except Exception as exc:
            print("[Static] Error:", str(exc))
            try:
                from microdot import send_from_directory
                return send_from_directory("static/", str(file_path))
            except Exception:
                return Microdot(text=str(exc), status_code=404)

    @app.get("/settings")
    async def settings_page(request):
        try:
            from microdot import send_from_directory
            return send_from_directory("static/", "settings.html")
        except Exception as exc:
            print("[Static] Settings error:", str(exc))
            return Microdot(text=str(exc), status_code=404)

    return app
