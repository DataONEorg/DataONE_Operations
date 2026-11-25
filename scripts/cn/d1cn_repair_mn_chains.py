#!/usr/bin/env python3
"""Find MN version-chain links that differ on the CN and re-synchronize them."""

import argparse
from collections import deque
from dataclasses import dataclass
import logging
from pathlib import Path
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen
from uuid import uuid4
import xml.etree.ElementTree as ET


ENV_BASE_URL = {
    "dev": "https://cn-dev.test.dataone.org/cn",
    "stage": "https://cn-stage.test.dataone.org/cn",
    "sandbox": "https://cn-sandbox.test.dataone.org/cn",
    "prod": "https://cn.dataone.org/cn",
}
FIELDS = ("obsoletes", "obsoletedBy", "seriesId")
LOG = logging.getLogger("mn_chains")


class ScanError(Exception):
    pass


def local_name(tag):
    return tag.rsplit("}", 1)[-1]


def children(element, name):
    return [child for child in element if local_name(child.tag) == name]


def field(element, name, required=False):
    matches = children(element, name)
    if len(matches) > 1 or (required and (not matches or not matches[0].text)):
        raise ScanError("invalid or missing {}".format(name))
    return matches[0].text if matches and matches[0].text else ""


@dataclass(frozen=True)
class Links:
    obsoletes: str
    obsoletedBy: str
    seriesId: str


class Client:
    def __init__(self, base_url, token):
        try:
            parts = urlsplit(base_url)
            valid = (parts.scheme in ("http", "https") and parts.hostname
                     and parts.username is None and parts.password is None
                     and not parts.query and not parts.fragment and parts.port != 0)
        except ValueError as exc:
            raise ScanError("invalid base URL: {!r}".format(base_url)) from exc
        if not valid:
            raise ScanError("invalid base URL: {!r}".format(base_url))
        self.base_url = base_url.rstrip("/")
        self.token = token

    def request(self, path, data=None, content_type=None, missing_ok=False):
        headers = {"Authorization": "Bearer " + self.token}
        if content_type:
            headers["Content-Type"] = content_type
        request = Request(self.base_url + path, data=data, headers=headers)
        try:
            with urlopen(request, timeout=30) as response:
                return response.read()
        except HTTPError as exc:
            if missing_ok and exc.code == 404:
                return None
            raise ScanError("HTTP {} for {}".format(exc.code, path)) from exc
        except (URLError, OSError) as exc:
            raise ScanError("request failed for {}: {}".format(path, exc)) from exc

    def xml(self, path, missing_ok=False):
        data = self.request(path, missing_ok=missing_ok)
        if data is None:
            return None
        try:
            return ET.fromstring(data)
        except ET.ParseError as exc:
            raise ScanError("invalid XML for {}: {}".format(path, exc)) from exc

    def metadata(self, pid, missing_ok=False):
        root = self.xml("/v2/meta/" + quote(pid, safe=""), missing_ok)
        if root is None:
            return None
        if local_name(root.tag) != "systemMetadata":
            raise ScanError("invalid systemMetadata for {!r}".format(pid))
        identifier = field(root, "identifier", required=True)
        if identifier != pid:
            raise ScanError("metadata for {!r} returned identifier {!r}".format(pid, identifier))
        return Links(*(field(root, name) for name in FIELDS))

    def synchronize(self, pid):
        boundary = "dataone-" + uuid4().hex
        data = (
            "--{}\r\nContent-Disposition: form-data; name=\"pid\"\r\n"
            "Content-Type: text/plain; charset=utf-8\r\n\r\n{}\r\n--{}--\r\n"
        ).format(boundary, pid, boundary).encode("utf-8")
        self.request("/v2/synchronize", data, "multipart/form-data; boundary=" + boundary)


def node_url(cn, node_id):
    root = cn.xml("/v2/node")
    if local_name(root.tag) != "nodeList":
        raise ScanError("invalid node list")
    matches = [
        node for node in root.iter()
        if local_name(node.tag) == "node" and field(node, "identifier") == node_id
    ]
    if len(matches) != 1:
        raise ScanError("expected one node matching {!r}, found {}".format(node_id, len(matches)))
    return field(matches[0], "baseURL", required=True)


def list_pids(mn, page_size):
    start = 0
    expected_total = None
    pids = []
    seen = set()
    while True:
        path = "/v2/object?" + urlencode({"start": start, "count": page_size})
        root = mn.xml(path)
        if local_name(root.tag) != "objectList":
            raise ScanError("invalid object list at start {}".format(start))
        try:
            total = int(root.attrib["total"])
            response_start = int(root.attrib["start"])
            count = int(root.attrib["count"])
        except (KeyError, ValueError) as exc:
            raise ScanError("invalid pagination at start {}".format(start)) from exc
        objects = children(root, "objectInfo")
        if (total < 0 or response_start != start or count != len(objects)
                or count < 0 or start + count > total
                or (expected_total is not None and total != expected_total)
                or (count == 0 and start < total)):
            raise ScanError("inconsistent object list at start {}".format(start))
        expected_total = total
        for obj in objects:
            pid = field(obj, "identifier", required=True)
            if pid in seen:
                raise ScanError("duplicate PID in object list: {!r}".format(pid))
            seen.add(pid)
            pids.append(pid)
        start += count
        LOG.info("Listed %d/%d MN objects", start, total)
        if start == total:
            return pids


