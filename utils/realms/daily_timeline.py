"""Observed UTC interval unions and a local-calendar Minecraft-inspired timeline."""
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
import hashlib
import io

ZONE = ZoneInfo('America/Chicago')
UTC = timezone.utc


def window(day):
    return tuple(datetime.combine(d, time(), ZONE).astimezone(UTC)
                 for d in (day, day + timedelta(days=1)))


def aggregate(rows, day):
    lo, hi = window(day)
    groups = {}
    count = 0
    for xuid, start, end in rows:
        if not xuid or start is None or end is None:
            continue
        start, end = (v.replace(tzinfo=UTC) if v.tzinfo is None else v.astimezone(UTC)
                      for v in (start, end))
        a, b = max(lo, start), min(hi, end)
        if a < b:
            groups.setdefault(xuid, []).append((a, b))
            count += 1
    for xuid, spans in groups.items():
        merged = []
        for a, b in sorted(spans):
            if merged and a <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(b, merged[-1][1]))
            else:
                merged.append((a, b))
        groups[xuid] = merged
    seconds = sum((b-a).total_seconds() for spans in groups.values() for a, b in spans)
    return groups, count, seconds


def fallback(xuid):
    return 'Player ' + hashlib.sha256(xuid.encode()).hexdigest()[:8]


def render(day, groups, names):
    from PIL import Image, ImageDraw, ImageFont
    lo, hi = window(day)
    hours = int((hi-lo).total_seconds() / 3600)
    image = Image.new('RGB', (1280, 190 + max(1, len(groups))*34), '#171e20')
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=16)
    title = ImageFont.load_default(size=25)
    draw.rectangle((0, 0, 1279, 7), fill='#6caf43')
    draw.text((24, 23), f'Coastal Craft | {day:%B %d, %Y}', font=title, fill='#e5f0df')
    draw.text((24, 62), 'Observed Realm Activity | America/Chicago', font=font, fill='#9acc83')
    draw.text((24, 88), 'Missing observations do not mean inactivity. Coverage is unverified.', font=font, fill='#b5bfc2')
    left, width, top = 260, 990, 148
    for h in range(hours+1):
        x = left + width*h/hours
        local = (lo+timedelta(hours=h)).astimezone(ZONE)
        draw.line((x, top-4, x, image.height-30), fill='#354146')
        if h % 2 == 0 or h == hours:
            draw.text((x-12, 120), local.strftime('%H'), font=font, fill='#c4ced0')
    colors = ('#77bc50', '#55b6d9', '#e4b65b', '#b38ce0')
    for i, xuid in enumerate(sorted(groups, key=lambda x: (names.get(x, fallback(x)).casefold(), x))):
        y = top+i*34
        draw.text((24, y+3), names.get(xuid, fallback(xuid))[:25], font=font, fill='#e5ecee')
        for a, b in groups[xuid]:
            x1 = left+width*(a-lo).total_seconds()/(hi-lo).total_seconds()
            x2 = left+width*(b-lo).total_seconds()/(hi-lo).total_seconds()
            draw.rectangle((x1, y+5, max(x1+1, x2), y+23), fill=colors[i % 4])
    if not groups:
        draw.text((left+15, top+5), 'No activity intervals observed; coverage may be unavailable.', font=font, fill='#c4ced0')
    draw.text((24, image.height-24), f'{hours}-hour reporting window; repeated DST hours are separate columns.', font=font, fill='#9caeb3')
    output = io.BytesIO()
    image.save(output, format='PNG')
    return output.getvalue()
