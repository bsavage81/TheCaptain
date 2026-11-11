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
