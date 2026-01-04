import {
	App,
	Editor,
	MarkdownView,
	Modal,
	Notice,
	Plugin,
	PluginSettingTab,
	Setting,
	FileSystemAdapter,
	setIcon,
} from 'obsidian';
import { spawn } from 'child_process';
import * as path from 'path';

interface O2APluginSettings {
	pythonPath: string;
	o2aScriptPath: string;
	debugMode: boolean;
	backend: 'auto' | 'apy' | 'ankiconnect';
	workers: number;
}

const DEFAULT_SETTINGS: O2APluginSettings = {
	pythonPath: 'python3',
	o2aScriptPath: '',
	debugMode: false,
	backend: 'auto',
	workers: 4,
};

export default class O2APlugin extends Plugin {
	settings: O2APluginSettings;
	statusBarItem: HTMLElement;

	async onload() {
		await this.loadSettings();

		// 1. Status Bar Setup
		this.statusBarItem = this.addStatusBarItem();
		this.updateStatusBar('idle');

		// 2. Ribbon Icon
		const ribbonIconEl = this.addRibbonIcon(
			'sheets-in-box',
			'Sync to Anki (o2a)',
			(evt: MouseEvent) => {
				this.runSync();
			},
		);

		// 3. Commands
		this.addCommand({
			id: 'o2a-sync',
			name: 'Sync',
			// Default hotkey: Cmd/Ctrl + Shift + A
			hotkeys: [{ modifiers: ['Mod', 'Shift'], key: 'A' }],
			callback: () => {
				this.runSync();
			},
		});

		this.addCommand({
			id: 'o2a-check-file',
			name: 'Check Current File',
			editorCallback: (editor: Editor, view: MarkdownView) => {
				if (view.file) {
					const vaultAdapter = this.app.vault.adapter as FileSystemAdapter;
					if (vaultAdapter.getBasePath) {
						const fullPath = path.join(vaultAdapter.getBasePath(), view.file.path);
						this.runCheck(fullPath);
					}
				}
			},
		});

		this.addCommand({
			id: 'o2a-check-integrity',
			name: 'Debug: Check Vault Integrity (Obsidian vs Linter)',
			callback: () => {
				this.checkVaultIntegrity();
			},
		});

		this.addCommand({
			id: 'o2a-sync-current-file',
			name: 'Sync Current File (Force Update)',
			callback: () => {
				const activeFile = this.app.workspace.getActiveFile();
				if (activeFile) {
					const vaultAdapter = this.app.vault.adapter as FileSystemAdapter;
					if (vaultAdapter.getBasePath) {
						const maxPath = path.join(vaultAdapter.getBasePath(), activeFile.path);
						this.runSync(false, maxPath, true);
					} else {
						new Notice('Error: Cannot resolve file path.');
					}
				} else {
					new Notice('No active file to sync.');
				}
			},
		});

		this.addCommand({
			id: 'o2a-sync-prune',
			name: 'Sync with Prune',
			callback: () => {
				this.runSync(true);
			},
		});

		// 4. Settings
		this.addSettingTab(new O2ASettingTab(this.app, this));
	}

	onunload() {
		if (this.statusBarItem) {
			this.statusBarItem.empty();
		}
	}

	updateStatusBar(state: 'idle' | 'syncing' | 'error' | 'success', msg?: string) {
		if (!this.statusBarItem) return;

		this.statusBarItem.empty();

		if (state === 'idle') {
			// Optional: Hide or show "Ready"
			// this.statusBarItem.setText('O2A: Ready');
			return;
		}

		if (state === 'syncing') {
			this.statusBarItem.createSpan({ cls: 'o2a-sb-icon', text: '🔄 ' }); // You can replace with CSS spinner
			this.statusBarItem.createSpan({ text: 'Anki Syncing...' });
		} else if (state === 'success') {
			this.statusBarItem.setText('✅ Sync Complete');
			// Reset after 3 seconds
			setTimeout(() => this.updateStatusBar('idle'), 3000);
		} else if (state === 'error') {
			this.statusBarItem.setText('❌ Sync Error');
			this.statusBarItem.title = msg || 'Check logs';
		}
	}

