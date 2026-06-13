import utime
from micropython import const

# Pre-calculate constant step states for fast lookup
_STEP_STATES = (
    const(0b1111111111100111), # Step 0
    const(0b1111111111110011), # Step 1
    const(0b1111111111111001), # Step 2
    const(0b1111111111101101)  # Step 3
)

_INIT_STATE = const(0b1111111111100001)

class SplitFlapModule:
    STANDARD_CHARS = (' ', 'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9')
    EXTENDED_CHARS = (' ', 'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '\'', ':', '?', '!', '.', '-', '/', '$', '@', '#', '%')

    def __init__(self, i2c, address, steps_per_rot, step_offset, magnet_pos, charset_size):
        self.i2c = i2c
        self.address = address
        self.position = 0
        self.step_number = 0
        self.steps_per_rot = steps_per_rot
        self.charset_size = charset_size
        self.has_errored = False
        
        self.magnet_position = magnet_pos + step_offset
        
        self.num_chars = 0
        if charset_size == 48:
            self.chars = self.EXTENDED_CHARS
            self.num_chars = 48
        else:
            self.chars = self.STANDARD_CHARS
            self.num_chars = 37

        # self.char_positions = [0] * self.num_chars
        # step_size = self.steps_per_rot / self.num_chars
        # current_position = 0.0
        # for i in range(self.num_chars):
        #     self.char_positions[i] = int(current_position)
        #     current_position += step_size

        self.char_positions = [
            round((i * self.steps_per_rot + self.num_chars / 2) / self.num_chars) for i in range(self.num_chars)
        ]
        
        
        # Pre-allocate buffer for I2C writes to avoid GC allocation during stepping
        self._buf = bytearray(2)

    @micropython.native
    def write_io(self, data: int):
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
        self.write_io(_INIT_STATE)
        
        self.stop()
        
        init_delay_ms = 100
        utime.sleep_ms(init_delay_ms)
        self.step()
        utime.sleep_ms(init_delay_ms)
        self.step()
        utime.sleep_ms(init_delay_ms)
        self.step()
        utime.sleep_ms(init_delay_ms)
        self.step()
        utime.sleep_ms(init_delay_ms)
        
        self.stop()

    def get_char_position(self, input_char):
        input_char = input_char.upper()
        try:
            index = self.chars.index(input_char)
            return self.char_positions[index]
        except ValueError:
            return 0 # Character not found, return blank

    @micropython.native
    def stop(self):
        self.write_io(_INIT_STATE)

    @micropython.native
    def start(self):
        self.step_number = (self.step_number + 3) % 4
        self.step(update_position=False)

    @micropython.native
    def step(self, update_position: bool = True):
        # Look up state directly from pre-calculated tuple using step_number
        self.write_io(_STEP_STATES[self.step_number])
        
        if update_position:
            # self.position = (self.position + 1) % self.steps_per_rot
            position = self.position + 1
            if position >= self.steps_per_rot:
                position = 0
            self.position = position
            
        # Bitwise AND 3 is equivalent to modulo 4 but faster
        self.step_number = (self.step_number + 1) & 3

    @micropython.native
    def read_hall_effect_sensor(self) -> bool:
        if self.has_errored:
            return False
            
        try:
            data = self.i2c.readfrom(self.address, 2)
            if len(data) == 2:
                input_state = data[0] | (data[1] << 8)
                return (input_state & (1 << 15)) != 0
        except OSError:
            pass
        return False

    @micropython.native
    def magnet_detected(self):
        self.position = self.magnet_position
        