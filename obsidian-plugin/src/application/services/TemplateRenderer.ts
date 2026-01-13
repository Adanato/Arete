import Mustache from 'mustache';
import { AnkiConnectRepository } from '@/infrastructure/anki/AnkiConnectRepository';
import { App, MarkdownRenderer } from 'obsidian';

interface ModelData {
	css: string;
	templates: Record<string, { Front: string; Back: string }>;
}

export class TemplateRenderer {
	private repo: AnkiConnectRepository;
	private cache: Map<string, ModelData> = new Map();
	private app: App;
	private mode: 'obsidian' | 'anki' = 'obsidian';

	constructor(app: App, ankiUrl?: string) {
		this.app = app;
		this.repo = new AnkiConnectRepository(ankiUrl);
	}

	setMode(mode: 'obsidian' | 'anki') {
		this.mode = mode;
	}

	async preloadModel(modelName: string): Promise<void> {
		console.log(`[Arete] Preloading model: ${modelName}`);
		if (this.cache.has(modelName)) {
			console.log(`[Arete] Model ${modelName} found in cache.`);
			return;
		}

		try {
			const [css, templates] = await Promise.all([
				this.repo.modelStyling(modelName),
				this.repo.modelTemplates(modelName),
			]);
			this.cache.set(modelName, { css, templates });
			console.log(`[Arete] Model ${modelName} cached successfully.`);
		} catch (e) {
			console.warn(`Failed to load model data for ${modelName}`, e);
			// Don't throw, just let render fail gracefully
		}
	}

	async render(
		modelName: string,
		templateType: 'Front' | 'Back',
		fields: Record<string, string>,
	): Promise<{ html: string; css: string } | null> {
		console.log(`[Arete] Render request for ${modelName} (${templateType})`);
		if (!this.cache.has(modelName)) {
			await this.preloadModel(modelName);
		}

		const data = this.cache.get(modelName);
		if (!data) return null;

		// Retrieve keys of the returned templates object (e.g., ["Card 1", "Card 2"])
		const cardTypeNames = Object.keys(data.templates);
		if (cardTypeNames.length === 0) {
			console.warn(`[Arete] No card templates found for model: ${modelName}`);
			return null;
		}

		// Default to the first card type found (e.g., "Card 1")
		// TODO: In the future, allow picking specific card type if needed.
		const cardTypeName = cardTypeNames[0];
		const cardTemplates = data.templates[cardTypeName] as any; // Cast to any because TS Record<string, string> doesn't match nested object

		console.log(`[Arete] Using Card Type: ${cardTypeName}`, cardTemplates);

		const template = cardTemplates[templateType]; // 'Front' or 'Back'
		if (!template) {
			console.warn(
				`[Arete] Template type '${templateType}' not found in card '${cardTypeName}'`,
			);
			return null;
		}

		// Create a view with case-insensitive fallback and useful variants
		const view: Record<string, string> = {};

		// Render markdown for all fields first if in Obsidian mode
		const renderedFields: Record<string, string> = {};

		if (this.mode === 'obsidian') {
			for (const key of Object.keys(fields)) {
				const val = fields[key];
				if (!val) {
					renderedFields[key] = '';
					continue;
				}

				// Create a dummy container to render into
				const dummy = document.createElement('div');
				dummy.style.display = 'none'; // Hide it
				document.body.appendChild(dummy); // Attach to DOM for MathJax measurement

				try {
					// Use MarkdownRenderer to render the field value (handles MD + LaTeX)
					await MarkdownRenderer.render(this.app, val, dummy, '', null as any);
					renderedFields[key] = dummy.innerHTML;
				} finally {
					document.body.removeChild(dummy); // Cleanup
				}
			}
		} else {
			// Anki Mode: Pass raw fields
			Object.assign(renderedFields, fields);
		}

		Object.assign(view, renderedFields);
		Object.keys(renderedFields).forEach((key) => {
			const val = renderedFields[key];
			const lower = key.toLowerCase();
			const capital = lower.charAt(0).toUpperCase() + lower.slice(1);
			if (!(lower in view)) view[lower] = val;
			if (!(capital in view)) view[capital] = val;
		});

		console.log('[Arete] Template Render View:', view);
		console.log(`[Arete] Template raw (${templateType}):`, template);

		// Helper to force unescaped variables in template
		const makeUnescaped = (tmpl: string) => {
			// Replace {{Var}} with {{{Var}}} to prevent escaping HTML
			// Avoids {{#Section}}, {{/Section}}, {{^Invert}}, {{&Unescaped}}, {{{Triple}}}
			return tmpl.replace(/\{\{(?!\{|#|\^|\/|&)(.+?)\}\}/g, '{{{$1}}}');
		};

		if (templateType === 'Back' && cardTemplates['Front']) {
			try {
				// We need Front rendered content for {{FrontSide}}
				// Also unescape the front template locally
				const frontTmpl = makeUnescaped(cardTemplates['Front']);
				const frontHtml = Mustache.render(frontTmpl, view);
				view['FrontSide'] = frontHtml;
			} catch (e) {
				console.warn('Failed to render FrontSide', e);
			}
		}

		try {
			// Unescape the main template
			const finalTemplate = makeUnescaped(template);
			const html = Mustache.render(finalTemplate, view);
			console.log(`[Arete] Rendered HTML (${templateType}):`, html);
			return { html, css: data.css };
		} catch (e) {
			console.error('Mustache render error', e);
			return null;
		}
	}
}
