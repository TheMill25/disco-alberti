from flask import Flask, render_template, request, jsonify
import hashlib
import hmac
import unicodedata
import os

app = Flask(__name__)

ALPHABET = "ABCDEFGHIJKLMNÑOPQRSTUVWXYZ"
N = len(ALPHABET)


def mod(value, base=N):
    return ((value % base) + base) % base


def normalize_spanish(value):
    value = str(value).upper().replace("Ñ", "\uE000")
    value = unicodedata.normalize("NFD", value)
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    return value.replace("\uE000", "Ñ").replace("Ü", "U")


def clean_passphrase(value):
    letters = [ch for ch in normalize_spanish(value) if ch in ALPHABET]
    return "".join(letters) or "ALBERTI"


def clean_key(value):
    return "".join(dict.fromkeys(clean_passphrase(value)))


def make_keyed_alphabet(key):
    unique = clean_key(key)
    return unique + "".join(ch for ch in ALPHABET if ch not in unique)


def keyed_step(key, seed, letter_counter):
    message = f"ALBERTI|{seed}|{letter_counter}".encode("utf-8")
    digest = hmac.new(key.encode("utf-8"), message, hashlib.sha256).digest()
    return (int.from_bytes(digest[:4], "big") % (N - 1)) + 1


@app.get("/")
def index():
    return render_template("index.html", alphabet=ALPHABET)


@app.post("/api/transform")
def transform():
    data = request.get_json(silent=True) or {}
    message = data.get("message", "")
    operation = data.get("operation", "encrypt")
    key = clean_passphrase(data.get("key", "ALBERTI SECRETO"))
    seed = str(data.get("seed", "CRUV-2026")).strip() or "CRUV-2026"
    mode = data.get("mode", "fixed")
    fixed_disk = data.get("fixed_disk", "outer")
    direction = data.get("direction", "right")

    try:
        interval = max(1, min(500, int(data.get("interval", 5))))
        step = max(1, min(N - 1, int(data.get("step", 3))))
        outer_start = data.get("outer_start", "A")
        inner_start = data.get("inner_start", "A")
        if outer_start not in ALPHABET or inner_start not in ALPHABET:
            raise ValueError("Selecciona letras válidas para los puntos iniciales.")
    except (TypeError, ValueError) as exc:
        return jsonify(error=str(exc)), 400

    inner = make_keyed_alphabet(key)
    outer_rotation = mod(-ALPHABET.index(outer_start))
    inner_rotation = mod(-inner.index(inner_start))
    base_offset = mod(outer_rotation - inner_rotation)
    moving_disk = "inner" if fixed_disk == "outer" else "outer"
    direction_sign = 1 if direction == "right" else -1
    disk_factor = 1 if moving_disk == "outer" else -1

    decrypt = operation == "decrypt"
    offset = base_offset
    counter = 0
    output = []
    trace = []

    for char in normalize_spanish(message):
        if char not in ALPHABET:
            output.append(char)
            continue

        if decrypt:
            cipher_index = inner.index(char)
            plain_index = mod(cipher_index - offset)
            transformed = ALPHABET[plain_index]
            outer_letter, inner_letter = transformed, char
        else:
            plain_index = ALPHABET.index(char)
            cipher_index = mod(plain_index + offset)
            transformed = inner[cipher_index]
            outer_letter, inner_letter = char, transformed

        trace.append({
            "number": counter + 1,
            "input": char,
            "output": transformed,
            "outer": outer_letter,
            "inner": inner_letter,
            "offset": offset,
            "operation": "DESCIFRADO" if decrypt else "CIFRADO"
        })
        output.append(transformed)
        counter += 1

        if mode == "periodic" and counter % interval == 0:
            offset = mod(offset + direction_sign * disk_factor * step)
        elif mode == "keyed":
            delta = keyed_step(key, seed, counter)
            offset = mod(offset + direction_sign * disk_factor * delta)

    return jsonify(
        result="".join(output),
        trace=trace,
        inner_alphabet=inner,
        base_offset=base_offset,
        fixed_disk=fixed_disk,
        moving_disk=moving_disk
    )




if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)