import utime
from micropython import const

# Pre-calculate constant step states for fast lookup
_STEP_STATES = (
    const(0b1111111111100111),       # Step 0
    const(0b1111111111110011),       # Step 1
    const(0b1111111111111001),       # Step 2
    const(0b1111111111101101)        # Step 3
)

# _INIT_STATE: idle/stop bit pattern for module outputs
_INIT_STATE = const(0b1111111111100001)
HALL_MASK = const(1 << 15)

class SplitFlapModule:
    STANDARD_CHARS = (' ', 'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9')
    EXTENDED_CHARS = (' ', 'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '\'', ':', '?', '!', '.', '-', '/', '$', '@', '#', '%')

    def __init__(self, i2c, address, steps_per_rot, step_offset, magnet_pos, charset_size):
        self.i2c = i2c
        self.address = address
        self.position = 0
        self.step_number = 0
        self.steps_per_rot = steps_per_rot
        self._err_count = 0
        self._err_reset_ticks_ms = 0
        I2C_ERR_MAX_COUNT = const(3)
        self._err_max_count = I2C_ERR_MAX_COUNT
        I2C_ERR_TIMEOUT_MS = const(10000)
        self._err_timeout_ms = I2C_ERR_TIMEOUT_MS

        self.magnet_position = magnet_pos + step_offset

        self.num_chars = 0
        if charset_size == 48:
            self.chars = self.EXTENDED_CHARS
            self.num_chars = 48
        else:
            self.chars = self.STANDARD_CHARS
            self.num_chars = 37

        self.char_positions = [
            round((i * self.steps_per_rot + self.num_chars / 2) / self.num_chars) for i in range(self.num_chars)
        ]

        # Build O(1) lookup from character -> step position
        self._char_to_pos = {c: p for c, p in zip(self.chars, self.char_positions)}

        # Pre-allocate buffer for I2C writes to avoid GC allocation during stepping
        self._buf = bytearray(2)

    @micropython.native
    def write_io(self, data: int):
        """Write step state to the module via I2C."""
        # Cache locals
        buf = self._buf
        buf[0] = data & 0xFF
        buf[1] = (data >> 8) & 0xFF
        try:
            self.i2c.writeto(self.address, buf)
        except OSError as e:
            if not self.has_errored:
                self.has_errored = True
                print("Error writing data to module", self.address, "error code:", e)

    def init(self):
        """Initialize module: set idle, then pulse steps for homing."""
        self.write_io(_INIT_STATE)

        self.stop()

        init_delay_ms = 100
        utime.sleep_ms(init_delay_ms)
        for _ in range(4):
            self.step()
            utime.sleep_ms(init_delay_ms)

        self.stop()

    def get_char_position(self, input_char):
        """Return step index for a character, or 0 if not found."""
        if not isinstance(input_char, str):
            return 0
        return self._char_to_pos.get(input_char.upper(), 0)

    @micropython.native
    def stop(self):
        """Stop the motor by sending the idle state."""
        self.write_io(_INIT_STATE)

    @micropython.native
    def start(self):
        """Advance step phase and begin rotation (no position update)."""
        self.step_number = (self.step_number + 3) % 4
        self.step(update_position=False)

    @micropython.native
    def step(self, update_position: bool = True):
        """Execute one step using precomputed step states."""
        # Look up state directly from pre-calculated tuple using step_number
        self.write_io(_STEP_STATES[self.step_number])

        if update_position:
            self.position = (self.position + 1) % self.steps_per_rot

        # Bitwise AND 3 is equivalent to modulo 4 but faster
        self.step_number = (self.step_number + 1) & 3

    @micropython.native
    def read_hall_effect_sensor(self) -> bool:
        """Read Hall-effect sensor. Returns False on I2C/read error."""
        # Check if we are blocked by I2C errors, with timeout-based recovery
        if self._err_count >= self._err_max_count:
            elapsed = utime.ticks_diff(utime.ticks_ms(), self._err_reset_ticks_ms)
            if 0 < elapsed < self._err_timeout_ms:
                return False

        try:
            data = self.i2c.readfrom(self.address, 2)
            if self._err_count > 0 and len(data) == 2:
                self._err_count = 0
            if len(data) == 2:
                input_state = data[0] | (data[1] << 8)
                return (input_state & HALL_MASK) != 0
        except OSError:
            pass
        return False

    @micropython.native
    def magnet_detected(self):
        """Reset position to magnet reference and clear error state."""
        self.position = self.magnet_position
        self._err_count = 0
        self._err_reset_ticks_ms = 0
        I2C_ERR_MAX_COUNT = const(3)
        self._err_max_count = I2C_ERR_MAX_COUNT
        I2C_ERR_TIMEOUT_MS = const(10000)
        self._err_timeout_ms = I2C_ERR_TIMEOUT_MS
