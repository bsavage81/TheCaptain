"""Operator-verified historical reconstruction; never applied to the live feed."""
import json
from pathlib import Path

from .stories_feed import event_reference
from utils.integrations.realms.errors import ProtocolError

ARCHIVE = Path(__file__).resolve().parents[2] / 'config' / 'old-coastal-s10-stories.json'


def restore_archive(body, *, path=ARCHIVE):
    data = json.loads(path.read_text(encoding='utf8'))
    if data.get('version') != 1 or not isinstance(data.get('events'), list):
        raise ProtocolError()
    if body.get('sourceRealmId') != data.get('realm_id'):
        return body
    records = {row['event_id']: row for row in data['events']}
    events = [dict(event) for event in body.get('realmEvents', [])]
    names = dict(body.get('playerNames', {}))
    by_id = {event.get('id'): event for event in events}
    for item in body['activityItems']:
        if not isinstance(item, dict):
            continue
        reference = event_reference(item)
        row = records.get(reference)
        if row is None:
            continue
        event = by_id.get(reference)
        if event is None:
            event = dict(id=reference, clubsPostId=item['feedItemId'], timestamp=item.get('date'))
            events.append(event)
            by_id[reference] = event
        participants = row['participants']
        if (not isinstance(participants, list) or not 1 <= len(participants) <= 25
                or not all(isinstance(name, str) and name.strip() for name in participants)):
            raise ProtocolError()
        players = [f'archive:{reference}:{index}' for index in range(len(participants))]
        names.update(zip(players, participants))
        event.update(eventName=row['event_name'], players=players, _archive_all_names=True)
        if row.get('pet_name'):
            event['metadata'] = {'metatext': row['pet_name']}
    return dict(body, realmEvents=events, playerNames=names)
