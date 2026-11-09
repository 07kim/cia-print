import os
import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "setup_printer.sh"


class PrinterSetupTests(unittest.TestCase):
    def run_setup(self, *, registered=False, devices="", lpadmin_exit=0):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            calls = temp / "lpadmin-calls"

            lpstat = temp / "lpstat"
            lpstat.write_text(
                "#!/bin/zsh\n"
                "if [[ \"$1\" == \"-p\" ]]; then\n"
                f"  exit {0 if registered else 1}\n"
                "fi\n"
                "exit 0\n",
                encoding="utf-8",
            )
            lpinfo = temp / "lpinfo"
            lpinfo.write_text(
                f"#!/bin/zsh\n/usr/bin/printf '%s\\n' {shlex.quote(devices)}\n",
                encoding="utf-8",
            )
            lpadmin = temp / "lpadmin"
            lpadmin.write_text(
                "#!/bin/zsh\n"
                f"print -r -- \"$@\" >> {str(calls)!r}\n"
                f"exit {lpadmin_exit}\n",
                encoding="utf-8",
            )
            for path in (lpstat, lpinfo, lpadmin):
                path.chmod(0o755)

            env = os.environ.copy()
            env.update(
                {
                    "CIA_PRINT_LPSTAT_BIN": str(lpstat),
                    "CIA_PRINT_LPINFO_BIN": str(lpinfo),
                    "CIA_PRINT_LPADMIN_BIN": str(lpadmin),
                    "CIA_PRINT_DISCOVERY_ATTEMPTS": "1",
                }
            )
            result = subprocess.run(
                ["/bin/zsh", str(SCRIPT)],
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
            return result, calls.read_text(encoding="utf-8") if calls.exists() else ""

    def test_registered_queue_is_left_unchanged(self):
        result, calls = self.run_setup(registered=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(calls, "")
        self.assertIn("登録済み", result.stdout)

    def test_exact_model_is_registered_as_driverless_printer(self):
        uri = "dnssd://EPSON%20EW-M634T%20Series._ipp._tcp.local./?uuid=test"
        result, calls = self.run_setup(devices=f"network {uri}")
        self.assertEqual(result.returncode, 0)
        self.assertIn("-p EPSON_EW_M634T_Series", calls)
        self.assertIn(f"-v {uri}", calls)
        self.assertIn("-m everywhere", calls)

    def test_no_matching_device_does_not_register_another_printer(self):
        result, calls = self.run_setup(
            devices="network dnssd://Other%20Printer._ipp._tcp.local./"
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls, "")
        self.assertIn("自動検出できません", result.stdout)

    def test_multiple_candidates_are_not_selected_automatically(self):
        devices = "\n".join(
            [
                "network dnssd://EPSON%20EW-M634T%20Series._ipp._tcp.local./?uuid=one",
                "network dnssd://EPSON%20EW-M634T%20Series._ipp._tcp.local./?uuid=two",
            ]
        )
        result, calls = self.run_setup(devices=devices)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls, "")
        self.assertIn("候補が複数", result.stdout)

    def test_unresolvable_bare_ipp_host_is_not_registered(self):
        result, calls = self.run_setup(
            devices="network ipp://EW-M634T:631/ipp/print"
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls, "")
        self.assertIn("自動検出できません", result.stdout)

    def test_bonjour_candidate_is_preferred_over_direct_ipp(self):
        bonjour = "dnssd://EPSON%20EW-M634T%20Series._ipp._tcp.local./?uuid=one"
        devices = "\n".join(
            [
                "network ipp://192.168.75.45:631/ipp/print",
                f"network {bonjour}",
            ]
        )
        result, calls = self.run_setup(devices=devices)
        self.assertEqual(result.returncode, 0)
        self.assertIn(f"-v {bonjour}", calls)
        self.assertNotIn("192.168.75.45", calls)


if __name__ == "__main__":
    unittest.main()
