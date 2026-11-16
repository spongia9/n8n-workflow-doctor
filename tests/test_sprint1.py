"""Synthetic regressions for parsing, rules, batch safety and CLI contracts."""
from __future__ import annotations

import copy
import io
import json
import stat
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile
from contextlib import redirect_stderr, redirect_stdout
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from workflow_doctor.cli import main
from workflow_doctor.inputs import read_file
from workflow_doctor.models import InputError, ScanLimits
from workflow_doctor.parser import parse_json
from workflow_doctor.scanner import scan_bytes, scan_file, scan_object, scan_path

FIXTURES = Path(__file__).parent / "fixtures"


def workflow():
    return json.loads((FIXTURES / "valid.json").read_text(encoding="utf-8"))


def encoded(data=None):
    return json.dumps(workflow() if data is None else data).encode("utf-8")


def link(node="HTTP Request", index=0, kind="main"):
    return {"node": node, "type": kind, "index": index}


class RulesAndParserTests(unittest.TestCase):
    def test_json_syntax_has_line_and_column_without_source_text(self):
        result = scan_bytes(b'{\n"password": "synthetic-private-value",\n"nodes": [}')
        finding = result["findings"][0]
        self.assertEqual(finding["rule_id"], "WF001")
        self.assertEqual(finding["location_details"]["line"], 3)
        self.assertGreater(finding["location_details"]["column"], 1)
        self.assertNotIn("synthetic-private-value", json.dumps(result))

    def test_utf8_bom_supported(self):
        self.assertEqual(scan_bytes(b"\xef\xbb\xbf" + encoded())["findings"], [])

    def test_invalid_encoding_is_finding(self):
        self.assertEqual(scan_bytes(b"\xff\xfe")["findings"][0]["rule_id"], "WF001")

    def test_duplicate_keys_and_nonstandard_numbers_rejected(self):
        for raw in (b'{"nodes": [], "nodes": [], "connections": {}}',
                    b'{"nodes": [], "connections": {}, "value": NaN}',
                    b'{"nodes": [], "connections": {}, "value": Infinity}',
                    b'{"nodes": [], "connections": {}, "value": -Infinity}',
                    b'{"nodes": [], "connections": {}, "value": 1e999}'):
            with self.subTest(raw=raw):
                self.assertEqual(scan_bytes(raw)["findings"][0]["rule_id"], "WF001")

    def test_depth_limit_and_quoted_brackets(self):
        limits = ScanLimits(max_json_depth=3)
        self.assertEqual(scan_bytes(b"[[[[]]]]", limits=limits)["findings"][0]["rule_id"], "WF001")
        data = {"nodes": [], "connections": {}, "extra": '["\\[]'}
        self.assertEqual(scan_bytes(encoded(data), limits=limits)["findings"], [])

    def test_valid_non_workflow_json_recognized(self):
        for value in (None, True, 42, "hello", [], [{"nodes": [], "connections": {}}], {"other": 1}):
            with self.subTest(value=value):
                raw = json.dumps(value).encode()
                self.assertTrue(all(f["rule_id"] == "WF002" for f in scan_bytes(raw)["findings"]))

    def test_missing_and_malformed_required_fields(self):
        for key, value in (("nodes", None), ("nodes", {}), ("connections", None), ("connections", [])):
            for missing in (False, True):
                data = workflow()
                if missing:
                    data.pop(key)
                else:
                    data[key] = value
                with self.subTest(key=key, value=value, missing=missing):
                    self.assertIn("$." + key, [f.location for f in scan_object(data)])

    def test_node_properties_missing_and_wrong_types(self):
        invalid = {"id": [None, "", " ", 3, []], "name": [None, "", " ", False, {}],
                   "type": [None, "", 3], "typeVersion": [None, True, 0, -1, "1", float("inf")],
                   "position": [None, [], [1], [1, 2, 3], [True, 2], [1, float("nan")]],
                   "parameters": [None, [], "secret"]}
        for key, values in invalid.items():
            for value in values:
                data = workflow()
                data["nodes"][0][key] = value
                with self.subTest(key=key, value=value):
                    self.assertIn(f"$.nodes[0].{key}", [f.location for f in scan_object(data)])
            data = workflow()
            data["nodes"][0].pop(key)
            self.assertIn(f"$.nodes[0].{key}", [f.location for f in scan_object(data)])

    def test_non_object_node(self):
        data = workflow()
        data["nodes"].append("not a node")
        self.assertIn("$.nodes[2]", [f.location for f in scan_object(data)])

    def test_duplicate_ids_and_names_located(self):
        data = workflow()
        data["nodes"][1]["id"] = data["nodes"][0]["id"]
        data["nodes"][1]["name"] = data["nodes"][0]["name"]
        findings = {f.rule_id: f for f in scan_object(data)}
        self.assertEqual(findings["WF003"].location, "$.nodes[1].id")
        self.assertEqual(findings["WF004"].location, "$.nodes[1].name")

    def test_multibranch_null_ports_fanout_and_input_indexes(self):
        data = workflow()
        data["connections"] = {"Manual Trigger": {"main": [None, [], [link(), link(index=3)], [link(index=8)]]}}
        self.assertEqual(scan_object(data), [])

    def test_unknown_node_and_connection_types_are_compatible_with_structure(self):
        data = workflow()
        data["nodes"][0]["type"] = "community.futureNode"
        data["connections"] = {"Manual Trigger": {"future_type": [[link(kind="future_input")]], "ai_tool": [[]]}}
        result = scan_bytes(encoded(data))
        self.assertEqual(result["findings"], [])
        self.assertEqual(result["compatibility"], "unknown")

    def test_invalid_connection_containers(self):
        for connections in ({"Manual Trigger": []}, {"Manual Trigger": {"main": {}}},
                            {"Manual Trigger": {"main": [3]}}, {"Manual Trigger": {"main": [[None]]}},
                            {"Manual Trigger": {"": [[]]}}):
            data = workflow()
            data["connections"] = connections
            self.assertIn("WF002", [f.rule_id for f in scan_object(data)])

    def test_invalid_link_fields(self):
        for field, values in {"node": [None, "", " ", 42, []],
                              "type": [None, "", True, []],
                              "index": [None, True, -1, 0.5, "0"]}.items():
            for value in values:
                data = workflow()
                data["connections"]["Manual Trigger"]["main"][0][0][field] = value
                with self.subTest(field=field, value=value):
                    self.assertTrue(any(f.rule_id == "WF002" and f.location.endswith("." + field)
                                        for f in scan_object(data)))
            data = workflow()
            del data["connections"]["Manual Trigger"]["main"][0][0][field]
            self.assertIn("WF002", [f.rule_id for f in scan_object(data)])

    def test_dangling_source_and_target_on_later_port(self):
        data = workflow()
        data["connections"] = {"absent": {"main": [[], [link("also absent")]]}}
        findings = [f for f in scan_object(data) if f.rule_id == "WF005"]
        self.assertEqual(len(findings), 2)
        self.assertEqual(findings[1].location_details,
                         {"source_index": 0, "connection_type_index": 0, "output_index": 1, "link_index": 0})

    def test_all_findings_have_rule_severity_reason_location_and_suggestion(self):
        data = workflow()
        data["nodes"][1] = copy.deepcopy(data["nodes"][0])
        data["nodes"].append(None)
        findings = scan_bytes(encoded(data))["findings"] + scan_bytes(b"[")["findings"]
        self.assertEqual({f["rule_id"] for f in findings}, {"WF001", "WF002", "WF003", "WF004", "WF005"})
        for finding in findings:
            for key in ("rule_id", "severity", "message", "location", "suggestion"):
                self.assertTrue(finding[key])

    def test_unknown_fields_and_objects_not_modified(self):
        data = workflow()
        data["future"] = {"opaque": [False, {"any": "value"}]}
        data["nodes"][0]["future"] = [1, 2]
        data["connections"]["Manual Trigger"]["main"][0][0]["future"] = {"x": 1}
        before = copy.deepcopy(data)
        self.assertEqual(scan_object(data), [])
        self.assertEqual(data, before)
        decoded, findings = parse_json(encoded(data), ScanLimits())
        self.assertEqual(findings, [])
        self.assertEqual(decoded, before)

    def test_optional_workflow_metadata(self):
        self.assertEqual(scan_object({"nodes": [], "connections": {}}), [])
        for key, value in (("name", 1), ("name", ""), ("settings", [])):
            data = workflow()
            data[key] = value
            self.assertIn("$." + key, [f.location for f in scan_object(data)])

    def test_sensitive_values_and_connection_keys_never_in_report(self):
        secret = "synthetic-secret-NEVER-ECHO"
        data = workflow()
        data["name"] = secret
        data["nodes"][0].update(name=secret, id=secret, parameters={"password": secret},
                                credentials={"httpHeaderAuth": {"name": secret, "token": secret}})
        data["connections"] = {secret: {secret: [[link(secret + "-absent", kind=secret)]]}}
        self.assertNotIn(secret, json.dumps(scan_bytes(encoded(data))))

    def test_limits_require_positive_integers(self):
        for field in vars(ScanLimits()):
            for value in (0, -1, True, "1"):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    ScanLimits(**{field: value})

    def test_scan_bytes_enforces_size(self):
        with self.assertRaises(InputError):
            scan_bytes(encoded(), limits=ScanLimits(max_file_bytes=1))

    def test_integer_length_is_bounded_before_conversion(self):
        result = scan_bytes(b'{"value": ' + b"9" * 1001 + b'}')
        self.assertEqual(result["findings"][0]["rule_id"], "WF001")
        self.assertIn("1000-digit", result["findings"][0]["message"])

    def test_connection_ordinals_resolve_to_original_member(self):
        data = workflow()
        data["connections"] = {"Manual Trigger": {"main": [[]]},
                               "HTTP Request": {"ai_tool": [[]], "main": [[], [], [link(), link("missing")]]}}
        finding = next(f for f in scan_object(data) if f.rule_id == "WF005")
        pos = finding.location_details
        source = list(data["connections"].values())[pos["source_index"]]
        ports = list(source.values())[pos["connection_type_index"]]
        target = ports[pos["output_index"]][pos["link_index"]]["node"]
        self.assertEqual(target, "missing")
        self.assertEqual(finding.location, "$.connections{source:1}{type:1}[2][1].node")

    def test_findings_limit_is_explicit_instead_of_silent_truncation(self):
        with self.assertRaises(InputError) as exc:
            scan_object({"nodes": [None, None], "connections": {}}, max_findings=1)
        self.assertEqual(exc.exception.code, "SCAN_FINDING_LIMIT")
        self.assertEqual(len(scan_object({"nodes": [None], "connections": {}}, max_findings=1)), 1)
        with self.assertRaises(ValueError):
            scan_object({}, max_findings=0)


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def archive(self, entries=None, compression=zipfile.ZIP_DEFLATED):
        path = self.root / "batch.zip"
        with zipfile.ZipFile(path, "w", compression=compression) as archive:
            for name, raw in (entries if entries is not None else [("one.json", encoded())]):
                archive.writestr(name, raw)
        return path

    def assert_error(self, report, code):
        self.assertFalse(report["complete"])
        self.assertEqual(report["results"], [])
        self.assertEqual(report["errors"][0]["code"], code)
        for key in ("severity", "location", "message", "suggestion"):
            self.assertTrue(report["errors"][0][key])

    def test_directory_case_insensitive_and_recursive(self):
        (self.root / "one.JSON").write_bytes(encoded())
        (self.root / "note.txt").write_text("ignored")
        nested = self.root / "nested"
        nested.mkdir()
        (nested / "two.json").write_bytes(b"{")
        self.assertEqual(scan_path(self.root)["file_count"], 1)
        result = scan_path(self.root, recursive=True)
        self.assertEqual(result["file_count"], 2)
        self.assertEqual(result["finding_count"], 1)

    def test_directory_count_file_and_total_limits(self):
        raw = encoded()
        for name in ("one.json", "two.json"):
            (self.root / name).write_bytes(raw)
        self.assert_error(scan_path(self.root, limits=ScanLimits(max_files=1)), "INPUT_FILE_COUNT")
        self.assert_error(scan_path(self.root, limits=ScanLimits(max_file_bytes=len(raw)-1)), "INPUT_FILE_TOO_LARGE")
        self.assert_error(scan_path(self.root, limits=ScanLimits(max_total_bytes=len(raw))), "INPUT_TOTAL_TOO_LARGE")

    def test_oversized_local_file_error_identifies_file(self):
        path = self.root / "one.json"
        path.write_bytes(encoded())
        result = scan_path(self.root, limits=ScanLimits(max_file_bytes=1))
        self.assertEqual(result["errors"][0]["file"], str(path))
        self.assertEqual(result["input"], str(self.root))

    def test_finding_limit_rejects_batch_without_partial_success(self):
        path = self.root / "file.json"
        path.write_bytes(encoded({"nodes": [None, None], "connections": {}}))
        self.assert_error(scan_path(path, limits=ScanLimits(max_findings_per_file=1)), "SCAN_FINDING_LIMIT")

    def test_directory_deterministic_order(self):
        for name in ("z.json", "a.json", "b.json"):
            (self.root / name).write_bytes(encoded())
        report = scan_path(self.root)
        self.assertEqual([Path(item["file"]).name for item in report["results"]], ["a.json", "b.json", "z.json"])

    def test_missing_empty_and_unsupported_input(self):
        self.assert_error(scan_path(self.root / "missing.json"), "INPUT_READ_ERROR")
        self.assert_error(scan_path(self.root), "INPUT_EMPTY")
        path = self.root / "file.txt"
        path.write_bytes(encoded())
        self.assert_error(scan_path(path), "INPUT_TYPE")

    def test_file_read_limit_checks_actual_bytes(self):
        path = self.root / "file.json"
        path.write_bytes(b"0123456789")
        with patch("workflow_doctor.inputs._regular_size", return_value=0), self.assertRaises(InputError):
            read_file(path, 4)

    def test_read_permission_failure_is_structured(self):
        path = self.root / "file.json"
        path.write_bytes(encoded())
        with patch("pathlib.Path.open", side_effect=PermissionError("synthetic-private-error")):
            report = scan_path(path)
        self.assert_error(report, "INPUT_READ_ERROR")
        self.assertNotIn("synthetic-private-error", json.dumps(report))

    def test_zip_multiple_workflows_nested_and_nonjson_skip(self):
        path = self.archive([("one.json", encoded()), ("nested/two.JSON", encoded()),
                             ("nested/", b""), ("run.py", b"raise RuntimeError('must not execute')")])
        with patch.object(zipfile.ZipFile, "extractall", side_effect=AssertionError("must not extract")):
            result = scan_path(path)
        self.assertEqual(result["file_count"], 2)
        self.assertEqual(result["finding_count"], 0)
        self.assertEqual(result["skipped_count"], 2)
        self.assertEqual({v["code"] for v in result["skipped"]}, {"ZIP_DIRECTORY", "ZIP_NON_JSON"})
        self.assertEqual(list(self.root.iterdir()), [path])

    def test_zip_invalid_json_does_not_hide_other_workflow(self):
        result = scan_path(self.archive([("good.json", encoded()), ("bad.json", b"{")]))
        self.assertTrue(result["complete"])
        self.assertEqual(result["file_count"], 2)
        self.assertEqual(result["results"][1]["findings"][0]["rule_id"], "WF001")

    def test_zip_non_workflow_data_is_finding(self):
        result = scan_path(self.archive([("data.json", b"42")]))
        self.assertEqual(result["results"][0]["findings"][0]["rule_id"], "WF002")

    def test_empty_and_only_nonjson_zip_retains_skip_reasons(self):
        self.assert_error(scan_path(self.archive([])), "INPUT_EMPTY")
        result = scan_path(self.archive([("note.txt", b"ignore")]))
        self.assert_error(result, "INPUT_EMPTY")
        self.assertEqual(result["skipped"][0]["code"], "ZIP_NON_JSON")

    def test_zip_signature_and_truncation(self):
        for raw in (b"not a zip", b"PK\x03\x04garbage", b"PK\x05\x06"):
            path = self.root / "bad.zip"
            path.write_bytes(raw)
            self.assert_error(scan_path(path), "ZIP_INVALID")
        path = self.archive()
        path.write_bytes(path.read_bytes()[:-12])
        self.assert_error(scan_path(path), "ZIP_INVALID")

    def test_zip_path_traversal_absolute_drive_and_null(self):
        for name in ("../escape.json", "dir/../../escape.json", "..\\escape.json", "/escape.json",
                     "C:/escape.json", "C:escape.json", "\\\\host\\share\\escape.json", "a/./b.json"):
            with self.subTest(name=name):
                result = scan_path(self.archive([("good.json", encoded()), (name, encoded())]))
                self.assert_error(result, "ZIP_UNSAFE_PATH")
                self.assertNotIn(name, json.dumps(result))
        path = self.archive([("evilX.json", encoded())], compression=zipfile.ZIP_STORED)
        path.write_bytes(path.read_bytes().replace(b"evilX.json", b"evil\x00.json"))
        self.assert_error(scan_path(path), "ZIP_UNSAFE_PATH")

    def test_zip_duplicate_and_case_colliding_names(self):
        path = self.archive([("one.json", encoded()), ("ONE.JSON", encoded())])
        self.assert_error(scan_path(path), "ZIP_DUPLICATE_PATH")

    def test_zip_symlink_rejected(self):
        info = zipfile.ZipInfo("link.json")
        info.create_system = 3
        info.external_attr = (0o120777 << 16)
        path = self.archive([(info, b"../target.json")])
        self.assert_error(scan_path(path), "ZIP_UNSAFE_TYPE")

    def test_zip_count_includes_nonjson_and_directory_entries(self):
        path = self.archive([("one.json", encoded()), ("dir/", b""), ("note.txt", b"x")])
        self.assert_error(scan_path(path, limits=ScanLimits(max_files=2)), "ZIP_FILE_COUNT")

    def test_zip_single_total_compressed_limits_and_exact_boundaries(self):
        raw = encoded()
        path = self.archive([("one.json", raw), ("two.json", raw)])
        self.assert_error(scan_path(path, limits=ScanLimits(max_file_bytes=len(raw)-1)), "ZIP_FILE_TOO_LARGE")
        self.assert_error(scan_path(path, limits=ScanLimits(max_total_bytes=2*len(raw)-1)), "ZIP_TOTAL_TOO_LARGE")
        self.assert_error(scan_path(path, limits=ScanLimits(max_archive_bytes=path.stat().st_size-1)), "ZIP_ARCHIVE_TOO_LARGE")
        result = scan_path(path, limits=ScanLimits(max_files=2, max_file_bytes=len(raw),
                          max_total_bytes=2*len(raw), max_archive_bytes=path.stat().st_size))
        self.assertEqual(result["error_count"], 0)

    def test_zip_nonjson_counts_toward_size_limits(self):
        raw = encoded()
        path = self.archive([("one.json", raw), ("not-json.bin", b"x" * (len(raw) + 1))])
        self.assert_error(scan_path(path, limits=ScanLimits(max_file_bytes=len(raw))), "ZIP_FILE_TOO_LARGE")
        self.assert_error(scan_path(path, limits=ScanLimits(max_total_bytes=2*len(raw))), "ZIP_TOTAL_TOO_LARGE")

    def test_zip_bomb_metadata_checked_before_member_read(self):
        path = self.archive([("bomb.json", b" " * 500_000)])
        self.assertLess(path.stat().st_size, 1000)
        with patch.object(zipfile.ZipFile, "open", side_effect=AssertionError("preflight must reject")):
            self.assert_error(scan_path(path, limits=ScanLimits(max_file_bytes=1000)), "ZIP_FILE_TOO_LARGE")

    def test_zip_actual_read_limit_and_size_mismatch(self):
        path = self.archive([("one.json", b"{}")])
        for raw, limit in ((b"x" * 21, 20), (b"x", 20)):
            with patch.object(zipfile.ZipFile, "open", return_value=io.BytesIO(raw)):
                self.assert_error(scan_path(path, limits=ScanLimits(max_file_bytes=limit)), "ZIP_SIZE_MISMATCH")

    def test_zip_crc_error_discards_partial_results(self):
        path = self.archive([("one.json", encoded()), ("two.json", encoded())], compression=zipfile.ZIP_STORED)
        raw = bytearray(path.read_bytes())
        offset = raw.find(encoded(), raw.find(encoded()) + 1)
        raw[offset] ^= 1
        path.write_bytes(raw)
        self.assert_error(scan_path(path), "ZIP_INVALID")

    def test_zip_encrypted_flag_rejected(self):
        path = self.archive()
        raw = bytearray(path.read_bytes())
        central = raw.index(b"PK\x01\x02")
        struct.pack_into("<H", raw, central + 8, 1)
        path.write_bytes(raw)
        self.assert_error(scan_path(path), "ZIP_ENCRYPTED")

    def test_zip_unsupported_compression_rejected(self):
        path = self.archive(compression=zipfile.ZIP_BZIP2)
        self.assert_error(scan_path(path), "ZIP_COMPRESSION")

    def test_file_and_zip_hashes_unchanged(self):
        path = self.root / "one.json"
        path.write_bytes(encoded())
        archive = self.archive()
        before = {p: sha256(p.read_bytes()).hexdigest() for p in (path, archive)}
        scan_path(self.root, recursive=True)
        scan_path(archive)
        self.assertEqual(before, {p: sha256(p.read_bytes()).hexdigest() for p in before})

    def test_no_execution_or_network_access(self):
        marker = self.root / "executed"
        data = workflow()
        data["nodes"][0]["type"] = "n8n-nodes-base.code"
        code = f"open({str(marker)!r}, 'w').write('executed')"
        data["nodes"][0]["parameters"] = {"jsCode": code, "url": "http://127.0.0.1/private"}
        path = self.archive([("code.json", encoded(data)), ("code.py", code.encode())])
        with patch("socket.socket", side_effect=AssertionError("network forbidden")), \
                patch("urllib.request.urlopen", side_effect=AssertionError("network forbidden")):
            result = scan_path(path)
        self.assertEqual(result["finding_count"], 0)
        self.assertFalse(marker.exists())

    def test_link_metadata_rejected_without_host_symlink_privileges(self):
        source = self.root / "one.json"
        source.write_bytes(encoded())
        for info in (SimpleNamespace(st_mode=stat.S_IFLNK),
                     SimpleNamespace(st_mode=stat.S_IFREG, st_file_attributes=0x400)):
            with patch("pathlib.Path.lstat", return_value=info):
                self.assert_error(scan_path(source), "INPUT_UNSAFE_TYPE")
        entry = SimpleNamespace(name="link.json", path=str(source),
                                stat=lambda **kwargs: SimpleNamespace(st_mode=stat.S_IFLNK))
        with patch("workflow_doctor.inputs.os.scandir") as entries:
            entries.return_value.__enter__.return_value = [entry]
            report = scan_path(self.root, recursive=True)
        self.assert_error(report, "INPUT_EMPTY")
        self.assertEqual(report["skipped_count"], 1)

    def test_special_json_file_in_directory_is_rejected(self):
        entry = SimpleNamespace(name="pipe.json", path=str(self.root / "pipe.json"),
                                stat=lambda **kwargs: SimpleNamespace(st_mode=stat.S_IFIFO))
        with patch("workflow_doctor.inputs.os.scandir") as entries:
            entries.return_value.__enter__.return_value = [entry]
            self.assert_error(scan_path(self.root), "INPUT_UNSAFE_TYPE")