	async runCheck(filePath: string) {
		new Notice('Checking file...');
		const python = this.settings.pythonPath || 'python3';
		const scriptPath = this.settings.o2aScriptPath || '';

		const cmd = python;
		const args = [];
		const env = Object.assign({}, process.env);

		if (scriptPath && scriptPath.endsWith('.py')) {
			const scriptDir = path.dirname(scriptPath);
			const packageRoot = path.dirname(scriptDir);
			env['PYTHONPATH'] = packageRoot;
			args.push('-m');
			args.push('o2a');
			args.push('check-file');
		} else {
			args.push('-m');
			args.push('o2a');
			args.push('check-file');
		}

		args.push(filePath);
		args.push('--json');

		try {
			const child = spawn(cmd, args, { env: env });
			let stdout = '';
			let stderr = '';

			child.stdout.on('data', (d) => (stdout += d.toString()));
			child.stderr.on('data', (d) => (stderr += d.toString()));

			child.on('close', (code) => {
				try {
					const res = JSON.parse(stdout);
					new CheckResultModal(this.app, this, res, filePath).open();
				} catch (e) {
					console.error('Failed to parse check output', stdout);
					new Notice('Check failed. See console.');
				}
			});

			child.on('error', (err) => {
				new Notice(`Error: ${err.message}`);
			});
		} catch (e: any) {
			new Notice(`Error: ${e.message}`);
		}
	}

	async runSync(prune = false, targetPath: string | null = null, force = false) {
		this.updateStatusBar('syncing');
		const action = targetPath ? 'Sycing file...' : 'Starting o2a sync...';
		new Notice(action);

		const vaultConfig = this.app.vault.adapter as FileSystemAdapter;
		if (!vaultConfig.getBasePath) {
			new Notice('Error: Cannot determine vault path.');
			this.updateStatusBar('error', 'No Vault Path');
			return;
		}
		const vaultPath = vaultConfig.getBasePath();

		// Logging Setup
		const pluginDir = (this.manifest && this.manifest.dir) || '.obsidian/plugins/obsidian-2-anki';
		const logPath = vaultPath ? path.join(vaultPath, pluginDir, 'o2a_plugin.log') : '';

		const log = (msg: string) => {
			const timestamp = new Date().toISOString();
			const line = `[${timestamp}] ${msg}\n`;
			console.log(msg);
			try {
				// eslint-disable-next-line @typescript-eslint/no-var-requires
				const fs = require('fs');
				fs.appendFileSync(logPath, line);
			} catch (e) {
				console.error('Failed to write to log file', e);
			}
		};

		log(`\n\n=== STARTING NEW SYNC RUN ===`);
		log(`Vault: ${vaultPath}`);

		const python = this.settings.pythonPath || 'python3';
		const scriptPath = this.settings.o2aScriptPath || '';

		const cmd = python;
		const args = [];
		const env = Object.assign({}, process.env); // Copy env

		if (scriptPath && scriptPath.endsWith('.py')) {
			log(`Trace: Detected .py script: ${scriptPath}`);
			const scriptDir = path.dirname(scriptPath);
			const packageRoot = path.dirname(scriptDir);
			log(`Trace: Derived package root (PYTHONPATH): ${packageRoot}`);
			env['PYTHONPATH'] = packageRoot;

			args.push('-m');
			args.push('o2a');

			if (this.settings.debugMode) {
				args.push('--verbose');
			}

			args.push('sync');
		} else if (scriptPath) {
			log(`Trace: Using custom script/binary: ${scriptPath}`);
			args.push(scriptPath);

			if (this.settings.debugMode) {
				args.push('--verbose');
			}

			args.push('sync');
		} else {
			log(`Trace: No script path provided. Defaulting to 'python -m o2a'`);
			args.push('-m');
			args.push('o2a');

			if (this.settings.debugMode) {
				args.push('--verbose');
			}

			args.push('sync');
		}

		if (prune) {
			args.push('--prune');
		}

		if (force) {
			args.push('--force');
		}

		if (this.settings.backend && this.settings.backend !== 'auto') {
			args.push('--backend');
			args.push(this.settings.backend);
		}

		if (this.settings.workers) {
			args.push('--workers');
			args.push(this.settings.workers.toString());
		}

		// If targetPath is specific file, append it.
		// CAREFUL: If targetPath is meant to be the "VAULT_ROOT" arg for default sync, we should handle that.
		// But for "single file sync", o2a supports `sync [PATH]`.
		// If targetPath is null, we default to vaultPath.
		args.push(targetPath || vaultPath);

		log(`Spawning: ${cmd} ${args.join(' ')}`);

		try {
			const child = spawn(cmd, args, {
				cwd: vaultPath,
				env: env,
			});

			let stderrBuffer = '';

			child.stdout.on('data', (data) => {
                if (!data) return;
				const lines = data.toString().split('\n');
				lines.forEach((l: string) => {
					if (l) log(`STDOUT: ${l}`);
				});
			});

			child.stderr.on('data', (data) => {
                if (!data) return;
				const str = data.toString();
				stderrBuffer += str;
				const lines = str.split('\n');
				lines.forEach((l: string) => {
					if (l) log(`STDERR: ${l}`);
				});
			});

			child.on('close', (code) => {
				log(`Process exited with code ${code}`);

				if (code === 0) {
					new Notice('o2a sync completed successfully!');
					this.updateStatusBar('success');
				} else {
					// Smart Error Handling
					this.updateStatusBar('error');

					if (
						stderrBuffer.includes('AnkiConnect call failed') ||
						stderrBuffer.includes('Connection refused')
					) {
						new Notice('Error: Anki is not reachable. Is Anki open with AnkiConnect?');
					} else if (stderrBuffer.includes('ModuleNotFoundError')) {
						new Notice(
							'Error: Python Dependencies missing. Check Python Executable path.',
						);
					} else if (stderrBuffer.includes('No module named')) {
						new Notice('Error: Invalid Python environment or o2a not installed.');
					} else {
						new Notice(`o2a sync failed! (Code ${code}). See log.`);
					}
				}
			});

			child.on('error', (err) => {
				log(`Process Error: ${err.message}`);
				new Notice(`Failed to start: ${err.message}`);
				this.updateStatusBar('error', err.message);
			});
		} catch (e: any) {
			log(`Exception during spawn: ${e.message}`);
			new Notice(`Exception: ${e.message}`);
			this.updateStatusBar('error', e.message);
		}
	}

