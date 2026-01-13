import { App, FileSystemAdapter, Notice } from 'obsidian';
import { spawn } from 'child_process';
import * as path from 'path';
import { AretePluginSettings } from '@domain/settings';

export class SyncService {
	app: App;
	settings: AretePluginSettings;
	pluginManifest: any;

	constructor(app: App, settings: AretePluginSettings, manifest: any) {
		this.app = app;
		this.settings = settings;
		this.pluginManifest = manifest;
	}

	async runSync(
		prune = false,
		targetPath: string | null = null,
		force = false,
		updateStatusBar: (state: 'idle' | 'syncing' | 'error' | 'success', msg?: string) => void,
	) {
		updateStatusBar('syncing');
		const action = targetPath ? 'Sycing file...' : 'Starting arete sync...';
		new Notice(action);

		const vaultConfig = this.app.vault.adapter as FileSystemAdapter;
		if (!vaultConfig.getBasePath) {
			new Notice('Error: Cannot determine vault path.');
			updateStatusBar('error', 'No Vault Path');
			return;
		}
		const vaultPath = vaultConfig.getBasePath();

		// Logging Setup
		const pluginDir =
			(this.pluginManifest && this.pluginManifest.dir) || '.obsidian/plugins/arete';
		const logPath = vaultPath ? path.join(vaultPath, pluginDir, 'arete_plugin.log') : '';

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
		const scriptPath = this.settings.areteScriptPath || '';

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
			args.push('arete');

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
			log(`Trace: No script path provided. Defaulting to 'python -m arete'`);
			args.push('-m');
			args.push('arete');

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

		if (
			this.settings.ankiConnectUrl &&
			this.settings.ankiConnectUrl !== 'http://localhost:8765'
		) {
			args.push('--anki-connect-url');
			args.push(this.settings.ankiConnectUrl);
		}

		if (this.settings.ankiMediaDir) {
			args.push('--anki-media-dir');
			args.push(this.settings.ankiMediaDir);
		}

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
					new Notice('arete sync completed successfully!');
					updateStatusBar('success');
				} else {
					updateStatusBar('error');

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
						new Notice('Error: Invalid Python environment or arete not installed.');
					} else {
						new Notice(`arete sync failed! (Code ${code}). See log.`);
					}
				}
			});

			child.on('error', (err) => {
				log(`Process Error: ${err.message}`);
				new Notice(`Failed to start: ${err.message}`);
				updateStatusBar('error', err.message);
			});
		} catch (e: any) {
			log(`Exception during spawn: ${e.message}`);
			new Notice(`Exception: ${e.message}`);
			updateStatusBar('error', e.message);
		}
	}
}
