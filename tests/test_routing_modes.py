import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

class RoutingModeTests(unittest.TestCase):
    def test_mode_is_frozen_until_restart_and_defaults_to_tor(self):
        source = (ROOT / 'overlay/Reynard/Tor/TorPrivacy.swift').read_text()
        self.assertIn('static let activeRoutingMode = routingMode', source)
        self.assertIn('?? .always', source)
        self.assertIn('setenv("TBIO_ROUTING_MODE"', source)

    def test_unknown_native_context_is_blocked_not_guessed(self):
        source = (ROOT / 'overlay/Reynard/Tor/TorNetwork.swift').read_text()
        self.assertIn('mode == .privateOnly && isPrivate == nil', source)
        self.assertIn('[TorUnknownContextBlocker.self]', source)
        self.assertIn('proxy.allowFailover = false', source)

    def test_mode_change_requires_confirmation_and_warns_about_real_ip(self):
        source = (ROOT / 'overlay/Reynard/Tor/TorStatusViewController.swift').read_text()
        self.assertIn('실제 IP 노출', source)
        self.assertIn('preferredStyle: .alert', source)
        self.assertIn('다음 앱 실행', source)

    def test_never_does_not_start_tor_and_media_has_per_session_context(self):
        source = (ROOT / 'overlay/Reynard/Tor/TorService.m').read_text()
        self.assertIn('strcmp(mode, "never") == 0', source)
        source = (ROOT / 'scripts/apply-overlay.py').read_text()
        self.assertIn('TorNetwork.session(isPrivate: session.isPrivateMode)', source)
        self.assertIn('defaults.setBoolPref("network.dns.disabled"', source)
