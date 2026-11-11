"""Small, explicit Story Feed renderer. Never dump unknown upstream fields."""
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import discord

from utils.integrations.realms.errors import ProtocolError


ARTWORK_DIR = Path(__file__).resolve().parents[2] / "images" / "realms-stories"
# Explicit names only: upstream event names never become arbitrary filesystem paths.
EVENT_ARTWORK = frozenset({
    '250HostileMobs',
    'AllMobNameEasterEggs',
    'CookEverything',
    'DefeatEnderdragon',
    'DefeatWither',
    'DiamondEverything',
    'EasyAndSafe',
    'FirstAbandonedMineshaftFound',
    'FirstAncientCityFound',
    'FirstBadlandsFound',
    'FirstConduit',
    'FirstCraftedNetherite',
    'FirstDiamondFound',
    'FirstEnchantment',
    'FirstEndPortal',
    'FirstEnderDragonDefeated',
    'FirstFullyExploredMap',
    'FirstMushroomFieldFound',
    'FirstNetherFortressFound',
    'FirstNetherPortalLit',
    'FirstPeakMountainFound',
    'FirstPillagerOutpostFound',
    'FirstPoweredBeacon',
    'FirstWitherDefeated',
    'FirstWoodlandMansionFound',
    'NamedMob',
    'NamedMobDies',
    'NewMember',
    'PillagerCaptainDefeated',
    'RealmCreated',
    'SlotSwitch',
})


def artwork_file(embed):
    """Open a fresh attachment for this send; the caller closes it afterward."""
    url = embed.image.url or ""
    prefix = "attachment://"
    if not url.startswith(prefix):
        return None
    filename = url[len(prefix):]
    if filename not in {name + ".png" for name in EVENT_ARTWORK}:
        return None
    return discord.File(ARTWORK_DIR / filename, filename=filename)


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


# Verified Minecraft en_US.lang feedEvent templates.
EVENT_TEXT = {
    'FirstEnderDragonDefeated': 'The Ender Dragon was defeated!',
    'FirstWitherDefeated': 'The Wither was defeated!',
    '250HostileMobs': '%1$s cannot be defeated by mere mobs',
    '250HostileMobs.grouped': '%1$s cannot be defeated by mere mobs',
    'AllMobNameEasterEggs': '%1$s created all the mystery mobs',
    'AllMobNameEasterEggs.grouped': '%1$s created all the mystery mobs',
    'CookEverything': '%1$s prepared a 13 course meal',
    'DefeatEnderdragon': '%1$s defeated the Ender Dragon!... again',
    'DefeatEnderdragon.grouped': 'The Ender Dragon was defeated!... again',
    'DefeatWither': '%1$s defeated the Wither!... again',
    'DefeatWither.grouped': 'The Wither was defeated!... again',
    'DiamondEverything': '%1$s has a full diamond set',
    'DiamondEverything.grouped': '%1$s have full diamond sets',
    'FirstAbandonedMineshaftFound': '%1$s discovered an Abandoned Mineshaft',
    'FirstAncientCityFound': '%1$s discovered an Ancient City',
    'FirstBadlandsFound': '%1$s discovered a Badlands',
    'FirstConduit': '%1$s now commands the sea',
    'FirstCraftedNetherite': '%1$s upgraded to Netherite',
    'FirstCraftedNetherite.grouped': '%1$s upgraded to Netherite',
    'FirstDiamondFound': '%1$s found a diamond',
    'FirstEnchantment': '%1$s discovered enchanting',
    'FirstEnchantment.grouped': '%1$s discovered enchanting',
    'FirstEndPortal': '%1$s traveled to the End?',
    'FirstFullyExploredMap': '%1$s started mapping the world',
    'FirstMushroomFieldFound': '%1$s discovered a Mushroom Field',
    'FirstNetherFortressFound': '%1$s discovered a Nether Fortress',
    'FirstNetherPortalLit': '%1$s created a portal to the Nether',
    'FirstPeakMountainFound': '%1$s scaled a Mountain Peak',
    'FirstPillagerOutpostFound': '%1$s discovered a Pillager Outpost',
    'FirstPoweredBeacon': '%1$s powered a Beacon!',
    'FirstWoodlandMansionFound': '%1$s discovered a Woodland Mansion',
    'NamedMob': '%1$s has a new friend, %2$s',
    'NamedMobDies': '%1$s met an untimely death',
    'NewMember': '%1$s joined the Realm',
    'NewMember.grouped': '%1$s joined the Realm',
    'PillagerCaptainDefeated': '%1$s defeated a Pillager Captain',
    'RealmCreated': 'A new adventure has begun! What will the story of this Realm be? You decide.',
    'SlotSwitch': 'The world changed to %1$s',
}
EVENT_TITLES = {'NewMember': 'New Realm member', 'FirstCraftedNetherite': 'Upgraded to Netherite', 'FirstEnchantment': 'Discovered enchanting', 'PillagerCaptainDefeated': 'Pillager Captain defeated', 'RealmCreated': 'Realm created'}


