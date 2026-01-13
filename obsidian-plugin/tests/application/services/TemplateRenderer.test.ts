import { TemplateRenderer } from '@/application/services/TemplateRenderer';
import { AnkiConnectRepository } from '@/infrastructure/anki/AnkiConnectRepository';
import { App, MarkdownRenderer } from 'obsidian';

jest.mock('@/infrastructure/anki/AnkiConnectRepository');

describe('TemplateRenderer', () => {
	let renderer: TemplateRenderer;
	let mockApp: App;
	let mockRepo: jest.Mocked<AnkiConnectRepository>;

	beforeEach(() => {
		mockApp = new (jest.requireMock('obsidian').App)() as App;
		mockRepo = new AnkiConnectRepository(
			'http://localhost:8765',
		) as jest.Mocked<AnkiConnectRepository>;

		// Setup default mocks for repo
		(AnkiConnectRepository as jest.Mock).mockImplementation(() => mockRepo);
		mockRepo.modelStyling.mockResolvedValue('.card { color: black; }');
		// Return a nested structure as expected now
		mockRepo.modelTemplates.mockResolvedValue({
			'Card 1': {
				Front: '{{Front}}',
				Back: '{{FrontSide}}<hr id=answer>{{Back}}',
			},
		});

		renderer = new TemplateRenderer(mockApp, 'http://localhost:8765');
	});

	it('should use MarkdownRenderer in obsidian mode', async () => {
		renderer.setMode('obsidian');

		// Mock MarkdownRenderer behavior
		(MarkdownRenderer.render as jest.Mock).mockImplementation(async (app, val, el) => {
			el.innerHTML = `<b>${val.replace(/\*\*/g, '')}</b>`; // Simple mock transform
		});

		const result = await renderer.render('Basic', 'Front', { Front: '**Bold Text**' });

		expect(MarkdownRenderer.render).toHaveBeenCalled();
		expect(result?.html).toContain('<b>Bold Text</b>');
	});

	it('should NOT use MarkdownRenderer in anki mode', async () => {
		renderer.setMode('anki');
		(MarkdownRenderer.render as jest.Mock).mockClear();

		const result = await renderer.render('Basic', 'Front', { Front: '**Bold Text**' });

		expect(MarkdownRenderer.render).not.toHaveBeenCalled();
		// Assuming the template just renders the field
		expect(result?.html).toContain('**Bold Text**');
	});

	it('should unescape HTML tags in Mustache templates', async () => {
		renderer.setMode('obsidian');

		// Mock MD render to return HTML
		(MarkdownRenderer.render as jest.Mock).mockImplementation(async (app, val, el) => {
			el.innerHTML = '<p>Paragraph</p>';
		});

		const result = await renderer.render('Basic', 'Front', { Front: 'Text' });

		// If escaped: &lt;p&gt;Paragraph&lt;/p&gt;
		// If unescaped: <p>Paragraph</p>
		expect(result?.html).toContain('<p>Paragraph</p>');
		expect(result?.html).not.toContain('&lt;p&gt;');
	});
});
