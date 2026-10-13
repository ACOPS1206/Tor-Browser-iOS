#!/usr/bin/env python3
"""Apply app-only privacy UI changes after apply-overlay.py; never modify Gecko."""
import sys
from pathlib import Path


def replace(path, before, after):
    text = path.read_text()
    if text.count(before) != 1:
        raise RuntimeError(f'{path}: expected exactly one privacy UI anchor: {before!r}')
    path.write_text(text.replace(before, after))


def apply(target):
    app = target / 'browser/Reynard'
    settings = app / 'Client/Interface/Library/Settings/SettingsViewController.swift'
    replace(settings,
        '        navigationItem.rightBarButtonItem = UIBarButtonItem(title: "Tor", style: .plain, target: self, action: #selector(showEmbeddedTor))',
        '        torPrivacySection.didChange = { [weak self] in self?.tableView.reloadData() }')
    replace(settings, '    private let privacySection = PrivacySettingsSection()',
        '    private let privacySection = PrivacySettingsSection()\n    private let torPrivacySection = TorPrivacySettingsSection()')
    replace(settings, 'return privacySection.rowCount', 'return torPrivacySection.rowCount + privacySection.rowCount')
    replace(settings, 'return privacySection.cell(at: indexPath.row)',
        '''if indexPath.row < torPrivacySection.rowCount {
                return torPrivacySection.cell(at: indexPath.row, from: self)
            }
            return privacySection.cell(at: indexPath.row - torPrivacySection.rowCount)''')
    replace(settings, 'privacySection.selectRow(at: indexPath.row, from: self)',
        '''if indexPath.row < torPrivacySection.rowCount {
                torPrivacySection.selectRow(at: indexPath.row, from: self)
            } else {
                privacySection.selectRow(at: indexPath.row - torPrivacySection.rowCount, from: self)
            }''')
    replace(settings, 'return SettingsSectionText(headerTitle: NSLocalizedString("Privacy", comment: ""))',
        'return SettingsSectionText(headerTitle: "Privacy", footerTitle: TorPrivacySettingsSection.footer)')
    # TorPrivacy forces the English app language at process startup; retain all
    # bundled localization files so explicit Xcode resource references stay valid.
    print('English privacy switches and relay navigation applied (app only)')


if __name__ == '__main__':
    apply(Path(sys.argv[1]).resolve())
