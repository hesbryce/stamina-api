from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime

app = FastAPI()

class HeartRateData(BaseModel):
    heartRate: float

# Convert the Swift-style BPM range mappings into Python
def generate_heart_rate_map():
    map = {}
    mappings = [
        (range(0, 60), 100), (range(60, 64), 99), (range(64, 68), 98), (range(68, 72), 97), (range(72, 76), 96),
        (range(76, 80), 95), (range(80, 84), 94), (range(84, 88), 93), (range(88, 92), 92), (range(92, 96), 91),
        (range(96, 99), 90), (range(99, 100), 89), (range(100, 104), 88), (range(104, 106), 87), (range(106, 108), 86),
        (range(108, 110), 85), (range(110, 112), 84), (range(112, 114), 83), (range(114, 116), 82), (range(116, 120), 81),
        (range(120, 121), 80), (range(121, 123), 79), (range(123, 125), 78), (range(125, 126), 77),
        (range(126, 127), 76), (range(127, 129), 75), (range(129, 131), 74), (range(131, 133), 72),
        (range(133, 135), 70), (range(135, 137), 68), (range(137, 141), 67), (range(141, 143), 65),
        (range(143, 145), 64), (range(145, 147), 62), (range(147, 149), 61), (range(149, 151), 59),
        (range(151, 153), 58), (range(153, 155), 57), (range(155, 157), 55), (range(157, 159), 54),
        (range(159, 161), 53), (range(161, 163), 51), (range(163, 165), 49), (range(165, 167), 47),
        (range(167, 169), 45), (range(169, 171), 41), (range(171, 173), 39), (range(173, 175), 35),
        (range(175, 177), 33), (range(177, 179), 29), (range(179, 181), 27), (range(181, 183), 25),
        (range(183, 185), 23), (range(185, 187), 21), (range(187, 189), 19), (range(189, 191), 17),
        (range(191, 193), 15), (range(193, 195), 13), (range(195, 197), 11), (range(197, 205), 10),
    ]

    for hr_range, stamina in mappings:
        for bpm in hr_range:
            map[bpm] = stamina
    return map

heart_rate_to_stamina = generate_heart_rate_map()

def get_color(stamina_score):
    if stamina_score >= 91:
        return "blue"
    elif stamina_score >= 86:
        return "green"
    elif stamina_score >= 76:
        return "green-yellow"
    elif stamina_score >= 51:
        return "yellow"
    elif stamina_score >= 40:
        return "yellow-orange"
    elif stamina_score >= 30:
        return "orange"
    else:
        return "red"

@app.post("/stamina")
def get_stamina(data: HeartRateData):
    bpm = round(data.heartRate)
    score = heart_rate_to_stamina.get(bpm, 0)
    color = get_color(score)
    timestamp = datetime.utcnow().isoformat()

    print(f"📥 Stamina at: {score}%, Color: {color}")

    return {
        "staminaScore": score,
        "color": color,
        "timestamp": timestamp
    }
