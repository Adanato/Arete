import './test-setup';
import { App, Notice } from 'obsidian';
import AretePlugin from '@/main';
import { SyncService } from '@application/services/SyncService';
import { CheckService } from '@application/services/CheckService';

// Mock Services
jest.mock('@application/services/SyncService');
jest.mock('@application/services/CheckService');

describe('AretePlugin Composition', () => {
	let plugin: AretePlugin;
	let app: App;

	beforeEach(async () => {
		jest.clearAllMocks();
		app = new App();
		(app.vault.adapter as any).getBasePath = jest.fn().mockReturnValue('/mock/vault/path');

		plugin = new AretePlugin(app, { dir: 'test-plugin-dir' } as any);
		plugin.statusBarItem = plugin.addStatusBarItem() as any;

		// Trigger onload to initialize services
		await plugin.onload();
	});

	test('onload initializes services', () => {
		expect(SyncService).toHaveBeenCalledWith(app, expect.anything(), expect.anything());
		expect(CheckService).toHaveBeenCalledWith(app, plugin);
		expect(plugin.syncService).toBeInstanceOf(SyncService);
		expect(plugin.checkService).toBeInstanceOf(CheckService);
	});

	test('commands delegate to SyncService', async () => {
		const commands = (global as any).registeredCommands;

		// runSync delegation
		await commands['arete-sync'].callback();
		expect(plugin.syncService.runSync).toHaveBeenCalled();

		// prune delegation
		await commands['arete-sync-prune'].callback();
		expect(plugin.syncService.runSync).toHaveBeenCalledWith(
			true,
			null,
			false,
			expect.any(Function),
		);
	});

	test('commands delegate to CheckService', async () => {
		const commands = (global as any).registeredCommands;

		// check-file delegation
		const mockView = { file: { path: 'test.md' } };
		await commands['arete-check-file'].editorCallback(null, mockView);
		expect(plugin.checkService.runCheck).toHaveBeenCalledWith('/mock/vault/path/test.md');

		// integrity delegation
		await commands['arete-check-integrity'].callback();
		expect(plugin.checkService.checkVaultIntegrity).toHaveBeenCalled();
	});
});
