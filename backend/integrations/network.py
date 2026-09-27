"""Public-only, DNS-pinned outbound connections for user-configured mail servers."""
import ipaddress
import imaplib
import smtplib
import ssl
import socket


class UnsafeMailServer(ValueError):
    """A mail server name resolves to an address unsuitable for public egress."""


def _is_public_unicast(address):
    return address.is_global and not (
        address.is_private or address.is_loopback or address.is_link_local
        or address.is_multicast or address.is_reserved or address.is_unspecified
    )


def public_mail_server_addresses(host, port):
    if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
        raise UnsafeMailServer('Mail server port must be between 1 and 65535.')
    if not isinstance(host, str) or not host or host != host.strip():
        raise UnsafeMailServer('Enter a valid public mail server hostname.')

    candidate = host.rstrip('.')
    try:
        literal = ipaddress.ip_address(candidate.strip('[]'))
    except ValueError:
        if any(char in candidate for char in ('/', '\\', '@', ':', '%')):
            raise UnsafeMailServer('Enter a hostname only, without a URL, port, or credentials.')
        try:
            hostname = candidate.encode('idna').decode('ascii')
            if len(hostname) > 253 or not hostname or any(
                not label or len(label) > 63 or label.startswith('-') or label.endswith('-')
                for label in hostname.split('.')
            ):
                raise ValueError
            records = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
        except (UnicodeError, ValueError, OSError, socket.gaierror) as exc:
            raise UnsafeMailServer('Mail server hostname could not be safely resolved.') from exc
        addresses = []
        for family, socktype, proto, canonname, sockaddr in records:
            if family not in (socket.AF_INET, socket.AF_INET6):
                raise UnsafeMailServer('Mail server resolved to an unsupported address.')
            try:
                ip = ipaddress.ip_address(sockaddr[0])
            except ValueError as exc:
                raise UnsafeMailServer('Mail server resolved to an invalid address.') from exc
            if not _is_public_unicast(ip):
                raise UnsafeMailServer('Mail server hostnames must resolve only to public IP addresses.')
            addresses.append((family, socktype, proto, sockaddr))
        if not addresses:
            raise UnsafeMailServer('Mail server hostname has no public IP addresses.')
        return hostname, addresses

    if not _is_public_unicast(literal):
        raise UnsafeMailServer('Mail server IP addresses must be public and globally routable.')
    candidate = str(literal)
    sockaddr = (candidate, port) if literal.version == 4 else (candidate, port, 0, 0)
    family = socket.AF_INET if literal.version == 4 else socket.AF_INET6
    return candidate, [(family, socket.SOCK_STREAM, socket.IPPROTO_TCP, sockaddr)]


def open_public_mail_socket(host, port, timeout=10):
    """Connect to a previously validated numeric address, avoiding a second DNS lookup."""
    hostname, addresses = public_mail_server_addresses(host, port)
    errors = []
    for family, socktype, proto, sockaddr in addresses:
        sock = socket.socket(family, socktype, proto)
        try:
            sock.settimeout(timeout)
            sock.connect(sockaddr)
            return hostname, sock
        except OSError as exc:
            errors.append(exc)
            sock.close()
    raise OSError(f'Unable to connect to public mail server {hostname}:{port}') from (errors[-1] if errors else None)


def validate_public_mail_server(host, port):
    public_mail_server_addresses(host, port)
    return host


class PublicSMTP(smtplib.SMTP):
    def _get_socket(self, host, port, timeout):
        normalized_host, sock = open_public_mail_socket(host, port, timeout)
        self._host = normalized_host
        return sock


class PublicSMTPSSL(smtplib.SMTP_SSL):
    def _get_socket(self, host, port, timeout):
        normalized_host, sock = open_public_mail_socket(host, port, timeout)
        self._host = normalized_host
        try:
            return self.context.wrap_socket(sock, server_hostname=normalized_host)
        except Exception:
            sock.close()
            raise


class PublicIMAP4SSL(imaplib.IMAP4_SSL):
    def __init__(self, host='', port=imaplib.IMAP4_SSL_PORT, timeout=10):
        super().__init__(host, port, ssl_context=ssl.create_default_context(), timeout=timeout)

    def _create_socket(self, timeout):
        hostname, sock = open_public_mail_socket(self.host, self.port, timeout)
        try:
            return self.ssl_context.wrap_socket(sock, server_hostname=hostname)
        except Exception:
            sock.close()
            raise


def connect_smtp(host, port, implicit_tls=False, timeout=10):
    connector = PublicSMTPSSL if implicit_tls else PublicSMTP
    return connector(host, port, timeout=timeout, context=ssl.create_default_context()) if implicit_tls else connector(host, port, timeout=timeout)
