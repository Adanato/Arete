import { App, Notice } from 'obsidian';
import { spawn, exec } from 'child_process';
import * as path from 'path';
import { AretePluginSettings } from '@domain/settings';

export class CheckService {
	app: App;
	settings: AretePluginSettings;

	constructor(app: App, settings: AretePluginSettings) {
		this.app = app;
		this.settings = settings;
	}

	private getPythonCommand(): { cmd: string; args: string[] } {
		const raw = this.settings.python_path || 'python3';
		const parts = raw.split(' ').filter((p) => p.trim() !== '');
		return {
			cmd: parts[0],
			args: parts.slice(1),
		};
	}

	private getEnv(cwd?: string) {
		const env = Object.assign({}, process.env);
		// Auto-detect 'src' folder in project root to fix PYTHONPATH
		if (cwd) {
			const srcPath = path.join(cwd, 'src');
			const currentPath = env['PYTHONPATH'] || '';
			env['PYTHONPATH'] = currentPath ? `${currentPath}:${srcPath}` : srcPath;
		}

		// Fix PATH on macOS for GUI apps (Obsidian often lacks .local/bin)
		if (process.platform === 'darwin' && process.env.HOME) {
			const home = process.env.HOME;
			const extraPaths = [
				path.join(home, '.local', 'bin'),
				path.join(home, '.cargo', 'bin'),
				'/opt/homebrew/bin',
				'/usr/local/bin',
			];
			const currentPath = env['PATH'] || '';
			env['PATH'] = `${currentPath}:${extraPaths.join(':')}`;
		}

		return env;
	}

	async getCheckResult(filePath: string): Promise<any> {
		const scriptPath = this.settings.arete_script_path || '';

		const { cmd, args: initialArgs } = this.getPythonCommand();
		const args = [...initialArgs];

		const cwd = this.settings.project_root || undefined;
		const env = this.getEnv(cwd);

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

		return new Promise((resolve, reject) => {
			// CRITICAL: Set cwd to project root so 'uv run' finds pyproject.toml
			const child = spawn(cmd, args, { env: env, cwd: cwd });
			let stdout = '';
			let stderr = '';

			child.stdout.on('data', (d) => (stdout += d.toString()));
			child.stderr.on('data', (d) => (stderr += d.toString()));

			child.on('close', (code) => {
				try {
					const res = JSON.parse(stdout);
					resolve(res);
				} catch (e) {
					console.error('Failed to parse check output', stdout);
					console.error('Stderr:', stderr);

					// Fallback: Try to extract JSON from stdout (in case of log spew)
					try {
						const jsonMatch = stdout.match(/\{[\s\S]*\}/);
						if (jsonMatch) {
							const res = JSON.parse(jsonMatch[0]);
							resolve(res);
							return;
						}
					} catch (e2) {
						// Fallback failed
					}

					const preview = stdout.trim().substring(0, 200);
					const errPreview = stderr.trim().substring(0, 200);
					reject(new Error(`Parse Error. Stdout: "${preview}" Stderr: "${errPreview}"`));
				}
			});

			child.on('error', (err) => {
				reject(err);
			});
		});
	}

	async runFix(filePath: string): Promise<void> {
		const settings = this.settings;
		const scriptPath = settings.arete_script_path;

		const { cmd, args: initialArgs } = this.getPythonCommand();
		const args = [...initialArgs];

		const cwd = this.settings.project_root || undefined;
		const env = this.getEnv(cwd);

		if (scriptPath && scriptPath.endsWith('.py')) {
			const scriptDir = path.dirname(scriptPath);
			const packageRoot = path.dirname(scriptDir);
			env['PYTHONPATH'] = packageRoot;
		}

		args.push('-m');
		args.push('arete');
		args.push('fix-file');
		args.push(filePath);

		return new Promise((resolve) => {
			const child = spawn(cmd, args, { env: env, cwd: cwd });

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

		const rawSettings = this.settings.python_path;
		const cwd = this.settings.project_root || undefined;
		const env = this.getEnv(cwd);

		if (!rawSettings) {
			new Notice('Error: Python Executable setting is empty.');
			return;
		}

		// Use exec to let the shell handle argument parsing
		// We need to carefully quote the python command
		// If rawSettings is "uv run python", we append the -c command
		const cmd = `${rawSettings} -c "import arete; print('Arete module found')"`;

		exec(cmd, { cwd: cwd, env: env }, (error: any, stdout: string, stderr: string) => {
			if (error) {
				console.error('Test Config Failed:', error);
				const msg = stderr || stdout || error.message;
				new Notice(`Error: Command failed. ${msg.substring(0, 200)}`);
			} else {
				new Notice(`Success: Python found & Arete module available.`);
			}
		});
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
