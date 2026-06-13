EXTENDED_CHARS = " ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789':?!.-/$@#%"  # 48 chars set
num_chars = len(EXTENDED_CHARS)
steps_per_rotation = 2048

char_positions = [
    (i * steps_per_rotation + num_chars // 2) // num_chars
    for i in range(num_chars)
]

char_positions_precise = [
    round((i * steps_per_rotation + num_chars / 2) / num_chars, 2)
    for i in range(num_chars)
]

char_positions_3 = [
    round((i * steps_per_rotation + num_chars / 2) / num_chars)
    for i in range(num_chars)
]

char_position_diffs = [
    (char_positions[(i + 1) % num_chars] - char_positions[i]) % steps_per_rotation
    for i in range(num_chars)
]

char_position_3_diffs = [
    (char_positions_3[(i + 1) % num_chars] - char_positions_3[i]) % steps_per_rotation
    for i in range(num_chars)
]

def get_char_position_byint():
    step_size = steps_per_rotation / num_chars
    current_position = 0.0
    char_positions = [0] * num_chars
    for i in range(num_chars):
        char_positions[i] = int(current_position)
        current_position += step_size
    return char_positions

char_positions_2 = get_char_position_byint()

for char, pos, diff, pos_3, diff3, precise in zip(
    EXTENDED_CHARS,
    char_positions,
    char_position_diffs,
    char_positions_3,
    char_position_3_diffs,
    char_positions_precise,
):
    print(char, pos, diff, pos_3, diff3, precise)

