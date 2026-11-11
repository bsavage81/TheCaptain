"""Temporary structural probe: no upstream scalar values or arbitrary keys escape."""
from collections import Counter

# Unknown keys may themselves be player names, XUIDs, text, or signed URLs.
FIELDS = frozenset('result stories posts feed items data entries id storyId postId author authorId creator owner xuid player playerName gamertag createdAt updatedAt timestamp time date text content message caption title description screenshots screenshot images image media attachments url imageUrl thumbnail thumbnailUrl type storyType eventType event events automaticEvent autoStory metadata pagination nextCursor cursor total count hasMore activity s e'.split())
KINDS = {
    'post': 'posts', 'story': 'posts', 'userpost': 'posts', 'playerstory': 'posts',
    'screenshot': 'screenshots', 'image': 'screenshots', 'photo': 'screenshots',
    'event': 'automatic events', 'automaticevent': 'automatic events',
    'autostory': 'automatic events', 'automaticstory': 'automatic events',
}


def json_type(value):
    if value is None:
        return 'null'
    if isinstance(value, bool):
        return 'boolean'
    if isinstance(value, dict):
        return 'object'
    if isinstance(value, list):
        return 'array'
    if isinstance(value, str):
        return 'string'
    return 'number'


def summarize(body):
    fields, arrays, types = Counter(), Counter(), Counter()
    detected = set()
    unknown_keys = nodes = 0
    truncated = False

    def walk(value, depth=0, parent=None):
        nonlocal unknown_keys, nodes, truncated
        if nodes >= 10000 or depth > 12:
            truncated = True
            return
        nodes += 1
        types[json_type(value)] += 1
        if isinstance(value, dict):
            for key, child in value.items():
                if nodes >= 10000:
                    truncated = True
                    break
                safe = key if key in FIELDS else '<redacted-key>'
                fields[safe + ':' + json_type(child)] += 1
                unknown_keys += safe == '<redacted-key>'
                # Only fixed, recognized type labels can affect output. Never echo values.
                if key in {'type', 'storyType', 'eventType'} and isinstance(child, str):
                    kind = KINDS.get(child.casefold().replace('_', '').replace('-', ''))
                    if kind:
                        detected.add(kind)
                if child and key in {'posts', 'stories'} and isinstance(child, list):
                    detected.add('posts')
                if child and key in {'screenshots', 'screenshot', 'images', 'image', 'imageUrl'}:
                    detected.add('screenshots')
                if child and key in {'automaticEvent', 'autoStory', 'eventType'}:
                    detected.add('automatic events')
                walk(child, depth + 1, safe)
        elif isinstance(value, list):
            arrays[parent or '<root>'] += len(value)
            for child in value:
                if nodes >= 10000:
                    truncated = True
                    break
                walk(child, depth + 1)

    walk(body)
    lines = ['Top-level JSON: ' + json_type(body)]
    if isinstance(body, (dict, list)):
        lines.append(f'Top-level item count: {len(body)}')
    if isinstance(body, dict):
        top = sorted({key if key in FIELDS else '<redacted-key>' for key in body})
        lines.append('Top-level fields: ' + (', '.join(top[:16]) or 'none'))
    lines.append('Field names/types (occurrences; unknown names redacted):')
    # Bound the report well below Discord's 2,000 character limit.
    for name, count in sorted(fields.items())[:24]:
        lines.append(f'  {name}: {count}')
    if len(fields) > 24:
        lines.append(f'  Additional field/type pairs omitted: {len(fields) - 24}')
    lines.append('Array item totals by field: ' + (', '.join(f'{k}={v}' for k, v in sorted(arrays.items())[:12]) or 'none'))
    lines.append('JSON value types: ' + ', '.join(f'{k}={v}' for k, v in sorted(types.items())))
    for label in ('posts', 'screenshots', 'automatic events'):
        lines.append(label.capitalize() + ': ' + ('structural evidence detected' if label in detected else 'not detected; presence unknown'))
    lines.append(f'Redacted key occurrences: {unknown_keys}. Scan truncated: {"yes" if truncated else "no"}.')
    lines.append('Detection is heuristic; no content values or image URLs are shown or fetched.')
    return '\n'.join(lines)


