import { requestUrl } from 'obsidian';
import { spawn } from 'child_process';
import * as path from 'path';

export class AreteClient {
	private settings: any;
	private url: string;

	constructor(settings: any) {
		this.settings = settings;
		this.url = `http://127.0.0.1:${settings.server_port || 8777}`;
	}

	// NOTE: This class previously called AnkiConnect directly.
	// It is now REFRACTORED to act as a client for the Arete Server OR CLI.

	async invoke(endpoint: string, body: any = {}): Promise<any> {
		if (this.settings.execution_mode === 'cli') {
			return this.invokeCLI(endpoint, body);
		}

		return this.invokeServer(endpoint, body);
	}

	async invokeServer(endpoint: string, body: any = {}): Promise<any> {
		const areteServerUrl = `http://127.0.0.1:${this.settings.server_port || 8777}`;

		console.log(`[Arete] Server Invoke: ${endpoint}`, body);

		// Inject Config Overrides
		const payload = {
			...body,
			backend: this.settings.backend,
			anki_connect_url: this.settings.anki_connect_url,
		};

		try {
			const response = await requestUrl({
				url: `${areteServerUrl}${endpoint}`,
				method: 'POST', // Most are POST
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(payload),
				throw: false,
			});

			if (response.status >= 300) {
				throw new Error(`Server returned ${response.status}: ${response.text}`);
			}
			const result = response.json;
			return result;
		} catch (error) {
			console.error(`Arete Server Error (${endpoint}):`, error);
			throw error;
		}
	}

	async invokeCLI(endpoint: string, body: any): Promise<any> {
		console.log(`[Arete] CLI Invoke: ${endpoint}`, body);

		// Map Endpoint to Arguments
		const args: string[] = ['anki'];

		if (endpoint === '/anki/cards/suspend') {
			args.push('cards-suspend');
			args.push('--cids');
			args.push(JSON.stringify(body.cids || []));
		} else if (endpoint === '/anki/cards/unsuspend') {
			args.push('cards-unsuspend');
			args.push('--cids');
			args.push(JSON.stringify(body.cids || []));
		} else if (endpoint.startsWith('/anki/models/')) {
			const parts = endpoint.split('/');
			if (parts.length >= 5) {
				const modelName = decodeURIComponent(parts[3]);
				const action = parts[4].split('?')[0]; // remove query params
				if (action === 'styling') {
					args.push('models-styling');
					args.push(modelName);
				} else if (action === 'templates') {
					args.push('models-templates');
					args.push(modelName);
				}
			}
		} else if (endpoint === '/anki/stats' || endpoint === '/anki/stats/enriched') {
			args.push(endpoint === '/anki/stats' ? 'stats' : 'stats-enriched');
			args.push('--nids');
			args.push(JSON.stringify(body.nids || []));
		} else if (endpoint === '/anki/browse') {
			args.push('browse');
			args.push('--query');
			args.push(body.query);
		} else {
			throw new Error(`CLI Endpoint not supported: ${endpoint}`);
		}

		// Config Overrides
		if (this.settings.backend && this.settings.backend !== 'auto') {
			args.push('--backend', this.settings.backend);
		}
		if (this.settings.anki_connect_url) {
			args.push('--anki-connect-url', this.settings.anki_connect_url);
		}

		// Spawn Logic
		return new Promise((resolve, reject) => {
			const pythonSetting = this.settings.python_path || 'python3';
			const scriptPath = this.settings.arete_script_path || '';
			const projectRoot = this.settings.project_root || '';

			const parts = pythonSetting.split(' ');
			const cmd = parts[0];
			const cmdArgs = parts.slice(1);
			const env = Object.assign({}, process.env);

			if (scriptPath && scriptPath.endsWith('.py')) {
				const scriptDir = path.dirname(scriptPath);
				const packageRoot = path.dirname(scriptDir);
				env['PYTHONPATH'] = packageRoot;
				cmdArgs.push('-m', 'arete');
			} else if (!cmdArgs.includes('-m')) {
				cmdArgs.push('-m', 'arete');
			}

			const finalArgs = [...cmdArgs, ...args];
			const runCwd = projectRoot || '.';

			console.log(`[Arete] Spawning: ${cmd} ${finalArgs.join(' ')}`);
			const child = spawn(cmd, finalArgs, { cwd: runCwd, env });

			let stdout = '';
			let stderr = '';

			child.stdout.on('data', (d) => (stdout += d.toString()));
			child.stderr.on('data', (d) => (stderr += d.toString()));

			child.on('close', (code) => {
				if (code === 0) {
					const trimmed = stdout.trim();
					try {
						// 1. Try to parse the entire trimmed stdout
						resolve(JSON.parse(trimmed));
					} catch (e) {
						// 2. Fallback: Find the first/last brackets to extract JSON block
						// This handles cases where warnings or logs are mixed with JSON
						const startIndex = trimmed.search(/[[{]/);
						const endIndex = trimmed.lastIndexOf(trimmed.match(/[\]}]/)?.[0] || '');

						if (startIndex !== -1 && endIndex !== -1 && endIndex >= startIndex) {
							const jsonBlock = trimmed.substring(startIndex, endIndex + 1);
							try {
								resolve(JSON.parse(jsonBlock));
								return; // Success!
							} catch (e2) {
								console.error('[Arete] Failed to parse extracted JSON block:', e2);
							}
						}

						// 3. Final Fallback: Return as output object
						resolve({ output: stdout });
					}
				} else {
					reject(new Error(`CLI Error (${code}): ${stderr}`));
				}
			});
		});
	}

	async modelStyling(modelName: string): Promise<string> {
		// GET /anki/models/{name}/styling
		const endpoint = `/anki/models/${encodeURIComponent(modelName)}/styling`;
		if (this.settings.execution_mode === 'cli') {
			const res = await this.invokeCLI(endpoint, {});
			return res.css || '';
		}

		// Server Mode
		const params = new URLSearchParams({
			backend: this.settings.backend || '',
			anki_connect_url: this.settings.anki_connect_url || '',
		});
		const response = await requestUrl(`${this.url}${endpoint}?${params.toString()}`);
		if (response.status !== 200) return '';
		return response.json?.css || '';
	}

	async modelTemplates(
		modelName: string,
	): Promise<Record<string, { Front: string; Back: string }>> {
		// GET /anki/models/{name}/templates
		const endpoint = `/anki/models/${encodeURIComponent(modelName)}/templates`;
		if (this.settings.execution_mode === 'cli') {
			return this.invokeCLI(endpoint, {});
		}

		const params = new URLSearchParams({
			backend: this.settings.backend || '',
			anki_connect_url: this.settings.anki_connect_url || '',
		});
		const response = await requestUrl(`${this.url}${endpoint}?${params.toString()}`);
		if (response.status !== 200) return {};
		return response.json || {};
	}

	async version(): Promise<number> {
		return 6;
	}

	async suspendCards(cardIds: number[]): Promise<boolean> {
		const res = await this.invoke('/anki/cards/suspend', { cids: cardIds });
		return res.ok;
	}

	async unsuspendCards(cardIds: number[]): Promise<boolean> {
		const res = await this.invoke('/anki/cards/unsuspend', { cids: cardIds });
		return res.ok;
	}

	async getCardInfo(cardIds: number[]): Promise<any[]> {
		return [];
	}

	async browse(query: string): Promise<boolean> {
		const res = await this.invoke('/anki/browse', { query });
		return res && res.ok;
	}
}