def player_phrase(event, names):
    players = event.get('players')
    ids = list(dict.fromkeys(p for p in players if isinstance(p, str))) if isinstance(players, list) else []
    known = [names[p] for p in ids if p in names][:5]
    others = len(ids) - len(known)
    if not known:
        return 'A player' if len(ids) <= 1 else f'{len(ids)} players'
    if others:
        return ', '.join(known) + f' and {others} other player' + ('s' if others != 1 else '')
    if len(known) == 1:
        return known[0]
    return ', '.join(known[:-1]) + ' and ' + known[-1]


def realm_event_text(event, names):
    kind = event.get('eventName')
    if not isinstance(kind, str) or kind not in EVENT_TEXT:
        return 'Realm Event', 'A Realm event was recorded.'
    title = EVENT_TITLES.get(kind, 'Realm Event')
    # These substitutions are not player identities. Until their payload fields
    # are verified, describe the event without guessing a mob or world name.
    if kind == 'NamedMobDies':
        return title, 'A named mob met an untimely death.'
    if kind == 'SlotSwitch':
        return title, 'The Realm world changed.'
    players = event.get('players')
    players = list(dict.fromkeys(p for p in players if isinstance(p, str))) if isinstance(players, list) else []
    if kind == 'NamedMob':
        return title, player_phrase(dict(event, players=players[:1]), names) + ' has a new friend.'
    template = EVENT_TEXT[kind]
    grouped = kind + '.grouped'
    if len(players) > 1 and grouped in EVENT_TEXT:
        template = EVENT_TEXT[grouped]
        subject = player_phrase(dict(event, players=players), names)
    else:
        subject = player_phrase(dict(event, players=players[:1]), names)
    text = template.replace('%1$s', subject)
    if not text.endswith(('.', '!', '?')):
        text += '.'
    return title, text


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
    supplied_names = body.get('playerNames', {})
    names = {x: clean(name, 80) for x, name in supplied_names.items()
             if isinstance(x, str) and isinstance(name, str) and name.strip() and not name.isdecimal()} if isinstance(supplied_names, dict) else {}
    for item in result:
        if not isinstance(item, dict):
            continue
        author = item.get('authorInfo')
        if isinstance(author, dict):
            identity = author.get('id')
            name = author.get('modernGamertag') or author.get('name')
            if isinstance(identity, str) and isinstance(name, str) and name.strip() and not name.isdecimal():
                names.setdefault(identity, clean(name, 80))
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
            event_title, text = realm_event_text(event, names)
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
        if media:
            embed.set_image(url=media[0])
        elif event is not None:
            kind = event.get('eventName')
            if isinstance(kind, str) and kind in EVENT_ARTWORK and (ARTWORK_DIR / (kind + '.png')).is_file():
                embed.set_image(url='attachment://' + kind + '.png')
        if len(media) > 1:
            embed.set_footer(text=f'{len(media) - 1} additional images not included')
        rendered.append((identity, embed))
    return rendered, skipped, max(0, len(result) - 10)
