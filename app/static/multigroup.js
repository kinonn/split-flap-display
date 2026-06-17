/** MultiGroup Display UI - Alpine.js component for multi-group ESP32 coordination.
 */

function multiGroupUI() {
  return {
    newMac: "",
    displayText: "HELLO ",
    slaveGroups: [],

    init() {
      console.log("[MG] Initializing...");
      this.fetchSlaves();
      setInterval.bind(null, function(){ self.pollAcks(); }, 5000);
    },

    async fetchSlaves() {
      try {
        var resp = await window.fetch("/api/slaves");
        if (!resp.ok) throw new Error("HTTP " + resp.status);
        var data = await resp.json();
        this.slaveGroups = (data.slaves || []).map(function(sg, idx){
          return { mac: sg.mac || ("00:00:00:00:00:" + String(idx).padStart(2,"0")),
                   modules: sg.modules ? sg.modules : 1, acked: false, _lastAck: Date.now(), idx: idx };
        });
        console.log("[MG] Loaded", this.slaveGroups.length, "slave(s)");
      } catch (err) {
        if (this.slaveGroups.length === 0) {
          this.slaveGroups = [{mac:"NO-SLAVES",modules:1,acked:false,_lastAck:Date.now(),idx:0}];
        }
      }
    },

    async broadcast() {
      var self = this;
      var text = this.displayText.trim();
      if (!text) { alert("Enter some text first!"); return; }
      try {
        console.log("[MG] Broadcasting to groups:", text, this.slaveGroups.length);
        var resp = await fetch("/api/display", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({text: text, mode: "multi_group"})
        });
        if (!resp.ok) throw new Error("HTTP " + resp.status);
        console.log("[MG] Broadcast sent OK");
        this.slaveGroups.forEach(function(g){ g.acked = false; });
      } catch (err) {
        console.error("[MG] Broadcast failed:", err.message);
        fetch("/api/display", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({text:text,mode:"single"})});
      }
    },

    async clearDisplay() {
      try {
        await fetch("/api/commands", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({cmd:"clear"})});
        this.displayText = "";
        console.log("[MG] Display cleared");
      } catch (err) {
        console.warn("[MG] Clear failed:", err.message);
      }
    },

    async pollAcks() {
      try {
        var resp = await fetch("/api/slaves");
        if (!resp.ok) throw new Error("HTTP " + resp.status);
        var data = await resp.json();
        var slaves = data.slaves || [];
        this.slaveGroups.forEach(function(g, idx){
          if (idx < slaves.length && slaves[idx] && slaves[idx].ack_sent) { g.acked=true; g._lastAck=Date.now(); }
        });
      } catch (err) {
        console.warn("[MG] Poll ACKs failed:", err.message);
      }
    },

    async confirmAck(mac) {
      try {
        var resp = await fetch("/api/confirm/" + mac, {method:"POST",headers:{"Content-Type":"application/json"}});
        if (!resp.ok) throw new Error("HTTP " + resp.status);
        console.log("[MG] Confirmed ACK for:", mac);
        var g = this.slaveGroups.find(function(x){ return x.mac === mac; });
        if (g) { g.acked=true; g._lastAck=Date.now(); }
      } catch (err) {
        console.warn("[MG] Confirm failed:", err.message);
      }
    },

    async addSlave() {
      var self = this;
      var mac = this.newMac.trim().toUpperCase();
      if (!mac || mac.length < 17) { alert("Enter valid MAC e.g. AA:BB:CC:DD:EE:FF"); return; }
      try {
        var resp = await fetch("/api/slaves", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({mac: mac, modules: 1})});
        if (!resp.ok) throw new Error("HTTP " + resp.status);
        console.log("[MG] Added slave:", mac);
        this.newMac = "";
        await this.fetchSlaves();
      } catch (err) {
        console.warn("[MG] Add failed:", err.message);
      }
    },

    async clearSlaves() {
      if (!confirm("Delete ALL registered slave groups?")) return;
      try {
        var resp = await fetch("/api/slaves", {method:"DELETE",headers:{"Content-Type":"application/json"},body:JSON.stringify({index:-1})});
        if (!resp.ok) throw new Error("HTTP " + resp.status);
        console.log("[MG] All slaves cleared");
        await this.fetchSlaves();
      } catch (err) {
        console.warn("[MG] Clear failed:", err.message);
      }
    }
  };
}
