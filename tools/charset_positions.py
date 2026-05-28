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

char_position_diffs = [
    (char_positions[(i + 1) % num_chars] - char_positions[i]) % steps_per_rotation
    for i in range(num_chars)
]

for char, pos, diff, precise in zip(
    EXTENDED_CHARS,
    char_positions,
    char_position_diffs,
    char_positions_precise,
):
    print(char, pos, diff, precise)

