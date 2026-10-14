import json
import re
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.prefs = json.loads((ROOT / 'privacy-prefs.json').read_text())

    def test_proxy_never_bypasses_tor(self):
        self.assertEqual(self.prefs['network.proxy.type'], 1)
        self.assertEqual(self.prefs['network.proxy.socks'], '127.0.0.1')
        self.assertEqual(self.prefs['network.proxy.socks_port'], 19050)
        self.assertTrue(self.prefs['network.proxy.socks_remote_dns'])
        self.assertEqual(self.prefs['network.proxy.no_proxies_on'], '')
        self.assertTrue(self.prefs['network.proxy.allow_hijacking_localhost'])
        self.assertFalse(self.prefs['network.proxy.allow_bypass'])
        self.assertNotIn('network.proxy.failover_direct', self.prefs)
        self.assertIn('--disable-proxy-direct-failover', (ROOT / 'scripts/apply-overlay.py').read_text())
        self.assertEqual(self.prefs['network.trr.mode'], 5)

    def test_non_tor_udp_transports_are_disabled(self):
        self.assertFalse(self.prefs['media.peerconnection.enabled'])
        self.assertFalse(self.prefs['network.http.http3.enable'])
        self.assertFalse(self.prefs['geo.enabled'])

    def test_native_requests_have_no_direct_failover(self):
        text = (ROOT / 'overlay/Reynard/Tor/TorNetwork.swift').read_text()
        self.assertIn('proxy.allowFailover = false', text)
        self.assertIn('configuration.proxyConfigurations = [proxy]', text)
        self.assertIn('URLSessionConfiguration.ephemeral', text)
        self.assertIn('rawValue: 19050', text)

    def test_bootstrap_needs_circuit_not_just_open_port(self):
        text = (ROOT / 'overlay/Reynard/Tor/TorService.m').read_text()
        self.assertIn('TBIOConnectionReady(valid, (int)progress', text)
        self.assertIn('status/circuit-established', text)
        self.assertIn('CookieAuthentication', (ROOT / 'README.md').read_text())
        self.assertNotIn('New Identity";', text)

    def test_dependencies_are_immutable(self):
        lock = json.loads((ROOT / 'upstream.lock.json').read_text())
        for key in ['commit', 'tor_framework_commit']:
            self.assertRegex(lock[key], r'^[0-9a-f]{40}$')
        self.assertIn(lock['tor_framework_commit'], (ROOT / 'Podfile').read_text())

    def test_hardening_does_not_rely_on_removed_prefs(self):
        self.assertNotIn('privacy.resistFingerprinting.letterboxing', self.prefs)
        self.assertNotIn('javascript.options.asmjs', self.prefs)
        self.assertTrue(self.prefs['network.dns.disabled'])
        self.assertTrue(self.prefs['network.lna.blocking'])
        self.assertFalse(self.prefs['network.lna.allow_top_level_navigation'])
        self.assertEqual(self.prefs['privacy.resistFingerprinting.exemptedDomains'], '')

    def test_active_content_and_disk_cache_restrictions(self):
        for key in ['javascript.options.ion', 'javascript.options.baselinejit',
                    'javascript.options.native_regexp', 'javascript.options.wasm',
                    'dom.webgpu.enabled', 'browser.cache.disk.enable',
                    'device.sensors.enabled', 'dom.battery.enabled',
                    'network.protocol-handler.external-default']:
            self.assertFalse(self.prefs[key], key)
        self.assertTrue(self.prefs['dom.security.https_only_mode'])
        self.assertFalse(self.prefs['dom.security.https_only_mode.upgrade_onion'])

if __name__ == '__main__':
    unittest.main()

