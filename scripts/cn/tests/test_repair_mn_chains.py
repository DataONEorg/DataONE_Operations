import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlsplit
from xml.etree import ElementTree as ET


SCRIPT = Path(__file__).resolve().parents[1] / "d1cn_repair_mn_chains.py"


def xml(tag, **fields):
    root = ET.Element(tag)
    for key, value in fields.items():
        if value:
            ET.SubElement(root, key).text = value
    return ET.tostring(root)


class FixtureServer(ThreadingHTTPServer):
    def __init__(self):
        super().__init__(("127.0.0.1", 0), Handler)
        self.pids = []
        self.mn = {}
        self.cn = {}
        self.posts = []
        self.gets = []
        self.bad_page = False
        self.sync_fixes = False
        self.sync_status = 200


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def reply(self, status, data=b""):
        self.send_response(status)
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlsplit(self.path)
        self.server.gets.append(self.path)
        if path.path == "/cn/v2/node":
            base = "http://127.0.0.1:{}".format(self.server.server_port)
            self.reply(200, ("<nodeList><node><identifier>urn:node:TEST</identifier>"
                             "<baseURL>{}/mn</baseURL></node></nodeList>".format(base)).encode())
        elif path.path == "/mn/v2/object":
            query = parse_qs(path.query)
            start = int(query["start"][0])
            count = min(int(query["count"][0]), 1)
            selected = self.server.pids[start:start + count]
            root = ET.Element("objectList", total=str(len(self.server.pids)),
                              start=str(start), count=str(len(selected)))
            for pid in selected:
                obj = ET.SubElement(root, "objectInfo")
                ET.SubElement(obj, "identifier").text = pid
            if self.server.bad_page and start:
                root.set("count", "0")
            self.reply(200, ET.tostring(root))
        elif "/v2/meta/" in path.path:
            side, pid = path.path.strip("/").split("/v2/meta/", 1)
            pid = unquote(pid)
            data = getattr(self.server, side).get(pid)
            if isinstance(data, int):
                self.reply(data)
            elif data is None:
                self.reply(404)
            else:
                self.reply(200, xml("systemMetadata", identifier=pid, **data))
        else:
            self.reply(404)

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        pid = body.split(b"\r\n\r\n", 1)[1].split(b"\r\n--", 1)[0].decode()
        self.server.posts.append(pid)
        if self.server.sync_fixes:
            self.server.cn[pid] = self.server.mn[pid]
        self.reply(self.server.sync_status)


class RepairChainsTest(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.TemporaryDirectory()
        token = Path(self.home.name) / "force_sync/token/TEST"
        token.parent.mkdir(parents=True)
        token.write_text("test-token")
        self.server = FixtureServer()
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.start()
        self.base = "http://127.0.0.1:{}".format(self.server.server_port)

    def tearDown(self):
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()
        self.home.cleanup()

    def run_script(self, *args):
        env = dict(os.environ, HOME=self.home.name)
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--cn-base-url", self.base + "/cn",
             "--page-size", "2", "--wait", "0", *args, "urn:node:TEST"],
            env=env, text=True, capture_output=True, timeout=10,
        )

    def test_paginated_scan_reports_only_linked_mismatches_without_sync(self):
        self.server.pids = ["alone", "old / α", "new"]
        self.server.mn = {
            "alone": {},
            "old / α": {"obsoletedBy": "new", "seriesId": "s"},
            "new": {"obsoletes": "old / α", "seriesId": "s"},
        }
        self.server.cn = {"old / α": {"seriesId": "s"}, "new": self.server.mn["new"]}
        result = self.run_script("--no-sync")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("obsoletedBy", result.stderr)
        self.assertEqual(self.server.posts, [])
        self.assertEqual(sum("/cn/v2/meta/" in path for path in self.server.gets), 2)
        self.assertTrue(any("start=2" in path for path in self.server.gets))

    def test_syncs_missing_and_incorrect_links_once_then_verifies(self):
        self.server.pids = ["a", "b", "c"]
        self.server.mn = {
            "a": {"obsoletedBy": "b"},
            "b": {"obsoletes": "a", "obsoletedBy": "c"},
            "c": {"obsoletes": "b"},
        }
        self.server.cn = {"a": {}, "c": self.server.mn["c"]}
        self.server.sync_fixes = True
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.server.posts, ["a", "b"])
        self.assertIn("0 unresolved, 0 errors", result.stderr)

    def test_failed_or_unchanged_sync_stays_unresolved(self):
        self.server.pids = ["a"]
        self.server.mn = {"a": {"obsoletedBy": "b"}, "b": {"obsoletes": "a"}}
        self.server.cn = {"a": {}, "b": self.server.mn["b"]}
        result = self.run_script()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(self.server.posts, ["a"])
        self.assertIn("Unresolved 'a'", result.stderr)

    def test_missing_mn_neighbor_and_cn_error_are_not_repaired(self):
        self.server.pids = ["a", "b"]
        self.server.mn = {"a": {"obsoletedBy": "missing"}, "b": {"obsoletes": "a"}}
        self.server.cn = {"a": 503, "b": self.server.mn["b"]}
        result = self.run_script()
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("MN metadata for 'missing'", result.stderr)
        self.assertIn("CN metadata for 'a'", result.stderr)
        self.assertEqual(self.server.posts, [])

    def test_incomplete_listing_fails_before_any_repair(self):
        self.server.pids = ["a", "b"]
        self.server.bad_page = True
        result = self.run_script()
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("inconsistent object list", result.stderr)
        self.assertEqual(self.server.posts, [])
        self.assertFalse(any("/v2/meta/" in path for path in self.server.gets))

    def test_cycles_and_incoming_only_links_are_compared_once(self):
        self.server.pids = ["a", "b", "c"]
        self.server.mn = {
            "a": {"obsoletedBy": "b"},
            "b": {"obsoletedBy": "a"},
            "c": {"obsoletes": "b"},
        }
        self.server.cn = dict(self.server.mn)
        result = self.run_script("--no-sync")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(sum("/cn/v2/meta/" in path for path in self.server.gets), 3)

    def test_synchronization_failure_is_an_error(self):
        self.server.pids = ["a"]
        self.server.mn = {"a": {"obsoletedBy": "b"}, "b": {}}
        self.server.cn = {"a": {}, "b": {}}
        self.server.sync_status = 500
        result = self.run_script()
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("Synchronization for 'a' failed", result.stderr)
        self.assertIn("Unresolved 'a'", result.stderr)


if __name__ == "__main__":
    unittest.main()
