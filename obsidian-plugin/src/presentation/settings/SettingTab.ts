import { App, PluginSettingTab, Setting } from 'obsidian';
import AretePlugin from '@/main';
import { CheckResultModal } from '@presentation/modals/CheckResultModal';

export class AreteSettingTab extends PluginSettingTab {
	plugin: AretePlugin;

	constructor(app: App, plugin: AretePlugin) {
		super(app, plugin);
		this.plugin = plugin;
	}

	display(): void {
		const { containerEl } = this;
		containerEl.empty();

		containerEl.createEl('h2', { text: 'Arete Settings' });

		new Setting(containerEl)
			.setName('Python Executable')
			.setDesc('Path to python3 or arete executable')
			.addText((text) =>
				text
					.setPlaceholder('python3')
					.setValue(this.plugin.settings.pythonPath)
					.onChange(async (value) => {
						this.plugin.settings.pythonPath = value;
						await this.plugin.saveSettings();
					}),
			);

		new Setting(containerEl)
			.setName('Arete Script Path')
			.setDesc(
				'Absolute path to arete/main.py. Leave empty if you are using a global binary.',
			)
			.addText((text) =>
				text
					.setPlaceholder('/path/to/arete/main.py')
					.setValue(this.plugin.settings.areteScriptPath)
					.onChange(async (value) => {
						this.plugin.settings.areteScriptPath = value;
						await this.plugin.saveSettings();
					}),
			);

		new Setting(containerEl)
			.setName('Debug Mode')
			.setDesc('Enable verbose logging and extra output.')
			.addToggle((toggle) =>
				toggle.setValue(this.plugin.settings.debugMode).onChange(async (value) => {
					this.plugin.settings.debugMode = value;
					await this.plugin.saveSettings();
				}),
			);

		new Setting(containerEl)
			.setName('Preview Renderer Mode')
			.setDesc(
				'Choose how card fields are processed before previewing. "Obsidian" renders Markdown/LaTeX (Recommended). "Anki" passes raw text.',
			)
			.addDropdown((dropdown) =>
				dropdown
					.addOption('obsidian', 'Obsidian (Markdown + LaTeX)')
					.addOption('anki', 'Anki (Raw HTML/Text)')
					.setValue(this.plugin.settings.rendererMode)
					.onChange(async (value) => {
						this.plugin.settings.rendererMode = value as 'obsidian' | 'anki';
						await this.plugin.saveSettings();
						// Update renderer instance
						this.plugin.templateRenderer.setMode(this.plugin.settings.rendererMode);
					}),
			);

		new Setting(containerEl)
			.setName('Anki Backend')
			.setDesc('Manual override for the Anki sync driver.')
			.addDropdown((dropdown) =>
				dropdown
					.addOption('auto', 'Auto (Recommended)')
					.addOption('apy', 'Apy (Direct DB Access, Faster)')
					.addOption('ankiconnect', 'AnkiConnect (Requires Anki running)')
					.setValue(this.plugin.settings.backend)
					.onChange(async (value: 'auto' | 'apy' | 'ankiconnect') => {
						this.plugin.settings.backend = value;
						await this.plugin.saveSettings();
					}),
			);

		new Setting(containerEl)
			.setName('Anki Connect URL')
			.setDesc('URL for AnkiConnect API (default: http://localhost:8765)')
			.addText((text) =>
				text
					.setPlaceholder('http://localhost:8765')
					.setValue(this.plugin.settings.ankiConnectUrl)
					.onChange(async (value) => {
						this.plugin.settings.ankiConnectUrl = value;
						await this.plugin.saveSettings();
					}),
			);

		new Setting(containerEl)
			.setName('Anki Media Directory')
			.setDesc('Custom path for Anki media uploads (optional)')
			.addText((text) =>
				text
					.setPlaceholder('/path/to/Anki/collection.media')
					.setValue(this.plugin.settings.ankiMediaDir)
					.onChange(async (value) => {
						this.plugin.settings.ankiMediaDir = value;
						await this.plugin.saveSettings();
					}),
			);

		new Setting(containerEl)
			.setName('Parallel Workers')
			.setDesc(
				'Number of parallel sync workers. Higher is faster but may stress AnkiConnect.',
			)
			.addSlider((slider) =>
				slider
					.setLimits(1, 16, 1)
					.setValue(this.plugin.settings.workers)
					.setDynamicTooltip()
					.onChange(async (value) => {
						this.plugin.settings.workers = value;
						await this.plugin.saveSettings();
					}),
			);

		// Test Button
		new Setting(containerEl)
			.setName('Test Configuration')
			.setDesc('Verifies that the Python Executable is valid.')
			.addButton((button) =>
				button.setButtonText('Test Config').onClick(async () => {
					await this.plugin.testConfig();
				}),
			);

		if (this.plugin.settings.debugMode) {
			new Setting(containerEl)
				.setName('Check Results (Debug)')
				.setDesc('Opens a sample result modal for testing.')
				.addButton((button) =>
					button.setButtonText('Open Sample Modal').onClick(() => {
						new CheckResultModal(
							this.app,
							this.plugin,
							{ ok: true, stats: { deck: 'Debug', cards_found: 0 } },
							'debug-file.md',
						).open();
					}),
				);
		}

		containerEl.createEl('h2', { text: 'Hotkeys' });
		containerEl.createEl('p', {
			text: 'To modify hotkeys, click the button to open Obsidian Hotkey settings.',
		});

		const commands = [
			{ id: 'obsidian-2-anki:arete-sync', name: 'Sync' },
			{ id: 'obsidian-2-anki:arete-sync-current-file', name: 'Sync Current File' },
			{ id: 'obsidian-2-anki:arete-sync-prune', name: 'Sync with Prune' },
		];

		commands.forEach((cmd) => {
			const command = (this.app as any).commands.findCommand(cmd.id);
			if (!command) return;

			const hotkeys = command.hotkeys || [];
			const hotkeyStr =
				hotkeys
					.map((h: any) => {
						const mods = h.modifiers.join('+');
						return `${mods}+${h.key}`;
					})
					.join(', ') || 'No hotkey set';

			new Setting(containerEl)
				.setName(cmd.name)
				.setDesc(`Current: ${hotkeyStr}`)
				.addButton((button) =>
					button.setButtonText('Configure').onClick(() => {
						// Open Hotkeys tab
						(this.app as any).setting.openTabById('hotkeys');
						// Optional: Try to set filter
						const hotkeysTab = (this.app as any).setting.activeTab;
						if (hotkeysTab && hotkeysTab.searchComponent) {
							hotkeysTab.searchComponent.setValue('arete');
							hotkeysTab.updateHotkeyVisibility();
						}
					}),
				);
		});
	}
}
