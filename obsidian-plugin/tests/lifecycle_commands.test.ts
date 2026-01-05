import './test-setup';
import { App } from 'obsidian';
import AretePlugin from '../main';

describe('AretePlugin Lifecycle and Commands', () => {
	let plugin: AretePlugin;
	let app: App;

	beforeEach(() => {
		app = new App();
		plugin = new AretePlugin(app, { dir: 'test-plugin-dir' } as any);
		// Mock required methods
		plugin.loadSettings = jest.fn().mockResolvedValue(undefined);
		plugin.addStatusBarItem = jest.fn().mockImplementation(() => ({
			empty: jest.fn(),
			setText: jest.fn(),
			createSpan: jest.fn().mockImplementation(() => ({ setText: jest.fn() })),
		}));
		plugin.addRibbonIcon = jest.fn().mockImplementation((icon, title, cb) => {
			return { icon, title, cb };
		});
		plugin.addCommand = jest.fn();
		plugin.addSettingTab = jest.fn();
	});

	test('onload initializes plugin components', async () => {
		await plugin.onload();
		expect(plugin.loadSettings).toHaveBeenCalled();
		expect(plugin.addStatusBarItem).toHaveBeenCalled();
		expect(plugin.addRibbonIcon).toHaveBeenCalled();
		expect(plugin.addCommand).toHaveBeenCalled();
		expect(plugin.addSettingTab).toHaveBeenCalled();
	});

	test('ribbon icon click triggers Sync', async () => {
		await plugin.onload();
		const ribbonMock = (plugin.addRibbonIcon as jest.Mock).mock.results[0].value;
		const runSyncSpy = jest.spyOn(plugin, 'runSync').mockImplementation();

		ribbonMock.cb({} as any);
		expect(runSyncSpy).toHaveBeenCalled();
		runSyncSpy.mockRestore();
	});

	test('command callbacks trigger correct methods', async () => {
		await plugin.onload();
		const commands = (plugin.addCommand as jest.Mock).mock.calls;

		const syncCmd = commands.find((c) => c[0].id === 'arete-sync')[0];
		const runSyncSpy = jest.spyOn(plugin, 'runSync').mockImplementation();
		syncCmd.callback();
		expect(runSyncSpy).toHaveBeenCalled();

		const integrityCmd = commands.find((c) => c[0].id === 'arete-check-integrity')[0];
		const integritySpy = jest.spyOn(plugin, 'checkVaultIntegrity').mockImplementation();
		integrityCmd.callback();
		expect(integritySpy).toHaveBeenCalled();

		const pruneCmd = commands.find((c) => c[0].id === 'arete-sync-prune')[0];
		pruneCmd.callback();
		expect(runSyncSpy).toHaveBeenCalledWith(true);

		runSyncSpy.mockRestore();
		integritySpy.mockRestore();
	});

	test('updateStatusBar all states', () => {
		plugin.statusBarItem = plugin.addStatusBarItem() as any;

		plugin.updateStatusBar('idle');
		expect(plugin.statusBarItem.empty).toHaveBeenCalled();

		plugin.updateStatusBar('syncing');
		expect(plugin.statusBarItem.createSpan).toHaveBeenCalledWith(
			expect.objectContaining({ text: 'Anki Syncing...' }),
		);

		plugin.updateStatusBar('error', 'Auth Failed');
		expect(plugin.statusBarItem.setText).toHaveBeenCalledWith('❌ Sync Error');
		expect(plugin.statusBarItem.title).toBe('Auth Failed');
	});

	test('onunload empties status bar', () => {
		plugin.statusBarItem = plugin.addStatusBarItem() as any;
		plugin.onunload();
		expect(plugin.statusBarItem.empty).toHaveBeenCalled();
	});
});
