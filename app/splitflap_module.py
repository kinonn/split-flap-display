import time

STANDARD_CHARS = " ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"  # 37 chars set
EXTENDED_CHARS = " ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789':?!.-/$@#%"  # 48 chars set
CHARSETS = {
    len(STANDARD_CHARS): STANDARD_CHARS,
    len(EXTENDED_CHARS): EXTENDED_CHARS,
}

INIT_STATE = 0b1111111111100001
STEP_STATES = (
    0b1111111111100111,
    0b1111111111110011,
    0b1111111111111001,
    0b1111111111101101,
)
INIT_PAYLOAD = bytes((INIT_STATE & 0xFF, (INIT_STATE >> 8) & 0xFF))
STEP_PAYLOADS = tuple(bytes((state & 0xFF, (state >> 8) & 0xFF)) for state in STEP_STATES)
HALL_EFFECT_PIN = const(15)
HALL_EFFECT_ACTIVE_LOW = True


class SplitFlapModule:
    def __init__(
        self,
        address=0,
        steps_per_rotation=2048,
        step_offset=0,
        magnet_position=615,  # 730 for 37 chars, 615 for 48 chars
        charset_size=48,
        i2c=None,
    ):
        self.address = address
        self.steps_per_rotation = steps_per_rotation
        self.position = 0
        self.step_number = 0
        self.magnet_position = magnet_position + step_offset
        self.i2c = i2c
        self.has_errored = False

        self.chars = CHARSETS.get(charset_size, EXTENDED_CHARS)
        self.num_chars = len(self.chars)
        self.char_positions = []

    def attach_i2c(self, i2c):
        self.i2c = i2c

    @micropython.native
    def init(self):
        self.char_positions = [
            (i * self.steps_per_rotation + self.num_chars // 2) // self.num_chars
            for i in range(self.num_chars)
        ]

        self.write_io(INIT_STATE)
        self.stop()

        for _ in range(4):
            time.sleep_ms(100)
            self.step()

        time.sleep_ms(100)
        self.stop()

    @micropython.native
    def get_char_position(self, char):
        if not char:
            return 0

        char = str(char)[0].upper()
        try:
            return self.char_positions[self.chars.index(char)]
        except ValueError:
            return 0

    def stop(self):
        self.write_payload(INIT_PAYLOAD)

    @micropython.native
    def start(self):
        hold_step_number = (self.step_number + 3) & 3
        self.write_payload(STEP_PAYLOADS[hold_step_number])

    @micropython.native
    def step(self, update_position=True):
        self.write_payload(STEP_PAYLOADS[self.step_number])
        if update_position:
            position = self.position + 1
            if position >= self.steps_per_rotation:
                position = 0
            self.position = position
            self.step_number = (self.step_number + 1) & 3

    @micropython.native
    def read_hall_effect_sensor(self) -> bool:
        if self.has_errored or self.i2c is None:
            return False

        try:
            data = self.i2c.readfrom(self.address, 2)
        except Exception as exc:
            self._record_error("read", exc)
            return False

        if len(data) != 2:
            return False

        input_state = data[0] | (data[1] << 8)
        sensor_high = (input_state & (1 << HALL_EFFECT_PIN)) != 0
        return not sensor_high if HALL_EFFECT_ACTIVE_LOW else sensor_high

    @micropython.viper
    def magnet_detected(self):
        self.position = self.magnet_position % self.steps_per_rotation

    @micropython.viper
    def write_io(self, data: int):
        payload = bytes((data & 0xFF, (data >> 8) & 0xFF))
        self.write_payload(payload)

    @micropython.native
    def write_payload(self, payload):
        if self.i2c is None:
            return

        try:
            self.i2c.writeto(self.address, payload)
        except Exception as exc:
            self._record_error("write", exc)

    @micropython.native
    def _record_error(self, action, exc):
        if self.has_errored:
            return
        self.has_errored = True
        print("I2C %s failed for module 0x%02x:" % (action, self.address), exc)