# Record field names are needed to discover an undocumented schema. Arbitrary
# map keys (identities, URLs, free text) remain redacted; values never escape.
def detailed_report(body):
    import hashlib
    import json
    import re
    from urllib.parse import urlsplit

    lines = ['Detailed schema (values withheld; item indexes are response order)']
    nodes = 0
    budget = 48000
    used = 0
    omitted = False
    fingerprints = {}

    def emit(line):
        nonlocal used, omitted
        if used + len(line) + 1 > budget:
            omitted = True
            return False
        lines.append(line)
        used += len(line) + 1
        return True

    def key_name(key, schema):
        if key in FIELDS:
            return key
        if schema and isinstance(key, str) and re.fullmatch(r'[a-z][A-Za-z_]{0,63}', key):
            return key
        return '<redacted-key>'

    def describe(value):
        kind = json_type(value)
        if isinstance(value, (dict, list)):
            return f'{kind} count={len(value)}'
        if isinstance(value, str):
            flags = []
            if not value:
                flags.append('empty')
            if value.isascii() and value.isdecimal():
                flags.append('decimal/possible identifier')
            if re.fullmatch(r'[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}', value):
                flags.append('UUID-shaped')
            if re.match(r'^\d{4}-\d{2}-\d{2}T', value):
                flags.append('ISO timestamp-shaped')
            if value.startswith(('https://', 'http://')):
                flags.append('URL-shaped')
                try:
                    url = urlsplit(value)
                    # Counts and fixed labels only: signed paths/queries stay private.
                    flags.append(f'path segments={len([p for p in url.path.split("/") if p])}')
                    flags.append('query present=' + ('yes' if url.query else 'no'))
                    extension = url.path.rsplit('.', 1)[-1].lower()
                    if extension in {'png', 'jpg', 'jpeg', 'webp', 'gif', 'mp4'}:
                        flags.append('media extension=' + extension)
                except ValueError:
                    pass
            if value.lstrip().startswith(('{', '[')):
                flags.append('JSON-shaped string')
            # Opaque equality labels reveal repeated references without emitting IDs,
            # hashes that can be guessed offline, or the underlying string.
            digest = hashlib.sha256(value.encode()).digest()
            if digest not in fingerprints:
                fingerprints[digest] = f'v{len(fingerprints) + 1}'
            return f'string length={len(value)} ref={fingerprints[digest]}' + ('; ' + ', '.join(flags) if flags else '')
        return kind + ' (value withheld)'

    def walk(value, path='$', depth=0, schema=False, field=None):
        nonlocal nodes, omitted
        if nodes >= 1500 or depth > 12 or used >= budget:
            omitted = True
            return
        nodes += 1
        if not emit(path + ': ' + describe(value)):
            return
        if isinstance(value, dict):
            # Root and direct feed items have schema keys. Unknown dictionaries
            # remain maps unless reached through a recognized schema container.
            for index, (key, child) in enumerate(value.items()):
                if index >= 80 or nodes >= 1500 or used >= budget:
                    omitted = True
                    break
                safe = key_name(key, schema)
                child_schema = key in {'result', 'posts', 'stories', 'items', 'entries', 'data',
                    'author', 'creator', 'content', 'body', 'media', 'attachments', 'images', 'screenshots', 'metadata'}
                walk(child, path + '.' + safe, depth + 1, child_schema, key)
        elif isinstance(value, list):
            for index, child in enumerate(value[:20]):
                if nodes >= 1500 or used >= budget:
                    omitted = True
                    break
                # The live response is result=[story objects]. Reveal their schema
                # fields, without treating an arbitrary identity map as a schema.
                walk(child, f'{path}[{index}]', depth + 1, schema, field)
            if len(value) > 20:
                emit(path + f': {len(value) - 20} additional items not expanded')
                omitted = True
        elif isinstance(value, str) and value.lstrip().startswith(('{', '[')) and len(value) <= 65536:
            try:
                decoded = json.loads(value)
            except (ValueError, RecursionError):
                return
            # Inspect encoded payload structure, but never print its literal text.
            if isinstance(decoded, (dict, list)):
                walk(decoded, path + '.<decoded-json>', depth + 1, True)

    walk(body, schema=True)
    lines.append('Detailed scan truncated: ' + ('yes' if omitted else 'no'))
    lines.append('No string, numeric or boolean values printed. ref labels apply only within this report.')
    return '\n'.join(lines)
