import './test-setup';
import { App } from 'obsidian';
import O2APlugin, { CheckResultModal } from '../main';
import { createMockElement } from './test-setup';

describe('CheckResultModal Deep Coverage', () => {
	let plugin: O2APlugin;
	let app: App;
	let modal: CheckResultModal;

	beforeEach(() => {
		jest.clearAllMocks();
		app = new App();
		plugin = {
			runFix: jest.fn().mockResolvedValue(undefined),
			runCheck: jest.fn().mockResolvedValue(undefined),
		} as any;
	});

	test('Auto-Fix button interaction', async () => {
		const result = {
			ok: false,
			errors: [{ line: 1, message: 'Tab Character Error' }],
		};
		modal = new CheckResultModal(app, plugin, result, '/path/to/file.md');

		let capturedBtn: any;
		modal.contentEl.createDiv = jest.fn().mockImplementation((opts) => {
			const div = createMockElement('div', opts);
			div.createEl = jest.fn().mockImplementation((tag, o) => {
				const el = createMockElement(tag, o);
				if (tag === 'button') capturedBtn = el;
				return el;
			});
			return div;
		});

		modal.onOpen();

		expect(capturedBtn).toBeDefined();
		const clickHandler = capturedBtn._listeners?.['click'];
		if (clickHandler) await clickHandler({ target: capturedBtn } as any);

		expect(capturedBtn.disabled).toBe(true);
		expect(capturedBtn.setText).toHaveBeenCalledWith('Fixing...');
		expect(plugin.runFix).toHaveBeenCalledWith('/path/to/file.md');
		expect(plugin.runCheck).toHaveBeenCalledWith('/path/to/file.md');
	});

	test('onOpen with ok: true constructs stats UI', () => {
		const result = { ok: true, stats: { deck: 'TestDeck', cards_found: 5 } };
		modal = new CheckResultModal(app, plugin, result, '/path/to/note.md');
		modal.onOpen();
		expect(modal.contentEl.createEl).toHaveBeenCalledWith('ul', expect.any(Object));
	});

	test('onClose empties contentEl', () => {
		modal = new CheckResultModal(app, plugin, { ok: true }, '/path/to/note.md');
		modal.onClose();
		expect(modal.contentEl.empty).toHaveBeenCalled();
	});
});
