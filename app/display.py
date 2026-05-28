try:
    from machine import I2C, Pin, idle
except ImportError:
    I2C = None
    Pin = None

    def idle():
        pass

import random
import time

from splitflap_module import EXTENDED_CHARS, SplitFlapModule


MAX_MODULES = const(8)
MAX_RPM = const(25)
MIN_RPM = const(2)
IDLE_INTERVAL_US = const(50000)
START_STOP_DELAY_MS = const(200)


class SplitFlapDisplay:
    def __init__(self, settings):
        self.settings = settings
        self.modules = []
        self.i2c = None
        self.mqtt = None

        self.num_modules: int = 0
        self.steps_per_rotation: int = 2048
        self.max_velocity: int = MAX_RPM
        self.charset_size: int = 48

    @micropython.native
    def init(self):
        if I2C is None or Pin is None:
            raise RuntimeError("machine.I2C is required on the target board")

        self.num_modules = _clamp(self.settings.get_int("moduleCount"), 1, MAX_MODULES)
        self.steps_per_rotation = self.settings.get_int("stepsPerRot")
        display_offset = self.settings.get_int("displayOffset")
        magnet_position = self.settings.get_int("magnetPosition")
        self.max_velocity = self.settings.get_int("maxVel")
        self.charset_size = self.settings.get_int("charset")

        addresses = self.settings.get_int_vector(
            "moduleAddresses", self.num_modules, fill=0x20
        )
        offsets = self.settings.get_int_vector("moduleOffsets", self.num_modules, fill=0)

        sda_pin = self.settings.get_int("sdaPin")
        scl_pin = self.settings.get_int("sclPin")
        self.i2c = I2C(0, sda=Pin(sda_pin), scl=Pin(scl_pin), freq=400000)

        self.modules = []
        for index in range(self.num_modules):
            module = SplitFlapModule(
                address=addresses[index],
                steps_per_rotation=self.steps_per_rotation,
                step_offset=offsets[index] + display_offset,
                magnet_position=magnet_position,
                charset_size=self.charset_size,
                i2c=self.i2c,
            )
            module.init()
            self.modules.append(module)

        print("Split-flap modules:", self.num_modules)
        print("Module offsets:", offsets)
        print("Magnet position:", magnet_position)

    def set_mqtt(self, mqtt):
        self.mqtt = mqtt

    # @micropython.native
    def write_string(self, text, speed=MAX_RPM, centering=True):
        display_text = self._fit_text(text, centering)
        targets = []
        for index, char in enumerate(display_text):
            targets.append(self.modules[index].get_char_position(char))

        self.move_to(targets, speed)

        if self.mqtt and self.mqtt.is_connected():
            self.mqtt.publish_state(display_text)

    # @micropython.native
    def write_char(self, char, speed=MAX_RPM):
        targets = [module.get_char_position(char) for module in self.modules]
        self.move_to(targets, speed)

    # @micropython.native
    def home(self, speed=MAX_RPM):
        print("Homing")
        targets = [
            (module.position - 1 + self.steps_per_rotation) % self.steps_per_rotation
            for module in self.modules
        ]
        # Keep motors energized (release_motors=False) so flaps don't physically
        # slip between the calibration pass and the final positioning move.
        self.move_to(targets, speed, release_motors=False)

        targets = [module.get_char_position(" ") for module in self.modules]
        self.move_to(targets, speed, release_motors=True)

    # @micropython.native
    def home_to_string(self, text, speed=MAX_RPM, centering=True):
        print("Homing")
        targets = [
            (module.position - 1 + self.steps_per_rotation) % self.steps_per_rotation
            for module in self.modules
        ]
        self.move_to(targets, speed, release_motors=False)
        print("Moving to text:", text)
        self.write_string(text, speed, centering)

    # @micropython.native
    def home_to_char(self, char, speed=MAX_RPM):
        print("Homing")
        targets = [
            (module.position - 1 + self.steps_per_rotation) % self.steps_per_rotation
            for module in self.modules
        ]
        self.move_to(targets, speed, release_motors=False)
        self.write_char(char, speed)

    # @micropython.native
    def move_to(self, target_positions: list[int], speed: int = MAX_RPM, release_motors: bool = True) -> None:
        modules = self.modules
        if not modules:
            return

        num_modules: int = self.num_modules
        steps_per_rotation = self.steps_per_rotation
        speed = _clamp(speed, MIN_RPM, self.max_velocity)
        steps_per_second = (speed / 60.0) * steps_per_rotation
        time_per_step_us = max(1, int(1000000.0 / steps_per_second))
        
        print("Moving to targets:", target_positions)

        # print(
        #     f"Moving to targets {target_positions} at {speed} RPM "
        #     f"({time_per_step_us} us/step), steps_per_second={steps_per_second:.2f}"
        # )

        active_modules = []
        active_steps = []
        active_sensor_reads = []
        active_magnet_resets = []
        active_sensor_state = []
        active_targets = []
        active_step_budget = []

        targets_len = len(target_positions)
        max_step = steps_per_rotation - 1
        steps_forward = _steps_forward

        for index in range(num_modules):
            module = modules[index]
            if index < targets_len:
                target_step = _clamp(int(target_positions[index]), 0, max_step)
            else:
                target_step = module.position

            steps = steps_forward(module.position, target_step, steps_per_rotation)
            if steps > 0:
                active_modules.append(module)
                active_steps.append(module.step)
                active_sensor_reads.append(module.read_hall_effect_sensor)
                active_magnet_resets.append(module.magnet_detected)
                active_sensor_state.append(module.read_hall_effect_sensor())
                active_targets.append(target_step)
                active_step_budget.append(steps + steps_per_rotation)
            else:
                module.stop()

        active_count = len(active_modules)
        if active_count == 0:
            if release_motors:
                self.stop_motors()
            else:
                self.start_motors()
            return

        for index in range(active_count):
            active_modules[index].start()

        time.sleep_ms(START_STOP_DELAY_MS)

        ticks_us = time.ticks_us
        ticks_diff = time.ticks_diff
        ticks_add = time.ticks_add
        sleep_ms = time.sleep_ms
        now = ticks_us()
        next_step_time = now
        last_idle = now

        while active_count > 0:
            now = ticks_us()
            if ticks_diff(now, next_step_time) < 0:
                if ticks_diff(now, last_idle) > IDLE_INTERVAL_US:
                    idle()
                    last_idle = now
                continue

            next_step_time = ticks_add(now, time_per_step_us)

            index = 0
            while index < active_count:
                module = active_modules[index]
                active_steps[index]()
                step_budget = active_step_budget[index] - 1

                is_sensor_active = active_sensor_reads[index]()
                if is_sensor_active and not active_sensor_state[index]:
                    # Capture how many steps remain to the target BEFORE the
                    # position is snapped to the calibrated magnet position.
                    remaining_before = steps_forward(
                        module.position,
                        active_targets[index],
                        steps_per_rotation,
                    )
                    active_magnet_resets[index]()
                    # Rebase the target from the new calibrated position so
                    # steps_left keeps counting toward the same logical
                    # destination.  Without this, the stale uncalibrated target
                    # causes an incorrect steps_left and the motor stops at the
                    # wrong position (or keeps running a full extra rotation).
                    active_targets[index] = (
                        module.position + remaining_before
                    ) % steps_per_rotation
                active_sensor_state[index] = is_sensor_active
                steps_left = steps_forward(
                    module.position,
                    active_targets[index],
                    steps_per_rotation,
                )

                if steps_left <= 0:
                    active_count -= 1
                    if index != active_count:
                        active_modules[index] = active_modules[active_count]
                        active_steps[index] = active_steps[active_count]
                        active_sensor_reads[index] = active_sensor_reads[active_count]
                        active_magnet_resets[index] = active_magnet_resets[active_count]
                        active_sensor_state[index] = active_sensor_state[active_count]
                        active_targets[index] = active_targets[active_count]
                        active_step_budget[index] = active_step_budget[active_count]
                    continue

                if step_budget <= 0:
                    print(
                        "Move step limit reached for module 0x%02x"
                        % getattr(module, "address", index)
                    )
                    active_count -= 1
                    if index != active_count:
                        active_modules[index] = active_modules[active_count]
                        active_steps[index] = active_steps[active_count]
                        active_sensor_reads[index] = active_sensor_reads[active_count]
                        active_magnet_resets[index] = active_magnet_resets[active_count]
                        active_sensor_state[index] = active_sensor_state[active_count]
                        active_targets[index] = active_targets[active_count]
                        active_step_budget[index] = active_step_budget[active_count]
                    continue

                active_step_budget[index] = step_budget
                index += 1

        if release_motors:
            sleep_ms(START_STOP_DELAY_MS)
            self.stop_motors()

    def test_all(self, speed=MAX_RPM):
        print("Testing all characters")
        chars = self.modules[0].chars if self.modules else EXTENDED_CHARS
        for char in chars:
            self.write_char(char, speed)
            time.sleep_ms(500)

    def test_count(self):
        for number in range(10 ** self.num_modules):
            text = ("%0*d" % (self.num_modules, number))[-self.num_modules :]
            self.write_string(text, centering=False)
            time.sleep_ms(250)

    def test_random(self, speed=MAX_RPM):
        chars = self.modules[0].chars if self.modules else EXTENDED_CHARS
        text = "".join(
            chars[random.randrange(0, len(chars))]
            for _ in range(self.num_modules)
        )
        print("Target:", text)
        self.write_string(text, speed, centering=False)

    # @micropython.native
    def start_motors(self):
        for module in self.modules:
            module.start()

    # @micropython.native
    def stop_motors(self):
        for module in self.modules:
            module.stop()

    @micropython.native
    def _fit_text(self, text, centering):
        display_text = str(text or "")[: self.num_modules]
        padding = self.num_modules - len(display_text)

        if padding <= 0:
            return display_text

        if centering:
            left = padding // 2
            right = padding - left
            return (" " * left) + display_text + (" " * right)

        return display_text + (" " * padding)

@micropython.viper
def _clamp(value: int, minimum: int, maximum: int) -> int:
    if value < minimum:
        return minimum
    if value > maximum:
        return maximum
    return value

@micropython.viper
def _steps_forward(current_step: int, target_step: int, steps_per_rotation: int) -> int:
    if steps_per_rotation <= 0:
        return 0

    current_step %= steps_per_rotation
    target_step %= steps_per_rotation
    if current_step < 0:
        current_step += steps_per_rotation
    if target_step < 0:
        target_step += steps_per_rotation

    steps = target_step - current_step
    if steps < 0:
        steps += steps_per_rotation
    return steps
