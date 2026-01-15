import '../../test-setup';
import { App, Notice } from 'obsidian';
import { spawn } from 'child_process';
import { createMockChildProcess } from '../../test-setup';
import { CheckService } from '@application/services/CheckService';
import AretePlugin from '@/main';

describe('CheckService', () => {
	let service: CheckService;
	let app: App;
	let plugin: AretePlugin;

	beforeEach(() => {
		jest.clearAllMocks();
		app = new App();
		(app.vault.adapter as any).getBasePath = jest.fn().mockReturnValue('/mock/vault/path');

		// Mock Plugin
		plugin = new AretePlugin(app, { dir: 'test-plugin-dir' } as any);
		plugin.settings = {
			python_path: 'python3',
			arete_script_path: '',
			debug_mode: false,
			backend: 'auto',
			workers: 4,
			anki_connect_url: 'http://localhost:8765',
			anki_media_dir: '',
			renderer_mode: 'obsidian',
			stats_algorithm: 'sm2',
			stats_lapse_threshold: 3,
			stats_ease_threshold: 2100,
			stats_difficulty_threshold: 0.9,
			graph_coloring_enabled: false,
			graph_tag_prefix: 'arete/retention',
			sync_on_save: false,
			sync_on_save_delay: 2000,
			ui_expanded_decks: [],
			ui_expanded_concepts: [],
			last_sync_time: null,
			execution_mode: 'cli',
			server_port: 8777,
		};

		service = new CheckService(app, plugin);
	});

	test('runCheck calls arete check-file', async () => {
		const mockChild = createMockChildProcess();
		(spawn as jest.Mock).mockReturnValue(mockChild);

		const checkPromise = service.runCheck('/mock/path/file.md');
		mockChild.emit('close', 0);
		await checkPromise;

		expect(spawn).toHaveBeenCalledWith(
			'python3',
			['-m', 'arete', 'check-file', '/mock/path/file.md', '--json'],
			expect.any(Object),
		);
	});

	test('runCheck with .py script path', async () => {
		plugin.settings.arete_script_path = '/path/to/o2a/main.py';
		const mockChild = createMockChildProcess();
		(spawn as jest.Mock).mockReturnValue(mockChild);

		const checkPromise = service.runCheck('/mock/path/file.md');
		mockChild.emit('close', 0);
		await checkPromise;

		expect(spawn).toHaveBeenCalledWith(
			'python3',
			['-m', 'arete', 'check-file', '/mock/path/file.md', '--json'],
			expect.objectContaining({
				env: expect.objectContaining({ PYTHONPATH: '/path/to' }),
			}),
		);
	});

	test('check vault integrity command', async () => {
		// Mock vault files
		const mockFile = { path: 'test.md' };
		(app.vault.getMarkdownFiles as jest.Mock).mockReturnValue([mockFile]);
		(app.vault.read as jest.Mock).mockResolvedValue('---\nvalid: true\n---\nContent');
		(app.metadataCache.getFileCache as jest.Mock).mockReturnValue({
			frontmatter: { valid: true },
		});

		// Spy on console.log/error to verify output or just ensure it runs without error
		const consoleSpy = jest.spyOn(console, 'log').mockImplementation(() => {
			/* mock */
		});

		await service.checkVaultIntegrity();

		expect(app.vault.getMarkdownFiles).toHaveBeenCalled();
		consoleSpy.mockRestore();
	});
});
