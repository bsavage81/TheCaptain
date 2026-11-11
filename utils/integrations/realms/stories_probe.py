"""Fixed, read-only Xbox probes derived only from a selected-Realm feed."""
import asyncio
import re
from urllib.parse import urlencode

from .errors import HTTPFailure, RealmsError
from .transport import XBOX_RP

REFERENCE = re.compile(
    r'userposts\.xboxlive\.com/users/xuid\(([1-9][0-9]{0,19})\)/posts/'
    r'([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})'
    r'/timelines/Club/([1-9][0-9]{0,19})')


def probe_urls(body):
    if not isinstance(body, dict) or not isinstance(body.get('result'), list):
        return None
    for item in body['result'][:1000]:
        if not isinstance(item, dict):
            continue
        reference = item.get('clubsPostId')
        if not isinstance(reference, str) or len(reference) > 256:
            continue
        match = REFERENCE.fullmatch(reference)
        if match and int(match[1]) < 2**64 and int(match[3]) < 2**64:
            return ('https://' + reference,
                    f'https://avty.xboxlive.com/clubs/clubId({match[3]})/activity/feed?numItems=10')
    return None


def next_club_page(base_url, body):
    """Build a same-club URL from an opaque token, never an upstream URL."""
    from .errors import StoriesError
    if not isinstance(body, dict):
        raise StoriesError('club_page')
    token = body.get('contToken')
    # Xbox's activity-feed empty response uses the string zero as its
    # exhausted cursor, not a cursor for another request.
    # https://github.com/XboxReplay/xboxlive-api/blob/master/__tests__/e2e.test.js
    if token in (None, '', '0') or (type(token) is int and token == 0):
        return None
    if not isinstance(token, str) or len(token) > 16384:
        raise StoriesError('cursor_invalid')
    return base_url + '&' + urlencode({'contToken': token})


async def investigate(client):
    body = await client.story_feed()
    report = {'realm_feed': {'http_status': 200, 'body': body}}
    urls = probe_urls(body)
    if urls is None:
        report['xbox_probes'] = {'state': 'skipped', 'reason': 'no_valid_club_post_reference'}
        return report
    try:
        client.config.authorize(client.principal)
        token = await client.authorization(client.principal, audience=XBOX_RP)
    except RealmsError as error:
        report['xbox_probes'] = {'state': 'authentication_failed', 'reason': error.category}
        return report
    except Exception:
        report['xbox_probes'] = {'state': 'authentication_failed'}
        return report
    for name, url, version in (('xbox_post', urls[0], None), ('club_feed', urls[1], '13')):
        try:
            client.config.authorize(client.principal)
            headers = {'Authorization': token.authorization.value,
                       'Accept': 'application/json', 'Accept-Language': 'en-US',
                       'Cache-Control': 'no-cache, no-store'}
            # The public direct-post example supplies no contract version.
            # Club activity feed implementations explicitly use version 13.
            if version:
                headers['x-xbl-contract-version'] = version
            async with asyncio.timeout(35):
                response = await client.transport.request('GET', url, headers=headers)
            entry = {'http_status': response.status}
            if response.status == 200:
                entry['body'] = response.body
            else:
                entry['state'] = 'request_rejected'
                if response.retry_after is not None:
                    entry['retry_after_seconds'] = response.retry_after
            report[name] = entry
        except HTTPFailure as error:
            report[name] = {'http_status': error.status, 'state': 'response_not_inspectable'}
        except RealmsError as error:
            report[name] = {'state': 'failed', 'reason': error.category}
        except Exception:
            report[name] = {'state': 'failed', 'reason': 'transport_or_response_failure'}
    return report
