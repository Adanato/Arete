import { App, FileSystemAdapter, Notice } from 'obsidian';
import { spawn } from 'child_process';
import * as path from 'path';
import { AretePluginSettings } from '@domain/settings';
import { CheckResultModal } from '@presentation/modals/CheckResultModal';
import AretePlugin from '@/main';

export class CheckService {
	app: App;
	plugin: AretePlugin;
	settings: AretePluginSettings;

	constructor(app: App, plugin: AretePlugin) {
		this.app = app;
		this.plugin = plugin;
		this.settings = plugin.settings;
	}

	async runCheck(filePath: string) {
		new Notice('Checking file...');
		const python = this.settings.pythonPath || 'python3';
		const scriptPath = this.settings.areteScriptPath || '';

		const cmd = python;
		const args = [];
		const env = Object.assign({}, process.env);

		if (scriptPath && scriptPath.endsWith('.py')) {
			const scriptDir = path.dirname(scriptPath);
			const packageRoot = path.dirname(scriptDir);
			env['PYTHONPATH'] = packageRoot;
			args.push('-m');
			args.push('arete');
			args.push('check-file');
		} else {
			args.push('-m');
			args.push('arete');
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
					// NOTE: CheckResultModal needs plugin instance to run fix commands.
					// Ideally we decouple this further, but for now passing plugin is fine.
					new CheckResultModal(this.app, this.plugin, res, filePath).open();
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

	async runFix(filePath: string): Promise<void> {
		const settings = this.settings;
		const pythonPath = settings.pythonPath || 'python3';
		const scriptPath = settings.areteScriptPath;

		let cmd = '';
		let args: string[] = [];

		if (scriptPath && scriptPath.endsWith('.py')) {
			const scriptDir = path.dirname(settings.areteScriptPath);
			cmd = pythonPath;
			args = ['-m', 'arete', 'fix-file', filePath];
		} else {
			cmd = pythonPath;
			args = ['-m', 'arete', 'fix-file', filePath];
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

	async testConfig() {
		new Notice('Testing configuration...');
		const python = this.settings.pythonPath || 'python3';

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

	async checkVaultIntegrity() {
		new Notice('Running Integrity Check...');
		const files = this.app.vault.getMarkdownFiles();
		let issues = 0;
		let checked = 0;

		console.log('--- Arete Integrity Check ---');

		for (const file of files) {
			checked++;
			const cache = this.app.metadataCache.getFileCache(file);
			const content = await this.app.vault.read(file);

			if (content.startsWith('---\n')) {
				if (!cache || !cache.frontmatter) {
					console.error(
						`[FAIL] ${file.path}: Has YAML block, but Obsidian Cache has no frontmatter! (Likely Invalid Properties)`,
					);
					issues++;
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
