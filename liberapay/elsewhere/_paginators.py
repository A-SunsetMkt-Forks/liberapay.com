"""Helper functions to handle pagination of API responses
"""

from functools import reduce
from operator import getitem
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit


def _modify_query(url, key, value):
    scheme, netloc, path, query, fragment = urlsplit(url)
    query = parse_qs(query)
    if value is None:
        query.pop(key, None)
    else:
        query[key] = [value]
    query = urlencode(query, doseq=True)
    return urlunsplit((scheme, netloc, path, query, fragment))


def _strip_prefix(prefix, s):
    """
    >>> str(_strip_prefix('https://api.example.com', 'https://api.example.com/foo/bar'))
    '/foo/bar'
    >>> _strip_prefix('https://api.example.org', 'https://api.example.com/baz')
    Traceback (most recent call last):
        ...
    ValueError: "https://api.example.org" is not a prefix of "https://api.example.com/baz"
    """
    i = len(prefix)
    if s[:i] == prefix:
        return s[i:]
    raise ValueError('"%s" is not a prefix of "%s"' % (prefix, s))


links_keys = {'prev', 'next', 'first', 'last'}


def query_param_paginator(param, **kw):
    # https://developers.google.com/+/api/#pagination
    page_key = kw.get('page')
    total_key = kw.get('total')
    links_keys_map = tuple((k, v) for k, v in kw.items() if k in links_keys)
    def f(self, response, parsed):
        url = _strip_prefix(self.api_url, response.request.url)
        links = {k: _modify_query(url, param, parsed[k2])
                 for k, k2 in links_keys_map
                 if parsed.get(k2)}
        if links.get('prev') and not links.get('first'):
            links['first'] = _modify_query(url, param, None)
        if page_key:
            page = parsed[page_key]
        else:
            lists = [a for a in parsed.values() if isinstance(a, list)]
            assert len(lists) == 1
            page = next(iter(lists))
        total_count = parsed.get(total_key, -1) if links else len(page)
        return page, total_count, links
    return f


def cursor_paginator(cursor_key, **kw):
    # https://dev.twitch.tv/docs/api/reference/
    if not isinstance(cursor_key, tuple):
        cursor_key = (cursor_key,)
    page_key = kw.get('page')
    total_key = kw.get('total')
    links_keys_map = tuple((k, v) for k, v in kw.items() if k in links_keys)
    def f(self, response, parsed):
        url = _strip_prefix(self.api_url, response.request.url)
        try:
            cursor = reduce(getitem, cursor_key, parsed)
        except KeyError:
            cursor = None
        if cursor:
            links = {k: _modify_query(url, k2, cursor) for k, k2 in links_keys_map}
        else:
            links = {}
        if page_key:
            page = parsed[page_key]
        else:
            lists = [a for a in parsed.values() if isinstance(a, list)]
            assert len(lists) == 1
            page = lists[0]
        total_count = parsed.get(total_key, -1) if links else len(page)
        return page, total_count, links
    return f


def header_links_paginator(total_header=None):
    # https://tools.ietf.org/html/rfc5988
    # https://developer.github.com/v3/#pagination
    def f(self, response, parsed):
        domain = urlsplit(response.request.url).hostname
        api_url = self.api_url.format(domain=domain)
        links = {k: _strip_prefix(api_url, v['url'])
                 for k, v in response.links.items()
                 if k in links_keys}
        total_count = -1 if links else len(parsed)
        if total_header and total_count == -1:
            try:
                total_count = int(response.headers.get('X-Total', None))
            except (ValueError, TypeError):
                pass
        return parsed, total_count, links
    return f


def keys_paginator(page_key, **kw):
    # https://confluence.atlassian.com/display/BITBUCKET/Version+2#Version2-Pagingthroughobjectcollections
    paging_key = kw.get('paging')
    total_key = kw.get('total')
    links_keys_map = tuple((k, kw.get(k, k)) for k in links_keys)
    def f(self, response, parsed):
        page = parsed[page_key]
        paging = parsed.get(paging_key, {}) if paging_key else parsed
        links = {k: _strip_prefix(self.api_url, paging[k2])
                 for k, k2 in links_keys_map
                 if paging.get(k2)}
        total_count = paging.get(total_key, -1) if links else len(page)
        return page, total_count, links
    return f