def discover(mn, pids):
    queue = deque(pids)
    queued = set(pids)
    metadata = {}
    linked = set()
    errors = 0
    while queue:
        pid = queue.popleft()
        try:
            links = mn.metadata(pid)
        except ScanError as exc:
            LOG.error("MN metadata for %r: %s", pid, exc)
            errors += 1
            continue
        metadata[pid] = links
        for neighbor in (links.obsoletes, links.obsoletedBy):
            if neighbor:
                linked.update((pid, neighbor))
                if neighbor not in queued:
                    queued.add(neighbor)
                    queue.append(neighbor)
    return metadata, linked, errors


def mismatch(mn_links, cn_links):
    if cn_links is None:
        return "missing on CN"
    return "; ".join(
        "{} MN={!r} CN={!r}".format(name, getattr(mn_links, name), getattr(cn_links, name))
        for name in FIELDS if getattr(mn_links, name) != getattr(cn_links, name)
    )


def scan(mn, cn, page_size, do_sync, wait):
    pids = list_pids(mn, page_size)
    metadata, linked, errors = discover(mn, pids)
    LOG.info("Discovered %d linked PIDs from %d listed MN objects", len(linked), len(pids))
    broken = {}
    for pid in sorted(linked):
        if pid not in metadata:
            continue
        try:
            reason = mismatch(metadata[pid], cn.metadata(pid, missing_ok=True))
        except ScanError as exc:
            LOG.error("CN metadata for %r: %s", pid, exc)
            errors += 1
            continue
        if reason:
            broken[pid] = reason
            LOG.warning("Broken %r: %s", pid, reason)

    if do_sync:
        for pid in broken:
            try:
                cn.synchronize(pid)
                LOG.info("Requested synchronization for %r", pid)
            except ScanError as exc:
                LOG.error("Synchronization for %r failed: %s", pid, exc)
                errors += 1
        for pid in list(broken):
            deadline = time.monotonic() + wait
            while True:
                try:
                    reason = mismatch(metadata[pid], cn.metadata(pid, missing_ok=True))
                except ScanError as exc:
                    LOG.error("CN metadata for %r during verification: %s", pid, exc)
                    errors += 1
                    break
                if not reason:
                    del broken[pid]
                    LOG.info("Fixed by synchronization: %r", pid)
                    break
                broken[pid] = reason
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                time.sleep(min(10, remaining))

    for pid, reason in broken.items():
        LOG.warning("Unresolved %r: %s", pid, reason)
    LOG.info("Scan complete: %d unresolved, %d errors", len(broken), errors)
    return 2 if errors else 1 if broken else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mn_id", help="Full MN node ID, e.g. urn:node:UCSB1")
    parser.add_argument("--env", choices=ENV_BASE_URL, default="prod")
    parser.add_argument("--mn-base-url", help="Override MN URL from the CN node list")
    parser.add_argument("--cn-base-url", help="Override CN URL from --env")
    parser.add_argument("--page-size", type=int, default=7000)
    parser.add_argument("--wait", type=int, default=60, help="Seconds to poll each PID after synchronization")
    parser.add_argument("--no-sync", action="store_true", help="Report discrepancies without synchronizing")
    args = parser.parse_args()
    if args.page_size <= 0 or args.wait < 0:
        parser.error("--page-size must be positive and --wait must be non-negative")
    node_name = args.mn_id.rsplit(":", 1)[-1]
    if not node_name or node_name in (".", "..") or "/" in node_name or "\\" in node_name:
        parser.error("invalid MN node ID")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(message)s")
    token_file = Path.home() / "force_sync" / "token" / node_name
    try:
        token = token_file.read_text().strip()
        if not token:
            raise ScanError("token file is empty: {}".format(token_file))
        cn = Client(args.cn_base_url or ENV_BASE_URL[args.env], token)
        mn_url = args.mn_base_url or node_url(cn, args.mn_id)
        LOG.info("MN base URL = %s; CN base URL = %s", mn_url, cn.base_url)
        return scan(Client(mn_url, token), cn, args.page_size, not args.no_sync, args.wait)
    except (OSError, ScanError) as exc:
        LOG.error("%s", exc)
        return 2


if __name__ == "__main__":
    sys.exit(main())
