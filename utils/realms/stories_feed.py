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
    # Direct screenshot locators avoid the legacy Xbox image-proxy wrapper.
    locators = item.get('gameMediaContentLocators')
    if isinstance(locators, list):
        for kind in ('Download', 'Thumbnail_Large', 'Thumbnail_Small'):
            for locator in locators[:20]:
                if isinstance(locator, dict) and locator.get('LocatorType') == kind:
                    url = image_url(locator.get('Uri'))
                    if url:
                        return [url]
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


EVENTS = {
    'NewMember': ('New Realm member', 'A new member event was recorded.'),
    'FirstCraftedNetherite': ('First netherite crafted', 'The first netherite crafting event was recorded.'),
    'FirstEnchantment': ('First enchantment', 'The first enchantment event was recorded.'),
    'RealmCreated': ('Realm created', 'The Realm was created.'),
}


def realm_event_text(event):
    kind = event.get('eventName')
    if isinstance(kind, str) and kind in EVENTS:
        return EVENTS[kind]
    return 'Realm Event', 'A Realm event was recorded.'


def participant_text(event, names):
    players = event.get('players')
    if not isinstance(players, list):
        return None
    # References are not proof that every listed player performed the action.
    identities = set(p for p in players if isinstance(p, str))
    known = [names[p] for p in sorted(identities) if p in names]
    missing = len(identities) - len(known)
    parts = known[:8]
    if len(known) > 8:
        parts.append(f'{len(known) - 8} more named players')
    if missing:
        parts.append(f'{missing} name(s) unavailable')
    return (f'{len(identities)} player reference(s): ' + (', '.join(parts) or 'none'))[:1024]


def render_feed(body):
    """Return (opaque ID, embed) pairs, plus skipped/remaining counts."""
    if not isinstance(body, dict) or not isinstance(body.get('activityItems'), list):
        raise ProtocolError()
    result = list(body['activityItems'])
    realm = body.get('realmEvents', [])
    if not isinstance(realm, list) or len(realm) > 1000:
        raise ProtocolError()
    if len(result) > 1000:
        raise ProtocolError()
    events = {}
    names = {}
    for item in result:
        if not isinstance(item, dict):
            continue
        author = item.get('authorInfo')
        if isinstance(author, dict):
            identity = author.get('id')
            name = author.get('modernGamertag') or author.get('name')
            if isinstance(identity, str) and isinstance(name, str) and name.strip() and not name.isdecimal():
                names[identity] = clean(name, 80)
    club_ids = {item.get('feedItemId') for item in result if isinstance(item, dict) and isinstance(item.get('feedItemId'), str)}
    for event in realm:
        if not isinstance(event, dict):
            continue
        reference = event.get('clubsPostId')
        if not isinstance(reference, str) or not reference or len(reference) > 256:
            continue
        events[reference] = event
        if reference not in club_ids:
            result.append({'feedItemId': reference, 'contentType': 'System'})
            club_ids.add(reference)
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
        event = events.get(identity)
        text, media = story_text(item), images(item)
        event_title = None
        if event is not None:
            event_title, text = realm_event_text(event)
        if not text and not media:
            # Avoid publishing IDs, event metadata, or empty placeholder stories.
            skipped += 1
            continue
        title = 'Realm Screenshot' if item.get('activityItemType') == 'Screenshot' else ('Realm Event' if item.get('contentType') == 'System' else 'Realm Story')
        embed = discord.Embed(title=event_title or title, description=text or None, colour=0x55AA55,
                              timestamp=(timestamp(event.get('timestamp')) if event else None) or timestamp(item.get('date')))
        author = item.get('authorInfo')
        if isinstance(author, dict) and event is None:
            name = author.get('modernGamertag') or author.get('name')
            if isinstance(name, str) and name.strip() and not name.isdecimal():
                suffix = author.get('modernGamertagSuffix')
                if isinstance(suffix, str) and suffix.isascii() and suffix.isdigit() and len(suffix) <= 8:
                    name += '#' + suffix
                avatar = image_url(author.get('imageUrl'))
                embed.set_author(name=clean(name, 80), **({'icon_url': avatar} if avatar else {}))
        if event is not None:
            participants = participant_text(event, names)
            if participants:
                embed.add_field(name='Players referenced by event', value=participants, inline=False)
        if media:
            embed.set_image(url=media[0])
        if len(media) > 1:
            embed.set_footer(text=f'{len(media) - 1} additional images not included')
        rendered.append((identity, embed))
    return rendered, skipped, max(0, len(result) - 10)
