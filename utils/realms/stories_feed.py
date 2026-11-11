"""Small, explicit Story Feed renderer. Never dump unknown upstream fields."""
from datetime import datetime, timezone
from urllib.parse import urlsplit

import discord

from utils.integrations.realms.errors import ProtocolError

TEXT_FIELDS = ('ugcCaption', 'itemText', 'description', 'shortDescription')


def clean(value, limit):
    if not isinstance(value, str):
        return ''
    value = ''.join(c for c in value if c in '\n\t' or ord(c) >= 32)
    return discord.utils.escape_mentions(discord.utils.escape_markdown(value[:limit]))[:limit]


def story_text(item):
    for key in TEXT_FIELDS:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return clean(value, 1500)
        if isinstance(value, dict):
            # Some feeds wrap content, but arbitrary metadata is never rendered.
            for nested in TEXT_FIELDS:
                if isinstance(value.get(nested), str) and value[nested].strip():
                    return clean(value[nested], 1500)
    return ''


def image_url(value):
    """Embed existing media references only; no new download/auth endpoint."""
    if not isinstance(value, str) or len(value) > 2048:
        return None
    try:
        url = urlsplit(value)
        host = (url.hostname or '').lower()
        # Club activity returns legacy HTTP image URLs on this Xbox CDN.
        # Preserve the path/query while using its HTTPS equivalent for embeds.
        if (url.scheme == 'http' and host == 'images-eds.xboxlive.com'
                and not url.username and not url.password and url.port is None):
            url = url._replace(scheme='https')
            value = url.geturl()
        trusted = ('minecraft-services.net', 'minecraft.net', 'xboxlive.com', 'blob.core.windows.net')
        if (url.scheme == 'https' and not url.username and not url.password
                and url.port in (None, 443)
                and any(host == domain or host.endswith('.' + domain) for domain in trusted)):
            return value
    except ValueError:
        pass
    return None


def images(item):
    # Prefer the verified full screenshot; do not substitute a game cover/avatar.
    for key in ('screenshotUri', 'screenshotThumbnail'):
        url = image_url(item.get(key))
        if url:
            return [url]
    return []


def timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return result.astimezone(timezone.utc) if result.tzinfo else None
    except (ValueError, OverflowError):
        return None


def render_feed(body):
    """Return (opaque ID, embed) pairs, plus skipped/remaining counts."""
    if not isinstance(body, dict) or not isinstance(body.get('activityItems'), list):
        raise ProtocolError()
    result = body['activityItems']
    if len(result) > 1000:
        raise ProtocolError()
    rendered, skipped, seen = [], 0, set()
    for item in result[:10]:
        if not isinstance(item, dict):
            skipped += 1
            continue
        identity = item.get('feedItemId')
        if not isinstance(identity, str) or not identity or len(identity) > 256:
            skipped += 1
            continue
        if identity in seen:
            skipped += 1
            continue
        seen.add(identity)
        text, media = story_text(item), images(item)
        if not text and not media:
            # Avoid publishing IDs, event metadata, or empty placeholder stories.
            skipped += 1
            continue
        title = 'Realm Screenshot' if item.get('activityItemType') == 'Screenshot' else ('Realm Event' if item.get('contentType') == 'System' else 'Realm Story')
        embed = discord.Embed(title=title, description=text or None, colour=0x55AA55,
                              timestamp=timestamp(item.get('date')))
        author = item.get('authorInfo')
        if isinstance(author, dict):
            name = author.get('modernGamertag') or author.get('name')
            if isinstance(name, str) and name.strip() and not name.isdecimal():
                suffix = author.get('modernGamertagSuffix')
                if isinstance(suffix, str) and suffix.isascii() and suffix.isdigit() and len(suffix) <= 8:
                    name += '#' + suffix
                avatar = image_url(author.get('imageUrl'))
                embed.set_author(name=clean(name, 80), **({'icon_url': avatar} if avatar else {}))
        if media:
            embed.set_image(url=media[0])
        if len(media) > 1:
            embed.set_footer(text=f'{len(media) - 1} additional images not included')
        rendered.append((identity, embed))
    return rendered, skipped, max(0, len(result) - 10)
