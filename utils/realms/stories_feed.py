"""Small, explicit Story Feed renderer. Never dump unknown upstream fields."""
from datetime import datetime, timezone
from urllib.parse import urlsplit

import discord

from utils.integrations.realms.errors import ProtocolError

TEXT_FIELDS = ('text', 'message', 'content', 'body', 'caption', 'description', 'storyText', 'storyMessage')
IMAGE_FIELDS = ('screenshots', 'images', 'attachments', 'media', 'screenshot', 'image', 'imageUrl', 'screenshotUrl')


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
        trusted = ('minecraft-services.net', 'minecraft.net', 'xboxlive.com', 'blob.core.windows.net')
        if (url.scheme == 'https' and not url.username and not url.password
                and url.port in (None, 443)
                and any(host == domain or host.endswith('.' + domain) for domain in trusted)):
            return value
    except ValueError:
        pass
    return None


def images(item):
    found = []
    def scan(value, depth=0):
        if depth > 3 or len(found) >= 4:
            return
        if isinstance(value, str):
            url = image_url(value)
            if url and url not in found:
                found.append(url)
        elif isinstance(value, list):
            for child in value[:20]:
                scan(child, depth + 1)
        elif isinstance(value, dict):
            for key in ('url', 'imageUrl', 'screenshotUrl', 'src', *IMAGE_FIELDS):
                if key in value:
                    scan(value[key], depth + 1)
    for key in IMAGE_FIELDS:
        scan(item.get(key))
    return found


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
    if not isinstance(body, dict) or not isinstance(body.get('result'), list):
        raise ProtocolError()
    result = body['result']
    if len(result) > 1000:
        raise ProtocolError()
    rendered, skipped, seen = [], 0, set()
    for item in result[:10]:
        if not isinstance(item, dict):
            skipped += 1
            continue
        identity = item.get('id')
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
        embed = discord.Embed(title='Realm Story', description=text or None, colour=0x55AA55,
                              timestamp=timestamp(item.get('timestamp')))
        author = item.get('author')
        if isinstance(author, dict):
            name = author.get('gamertag') or author.get('displayName') or author.get('name')
            if isinstance(name, str) and name.strip() and not name.isdecimal():
                embed.set_author(name=clean(name, 80))
        if media:
            embed.set_image(url=media[0])
        if len(media) > 1:
            embed.set_footer(text=f'{len(media) - 1} additional images not included')
        rendered.append((identity, embed))
    return rendered, skipped, max(0, len(result) - 10)