class CliContractTests(unittest.TestCase):
    def invoke(self, args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(args)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_exit_codes_and_json_report(self):
        for filename, expected in (("valid.json", 0), ("missing_target.json", 1), ("invalid.json", 1), ("absent.json", 2)):
            with self.subTest(filename=filename):
                code, stdout, stderr = self.invoke(["scan", str(FIXTURES / filename), "--format", "json"])
                self.assertEqual(code, expected)
                self.assertEqual(stderr, "")
                self.assertIn("errors", json.loads(stdout))

    def test_text_contains_severity_location_and_suggestion(self):
        code, output, _ = self.invoke(["scan", str(FIXTURES / "missing_target.json")])
        self.assertEqual(code, 1)
        for value in ("WF005", "error", "$.connections", "Suggestion:", "compatibility is unknown"):
            self.assertIn(value, output)

    def test_json_and_text_export(self):
        with tempfile.TemporaryDirectory() as folder:
            for fmt in ("json", "text"):
                target = Path(folder) / ("report." + fmt)
                code, _, _ = self.invoke(["scan", str(FIXTURES / "valid.json"), "--format", fmt, "--output", str(target)])
                self.assertEqual(code, 0)
                content = target.read_text(encoding="utf-8")
                if fmt == "json":
                    self.assertEqual(json.loads(content)["file_count"], 1)
                else:
                    self.assertIn("Scanned 1 JSON file(s)", content)

    def test_output_cannot_overwrite_input_or_existing_report(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "input.json"
            path.write_bytes(encoded())
            before = path.read_bytes()
            code, _, stderr = self.invoke(["scan", str(path), "--format", "json", "--output", str(path)])
            self.assertEqual(code, 2)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(json.loads(stderr)["errors"][0]["code"], "OUTPUT_WRITE_ERROR")

    def test_output_failure_does_not_leak_exception(self):
        with patch("pathlib.Path.mkdir", side_effect=PermissionError("synthetic-private-error")):
            code, _, stderr = self.invoke(["scan", str(FIXTURES / "valid.json"), "--output", "report.json"])
        self.assertEqual(code, 2)
        self.assertNotIn("synthetic-private-error", stderr)

    def test_limit_flags_applied_and_invalid_arguments_exit_two(self):
        code, output, _ = self.invoke(["scan", str(FIXTURES / "valid.json"), "--max-file-bytes", "1", "--format", "json"])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(output)["errors"][0]["code"], "INPUT_FILE_TOO_LARGE")
        for invalid in ("0", "-1", "nonnumeric"):
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as exc:
                main(["scan", str(FIXTURES), "--max-files", invalid])
            self.assertEqual(exc.exception.code, 2)

    def test_module_entrypoint_in_subprocess(self):
        process = subprocess.run([sys.executable, "-m", "workflow_doctor", "scan",
                                  str(FIXTURES / "valid.json"), "--format", "json"],
                                 capture_output=True, text=True, check=False)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(json.loads(process.stdout)["file_count"], 1)

    def test_zip_and_recursive_directory_cli(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "nested").mkdir()
            (root / "one.json").write_bytes(encoded())
            (root / "nested" / "two.json").write_bytes(encoded())
            archive = root / "batch.zip"
            with zipfile.ZipFile(archive, "w") as bundle:
                bundle.writestr("one.json", encoded())
                bundle.writestr("nested/two.json", encoded())
            for target, extra in ((archive, []), (root, ["--recursive"])):
                code, stdout, _ = self.invoke(["scan", str(target), "--format", "json"] + extra)
                self.assertEqual(code, 0)
                self.assertEqual(json.loads(stdout)["file_count"], 2)

    def test_text_and_json_reports_omit_sensitive_content(self):
        secret = "synthetic-private-DO-NOT-PRINT"
        data = workflow()
        data["name"] = secret
        data["nodes"][0]["parameters"] = {"token": secret}
        data["connections"] = {secret: {secret: [[link(secret)]]}}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "batch.zip"
            with zipfile.ZipFile(path, "w") as bundle:
                bundle.writestr(secret + ".json", encoded(data))
                bundle.writestr(secret + ".txt", b"ignored")
            for fmt in ("json", "text"):
                code, stdout, stderr = self.invoke(["scan", str(path), "--format", fmt])
                self.assertEqual(code, 1)
                self.assertNotIn(secret, stdout + stderr)


if __name__ == "__main__":
    unittest.main()