	// Helper to test configuration
	async testConfig() {
		new Notice('Testing configuration...');
		const python = this.settings.pythonPath || 'python3';

		// Ideally checking version: python -m o2a --version (if installed via pip)
		// Our current setup doesn't expose --version easily on the main entry point logic if importing script
		// But `pip` installed o2a works with --version if using typer?
		// Typer usually adds --version if configured?
		// Let's just try running `python --version` to at least valid python path.

		// Checking Python
		try {
			const child = spawn(python, ['--version']);
			child.on('close', (code) => {
				if (code === 0) {
					new Notice(`Success: Python found.`);
				} else {
					new Notice(`Error: Python command failed.`);
				}
			});
			child.on('error', (err) => {
				new Notice(`Error: Invalid Python Path. ${err.message}`);
			});
		} catch (e: any) {
			new Notice(`Error: ${e.message}`);
		}
	}

	async loadSettings() {
		this.settings = Object.assign({}, DEFAULT_SETTINGS, await this.loadData());
	}

	async saveSettings() {
		await this.saveData(this.settings);
	}

	async runFix(filePath: string): Promise<void> {
		// Run o2a fix-file
		const settings = this.settings;
		const pythonPath = settings.pythonPath || 'python3';
		const scriptPath = settings.o2aScriptPath;

		let cmd = '';
		let args: string[] = [];

		if (scriptPath && scriptPath.endsWith('.py')) {
			const scriptDir = path.dirname(settings.o2aScriptPath);
			cmd = pythonPath;
			args = ['-m', 'o2a', 'fix-file', filePath];
		} else {
			cmd = pythonPath;
			args = ['-m', 'o2a', 'fix-file', filePath];
		}

		const env = Object.assign({}, process.env);
		if (scriptPath && scriptPath.endsWith('.py')) {
			const scriptDir = path.dirname(scriptPath);
			const packageRoot = path.dirname(scriptDir);
			env['PYTHONPATH'] = packageRoot;
		}

		return new Promise((resolve) => {
			const child = spawn(cmd, args, { env: env });

			child.on('close', (code) => {
				if (code === 0) {
					new Notice('✨ File auto-fixed!');
				} else {
					new Notice('❌ Fix failed (check console)');
				}
				resolve();
			});
		});
	}

	async checkVaultIntegrity() {
		new Notice('Running Integrity Check...');
		const files = this.app.vault.getMarkdownFiles();
		let issues = 0;
		let checked = 0;

		console.log('--- O2A Integrity Check ---');

		for (const file of files) {
			checked++;
			const cache = this.app.metadataCache.getFileCache(file);
			const content = await this.app.vault.read(file);

			// Basic check: Does it look like it SHOULD have frontmatter?
			if (content.startsWith('---\n')) {
				// If Obsidian parses it successfully, cache.frontmatter should exist.
				// If it's invalid (e.g. tabs), frontmatter is usually undefined or empty
				// Note: empty frontmatter --- \n --- might be parsed as {}

				if (!cache || !cache.frontmatter) {
					console.error(
						`[FAIL] ${file.path}: Has YAML block, but Obsidian Cache has no frontmatter! (Likely Invalid Properties)`,
					);
					issues++;
				} else {
					// Valid according to Obsidian
					// console.log(`[PASS] ${file.path}`);
				}
			}
		}

		console.log(
			`Integrity Check Complete. ${checked} files checked. ${issues} potential issues.`,
		);
		if (issues > 0) {
			new Notice(`Found ${issues} files with Invalid Properties (Check Console)`);
		} else {
			new Notice(`Integrity Check Passed (Obsidian parses all YAML correctly)`);
		}
	}
}

