import { App, Notice, requestUrl } from 'obsidian';
import { spawn, ChildProcess } from 'child_process';
import * as path from 'path';
import { AretePluginSettings } from '@domain/settings';

export class ServerManager {
	app: App;
	settings: AretePluginSettings;
	private serverProcess: ChildProcess | null = null;
	private manifest: any;

	constructor(app: App, settings: AretePluginSettings, manifest: any) {
		this.app = app;
		this.settings = settings;
		this.manifest = manifest;
	}

	async start() {
		if (this.settings.execution_mode !== 'server') return;

		// 1. Check if already running
		const isRunning = await this.checkHealth();
		if (isRunning) {
			console.log('[Arete] Server already running.');
			new Notice('Arete Server connected.');
			return;
		}

		// 2. Start Server
		new Notice('Starting Arete Server...');
		try {
			this.spawnServer();

			// 3. Wait for startup
			let attempts = 0;
			while (attempts < 10) {
				await new Promise((r) => setTimeout(r, 1000));
				if (await this.checkHealth()) {
					new Notice('Arete Server started successfully!');
					return;
				}
				attempts++;
			}
			new Notice('Failed to connect to Arete Server after spawning.');
		} catch (e) {
			console.error(e);
			new Notice('Failed to spawn Arete Server.');
		}
	}

	async stop() {
		if (this.settings.execution_mode !== 'server') return;

		// Graceful shutdown via API
		const port = this.settings.server_port || 8777;
		try {
			await requestUrl({
				url: `http://127.0.0.1:${port}/shutdown`,
				method: 'POST',
			});
			console.log('[Arete] Shutdown signal sent.');
		} catch (e) {
			// Server might already be dead
		}

		if (this.serverProcess) {
			this.serverProcess.kill();
			this.serverProcess = null;
		}
	}

	private async checkHealth(): Promise<boolean> {
		const port = this.settings.server_port || 8777;
		try {
			const res = await requestUrl({
				url: `http://127.0.0.1:${port}/health`,
				throw: false,
			});
			return res.status === 200;
		} catch (e) {
			return false;
		}
	}

	private spawnServer() {
		// Reuse logic from SyncService but simplified
		// We know exactly what to run: `arete server`
		const python = this.settings.python_path || 'python3';
		const scriptPath = this.settings.arete_script_path || '';

		const args = [];
		const env = Object.assign({}, process.env);

		// Derive PYTHONPATH if using script
		if (scriptPath && scriptPath.endsWith('.py')) {
			const scriptDir = path.dirname(scriptPath);
			const packageRoot = path.dirname(scriptDir);
			env['PYTHONPATH'] = packageRoot;
			args.push('-m', 'arete');
		} else {
			// Binary or module default
			args.push('-m', 'arete');
		}

		args.push('server', '--port', (this.settings.server_port || 8777).toString());

		// We probably want to detach it so it survives?
		// Or keep it attached so we can kill it?
		// Let's keep it attached but unref so it doesn't block Obsidian?
		// Actually, Obsidian is Electron, spawn works fine.

		// Use 'uv' if not configured?
		// User likely configured 'uv' in python_path or alias?
		// If python_path is 'python3', assuming 'python3 -m arete' works.

		console.log(`[Arete] Spawning server: ${python} ${args.join(' ')}`);

		// TODO: Handle user-defined CWD properly
		const vaultConfig = this.app.vault.adapter as any;
		const cwd = vaultConfig.getBasePath ? vaultConfig.getBasePath() : process.cwd();

		this.serverProcess = spawn(python, args, {
			cwd: cwd,
			env: env,
			stdio: 'ignore', // Don't pipe stdio to avoid buffer issues, or maybe pipe to log file later
		});

		this.serverProcess.on('error', (err) => {
			console.error('[Arete] Server spawn error:', err);
		});

		this.serverProcess.unref(); // Allow Obsidian to close without waiting for this
	}
}
