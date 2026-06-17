# MultiGroupDisplayController - Manages multi-group split-flap via MQTT broadcast messages.
# Each group runs this controller which distributes text across all configured groups.

MODE_MULTIGROUP = 4


class MultiGroupDisplayController:
    def __init__(self, display, settings=None):
        self.display = display
        self.settings = settings
        self.num_groups = 0
        self.group_configs = []
        self.acks_pending = {}
        self.last_seq = 0

    def set_group_config(self, groups_info):
        self.num_groups = len(groups_info)
        for item in groups_info:
            mc = int(item.get("modules", 8))
            if mc < 1 or mc > 8:
                mc = 8
            cfg = {"mac": item.get("mac", "unknown"), "modules": mc}
            self.group_configs.append(cfg)

    def broadcast_text(self, text):
        if not self.group_configs:
            return []
        text = str(text)[:8 * self.num_groups]
        chars = list(text)
        total_chars = len(chars)
        seg_size = max(1, (total_chars + self.num_groups - 1) // self.num_groups)
        ack_ids = []
        frames_list = []
        for gid in range(self.num_groups):
            start = gid * seg_size
            end = min(start + seg_size, total_chars)
            if start < total_chars:
                seg_text = "".join(chars[start:end]).ljust(8)[:8]
            else:
                seg_text = "          "
            self.last_seq += 1
            sid = self.last_seq
            fdata = {
                 "cmd": "display",
                 "group_id": gid,
                 "data": seg_text,
                 "version": 1,
                 "seq_id": sid,
             }
            frames_list.append(fdata)
            ack_ids.append(sid)
            gs = set()
            self.acks_pending[sid] = {
                 "cmd": "multi_display",
                 "groups_ack": gs,
                 "total_groups": self.num_groups,
             }
        bc_data = {
             "seq_id": self.last_seq,
             "master_cmd": "multi_display",
             "num_groups": self.num_groups,
             "frames": frames_list,
         }
        for gid in range(self.num_groups):
            print("[MultiGroup] seq=%d group=%d frames=%d" % (sid, gid, len(frames_list)))
        return ack_ids

    def on_ack_received(self, mac_string, ack_dict):
        seq_id = ack_dict.get("seq_id", -1)
        group_id = ack_dict.get("group_id", 0)
        if not (isinstance(seq_id, int) and 0 < seq_id <= self.last_seq):
            return False
        entry = self.acks_pending.get(seq_id)
        if entry is None:
            return False
        try:
            gset = set(entry["groups_ack"])
        except Exception:
            gset = set()
        g_key = str(group_id)
        gset.add(g_key)
        count = len(gset)
        total = int(entry["total_groups"])
        print("[MultiGroup] ACK group %d seq %d: %d/%d" % (int(group_id), seq_id, count, total))
        if count >= total:
            del self.acks_pending[seq_id]
            return True
        return False

    def get_ack_status(self):
        out = {}
        for sid, entry in self.acks_pending.items():
            try:
                gs = set(entry.get("groups_ack", []))
            except Exception:
                gs = set()
            total = int(entry["total_groups"])
            out[str(sid)] = {
                 "ack_count": len(gs),
                 "total_groups": total,
                 "complete": len(gs) >= total,
             }
        return out

    def retransmit(self, seq_id):
        entry = self.acks_pending.get(seq_id)
        if entry is None:
            return []
        retransmitted = []
        for gid in range(int(entry.get("total_groups", 0))):
            key = str(gid)
            if key not in entry.get("groups_ack", set()):
                retransmitted.append(gid)
            else:
                retransmitted.append(0xFFFF)
        return retransmitted

    def clear_acks(self):
        self.acks_pending.clear()