export class O2ASettingTab extends PluginSettingTab {
	plugin: O2APlugin;

	constructor(app: App, plugin: O2APlugin) {
		super(app, plugin);
		this.plugin = plugin;
	}

	display(): void {
		const { containerEl } = this;
		containerEl.empty();
        // console.log('SettingTab Display. Debug Mode:', this.plugin.settings.debugMode);

		containerEl.createEl('h2', { text: 'O2A Settings' });

		new Setting(containerEl)
			.setName('Python Executable')
			.setDesc('Path to python3 or o2a executable')
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
			.setName('O2A Script Path')
			.setDesc('Absolute path to o2a/main.py. Leave empty if you are using a global binary.')
			.addText((text) =>
				text
					.setPlaceholder('/path/to/o2a/main.py')
					.setValue(this.plugin.settings.o2aScriptPath)
					.onChange(async (value) => {
						this.plugin.settings.o2aScriptPath = value;
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
			{ id: 'obsidian-2-anki:o2a-sync', name: 'Sync' },
			{ id: 'obsidian-2-anki:o2a-sync-current-file', name: 'Sync Current File' },
			{ id: 'obsidian-2-anki:o2a-sync-prune', name: 'Sync with Prune' },
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
							hotkeysTab.searchComponent.setValue('o2a');
							hotkeysTab.updateHotkeyVisibility();
						}
					}),
				);
		});
	}
}

export class CheckResultModal extends Modal {
	result: any;
	plugin: O2APlugin;
	filePath: string;

	constructor(app: App, plugin: O2APlugin, result: any, filePath: string) {
		super(app);
		this.plugin = plugin;
		this.result = result;
		this.filePath = filePath;
	}

	onOpen() {
		const { contentEl } = this;
		contentEl.addClass('o2a-modal');

		const header = contentEl.createDiv({ cls: 'modal-header' });
		header.createEl('h2', { text: 'O2A File Check' });
		header.createEl('span', { text: path.basename(this.filePath), cls: 'o2a-filename' });

		if (this.result.ok) {
			contentEl.createDiv({ text: '✅ Valid', cls: 'o2a-success' });

			const ul = contentEl.createEl('ul', { cls: 'o2a-stats' });

			const li1 = ul.createEl('li');
			li1.createSpan({ text: 'Deck', cls: 'o2a-stats-label' });
			li1.createSpan({ text: this.result.stats.deck || 'None', cls: 'o2a-stats-val' });

			const li2 = ul.createEl('li');
			li2.createSpan({ text: 'Cards Found', cls: 'o2a-stats-label' });
			li2.createSpan({
				text: this.result.stats.cards_found.toString(),
				cls: 'o2a-stats-val',
			});
		} else {
			contentEl.createDiv({ text: '❌ Validation Failed', cls: 'o2a-error' });

			const table = contentEl.createEl('table', { cls: 'o2a-error-table' });
			const head = table.createEl('thead');
			const row = head.createEl('tr');
			row.createEl('th', { text: 'Line' });
			row.createEl('th', { text: 'Error Message' });

			const body = table.createEl('tbody');
			let fixable = false;

			this.result.errors.forEach((err: any) => {
				const tr = body.createEl('tr');
				tr.createEl('td', { text: err.line.toString(), cls: 'o2a-error-line' });
				tr.createEl('td', { text: err.message, cls: 'o2a-err-msg' });

				// Detect fixable errors
				if (
					err.message.includes('Tab Character Error') ||
					err.message.includes("Missing 'cards' list")
				) {
					fixable = true;
				}
			});

			if (fixable) {
				const btnContainer = contentEl.createDiv({
					cls: 'o2a-btn-container',
					attr: { style: 'margin-top: 1rem; text-align: right;' },
				});
				const btn = btnContainer.createEl('button', {
					text: '✨ Auto-Fix Issues',
					cls: 'mod-cta',
				});
				btn.addEventListener('click', async () => {
					btn.disabled = true;
					btn.setText('Fixing...');
					await this.plugin.runFix(this.filePath);
					this.close();
					// Re-run check
					this.plugin.runCheck(this.filePath);
				});
			}

			contentEl.createDiv({
				text: '💡 Tip: Check for correct YAML indentation (2 spaces) and ensure "cards" list exists.',
				cls: 'o2a-hint',
			});
		}
	}

	onClose() {
		const { contentEl } = this;
		contentEl.empty();
	}
}
