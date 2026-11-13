"""Observed UTC interval unions and a local-calendar Minecraft-inspired timeline."""
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
import hashlib
import io

from .activity_credit import ActivityGroups, credited_totals, group_credit

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
    groups = ActivityGroups(groups, credited_totals(rows, lo=lo, hi=hi))
    seconds = sum(groups.credits.values())
    return groups, count, seconds


def fallback(xuid):
    return 'Player ' + hashlib.sha256(xuid.encode()).hexdigest()[:8]


PALETTE = ('#64cbe9', '#8cd38d', '#f6b46d', '#c09cf5', '#f28fa0', '#68d6bf', '#e6cf78', '#80aefa')


def player_color(xuid):
    return PALETTE[int.from_bytes(hashlib.sha256(xuid.encode()).digest()[:4], 'big') % len(PALETTE)]


def duration(seconds):
    # Preserve brief visits without claiming a full minute of observed activity.
    if 0 < seconds < 60:
        return '<1m'
    minutes = int(max(0, seconds) / 60 + 0.5)
    return f'{minutes // 60}h {minutes % 60:02d}m' if minutes >= 60 else f'{minutes}m'


def row_names(xuid, names):
    value = names.get(xuid, {})
    if isinstance(value, str):
        value = {'gamertag': value}
    gamertag = value.get('gamertag') or fallback(xuid)
    discord = value.get('discord')
    if discord and discord.casefold() != gamertag.casefold():
        return discord, gamertag
    return gamertag, None


def ordered_players(groups):
    return sorted(groups, key=lambda x: (-group_credit(groups, x), x))


def axis_ticks(day):
    lo, hi = window(day)
    # Local wall-clock major ticks retain proportional UTC spacing across DST.
    return [(datetime.combine(day, time(hour), ZONE).astimezone(UTC), label)
            for hour, label in ((0, '12 AM'), (6, '6 AM'), (12, '12 PM'), (18, '6 PM'))] + [(hi, '12 AM')]


def load_font(size, bold=False):
    from PIL import ImageFont
    # Use host fonts when present; Pillow's bundled font remains portable.
    for path in (('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf'),
                 ('C:/Windows/Fonts/segoeuib.ttf' if bold else 'C:/Windows/Fonts/segoeui.ttf')):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default(size=size)


def render(day, groups, names, collected_at=None):
    from PIL import Image, ImageDraw, ImageFont
    lo, hi = window(day)
    elapsed = (hi-lo).total_seconds()
    hours = int(elapsed / 3600)
    image = Image.new('RGB', (1200, 212 + max(1, len(groups))*70), '#101a25')
    draw = ImageDraw.Draw(image)

    font = load_font

    title, heading, regular, small = font(27, True), font(21, True), font(19), font(16)

    def fitted(text, face, width):
        text = ' '.join(str(text).split())
        if draw.textlength(text, font=face) <= width:
            return text
        while text and draw.textlength(text + '…', font=face) > width:
            text = text[:-1]
        return text + '…'

    draw.rectangle((12, 12, 1187, image.height-13), outline='#304658', width=2)
    draw.rectangle((12, 12, 20, 20), fill='#f6b46d')
    draw.rectangle((1180, 12, 1187, 20), fill='#f6b46d')
    draw.text((30, 25), 'Coastal Craft · Season 10', font=title, fill='#e3edf5')
    draw.text((30, 61), 'The Mighty Mesa Reborn', font=regular, fill='#f6b46d')
    draw.text((30, 96), 'Observed Realm Activity', font=heading, fill='#e3edf5')
    draw.text((1170, 32), f'{day:%B %d, %Y}', font=heading, fill='#e3edf5', anchor='ra')
    draw.text((1170, 68), f'America/Chicago · {hours}-hour day', font=small, fill='#afc5d7', anchor='ra')
    left, width, top = 300, 730, 164
    now = datetime.now(UTC)
    future_x = left + width * max(0, min(1, (now-lo).total_seconds()/elapsed))
    ticks = axis_ticks(day)
    draw.text((40, 135), 'PLAYER', font=small, fill='#8fa7bb')
    draw.text((1160, 135), 'TOTAL', font=small, fill='#8fa7bb', anchor='ra')
    for stamp, label in ticks:
        x = left + width*(stamp-lo).total_seconds()/elapsed
        draw.text((x, 135), label, font=small, fill='#afc5d7', anchor='ma')
    for i, xuid in enumerate(ordered_players(groups)):
        y = top+i*70
        # Separate outlined rows distinguish neighboring players even when colors collide.
        draw.rectangle((30, y, 1169, y+63), fill='#1b2b39' if i % 2 == 0 else '#152331', outline='#2b4052')
        color = player_color(xuid)
        draw.rectangle((40, y+12, 45, y+51), fill=color)
        first, second = row_names(xuid, names)
        draw.text((58, y+(8 if second else 20)), fitted(first, heading, 220), font=heading, fill='#e3edf5')
        if second:
            draw.text((58, y+34), fitted(second, regular, 220), font=regular, fill='#9eb6ca')
        draw.rectangle((left, y+23, left+width, y+42), fill='#283949')
        if now < hi:
            draw.rectangle((future_x, y+23, left+width, y+42), fill='#111b28')
        for stamp, _ in ticks:
            x = left+width*(stamp-lo).total_seconds()/elapsed
            draw.line((x, y+5, x, y+58), fill='#354a5b')
        for a, b in groups[xuid]:
            x1 = left+width*(a-lo).total_seconds()/elapsed
            x2 = left+width*(b-lo).total_seconds()/elapsed
            draw.rectangle((x1, y+23, min(left+width, max(x1+1, x2)), y+42), fill=color)
        total = group_credit(groups, xuid)
        draw.text((1158, y+19), duration(total), font=heading, fill='#e3edf5', anchor='ra')
    if not groups:
        draw.text((40, top+20), 'No activity intervals observed; coverage may be unavailable.', font=regular, fill='#afc5d7')
    footer = 'Credit: live 100%, timeline-only 50%'
    if lo <= now < hi:
        footer = 'Live 100%, timeline-only 50% · Dark = future'
    elif hours != 24:
        footer = f'Live 100%, timeline-only 50% · {hours}h DST day'
    draw.text((30, image.height-32), footer, font=small, fill='#8fa7bb')
    if collected_at is not None:
        local = collected_at.astimezone(ZONE)
        stamp = f"{local:%B} {local.day}, {local.year} {local:%I:%M %p}".replace(' 0', ' ')
        collection = 'Last successful collection: ' + stamp
    else:
        collection = 'Last successful collection: unavailable'
    draw.text((1170, image.height-32), collection, font=small, fill='#8fa7bb', anchor='ra')
    output = io.BytesIO()
    image.save(output, format='PNG')
    return output.getvalue()
