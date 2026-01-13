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
					.setValue(this.plugin.settings.python_path)
					.onChange(async (value) => {
						this.plugin.settings.python_path = value;
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
					.setValue(this.plugin.settings.arete_script_path)
					.onChange(async (value) => {
						this.plugin.settings.arete_script_path = value;
						await this.plugin.saveSettings();
					}),
			);

		new Setting(containerEl)
			.setName('Debug Mode')
			.setDesc('Enable verbose logging and extra output.')
			.addToggle((toggle) =>
				toggle.setValue(this.plugin.settings.debug_mode).onChange(async (value) => {
					this.plugin.settings.debug_mode = value;
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
					.setValue(this.plugin.settings.renderer_mode)
					.onChange(async (value) => {
						this.plugin.settings.renderer_mode = value as 'obsidian' | 'anki';
						await this.plugin.saveSettings();
						// Update renderer instance
						this.plugin.templateRenderer.setMode(this.plugin.settings.renderer_mode);
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
					.setValue(this.plugin.settings.anki_connect_url)
					.onChange(async (value) => {
						this.plugin.settings.anki_connect_url = value;
						await this.plugin.saveSettings();
					}),
			);

		new Setting(containerEl)
			.setName('Anki Media Directory')
			.setDesc('Custom path for Anki media uploads (optional)')
			.addText((text) =>
				text
					.setPlaceholder('/path/to/Anki/collection.media')
					.setValue(this.plugin.settings.anki_media_dir)
					.onChange(async (value) => {
						this.plugin.settings.anki_media_dir = value;
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

		containerEl.createEl('h3', { text: 'Statistics Dashboard' });

		new Setting(containerEl)
			.setName('Algorithm')
			.setDesc('Choose the scoring algorithm used to identify problematic concepts.')
			.addDropdown((dropdown) =>
				dropdown
					.addOption('sm2', 'Classic (SM-2)')
					.addOption('fsrs', 'FSRS (New Scheduler)')
					.setValue(this.plugin.settings.stats_algorithm)
					.onChange(async (value: 'sm2' | 'fsrs') => {
						this.plugin.settings.stats_algorithm = value;
						// Clean cache to force re-evaluation with new algorithm
						this.plugin.statsCache = { concepts: {}, lastFetched: 0 };
						await this.plugin.saveSettings();
					}),
			);

		new Setting(containerEl)
			.setName('Lapse Threshold')
			.setDesc('Cards with this many lapses or more are considered problematic.')
			.addSlider((slider) =>
				slider
					.setLimits(1, 20, 1)
					.setValue(this.plugin.settings.stats_lapse_threshold)
					.setDynamicTooltip()
					.onChange(async (value) => {
						this.plugin.settings.stats_lapse_threshold = value;
						await this.plugin.saveSettings();
					}),
			);

		if (this.plugin.settings.stats_algorithm === 'sm2') {
			new Setting(containerEl)
				.setName('Ease Threshold (%)')
				.setDesc(
					'Cards with ease below this percentage are considered problematic (Ease Hell). Standard is 250%.',
				)
				.addSlider((slider) =>
					slider
						.setLimits(130, 300, 10)
						.setValue(this.plugin.settings.stats_ease_threshold / 10)
						.setDynamicTooltip()
						.onChange(async (value) => {
							this.plugin.settings.stats_ease_threshold = value * 10;
							await this.plugin.saveSettings();
						}),
				);
		} else {
			new Setting(containerEl)
				.setName('Difficulty Threshold (FSRS)')
				.setDesc(
					'Cards with FSRS difficulty above this value (0.0 to 1.0) are problematic.',
				)
				.addSlider((slider) =>
					slider
						.setLimits(50, 100, 5) // Slider 0-100%
						.setValue(this.plugin.settings.stats_difficulty_threshold * 100)
						.setDynamicTooltip()
						.onChange(async (value) => {
							this.plugin.settings.stats_difficulty_threshold = value / 100;
							await this.plugin.saveSettings();
						}),
				);
		}

		// Test Button
		new Setting(containerEl)
			.setName('Test Configuration')
			.setDesc('Verifies that the Python Executable is valid.')
			.addButton((button) =>
				button.setButtonText('Test Config').onClick(async () => {
					await this.plugin.testConfig();
				}),
			);

		if (this.plugin.settings.debug_mode) {
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
