import hashlib
import ipaddress
import json
import socket
import ssl
import http.client
from dataclasses import dataclass
from urllib.parse import urlsplit
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .config import settings


@dataclass(frozen=True)
class Principal:
    tenant: str
    subject: str
    groups: tuple[str, ...] = ()

    @property
    def readers(self):
        return [f'user:{self.subject}', *[f'group:{g}' for g in self.groups]]


def authenticate(credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer())):
    digest = hashlib.sha256(credentials.credentials.encode()).hexdigest()
    identity = json.loads(settings().auth_tokens).get(digest)
    if not identity:
        raise HTTPException(401, 'Invalid credentials')
    return Principal(identity['tenant'], identity['subject'], tuple(identity.get('groups', [])))


def public_destination(url: str):
    parts = urlsplit(url)
    if parts.scheme != 'https' or not parts.hostname or parts.username or parts.password or parts.port not in (None, 443):
        raise ValueError('Only public HTTPS URLs on port 443 without credentials are accepted')
    addresses = socket.getaddrinfo(parts.hostname, 443, type=socket.SOCK_STREAM)
    ips = [x[4][0] for x in addresses]
    if not ips or any(not ipaddress.ip_address(ip).is_global for ip in ips):
        raise ValueError('Destination is not public')
    return parts, ips[0]


class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, hostname, ip):
        super().__init__(hostname, timeout=10, context=ssl.create_default_context())
        self.ip = ip

    def connect(self):
        sock = socket.create_connection((self.ip, 443), self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


def fetch_url(url: str, maximum: int):
    parts, ip = public_destination(url)
    connection = PinnedHTTPS(parts.hostname, ip)
    try:
        path = parts.path or '/'
        if parts.query:
            path += '?' + parts.query
        connection.request('GET', path, headers={'User-Agent': 'UniversalKnowledge/0.1', 'Accept-Encoding': 'identity'})
        response = connection.getresponse()
        if response.status != 200:
            raise ValueError('Website request failed; redirects are intentionally rejected')
        if response.getheader('Content-Encoding', 'identity') != 'identity':
            raise ValueError('Compressed website responses are unsupported')
        data = response.read(maximum + 1)
        if len(data) > maximum:
            raise ValueError('Website exceeds size limit')
        content_type = response.getheader('Content-Type', '').split(';')[0]
        if content_type not in {'text/html', 'text/plain', 'text/markdown'}:
            raise ValueError('Unsupported website content type')
        return data, '.html' if content_type == 'text/html' else '.txt'
    finally:
        connection.close()
