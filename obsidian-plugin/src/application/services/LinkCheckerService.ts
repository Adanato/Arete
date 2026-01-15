import { App, TFile } from 'obsidian';

export interface BrokenReference {
	sourceFile: TFile;
	linkText: string;
	linkPath: string; // The resolved path we tried to find
	type: 'link' | 'image' | 'invalid-yaml';
	position: {
		start: { line: number; col: number; offset: number };
		end: { line: number; col: number; offset: number };
	} | null;
}

export class LinkCheckerService {
	app: App;

	constructor(app: App) {
		this.app = app;
	}

	/**
	 * Scans the provided files (or all markdown files if none provided) for broken links/embeds.
	 */
	async checkIntegrity(files?: TFile[]): Promise<BrokenReference[]> {
		const targetFiles = files || this.app.vault.getMarkdownFiles();
		const allBroken: BrokenReference[] = [];

		for (const file of targetFiles) {
			// 1. Check Links & Embeds
			const brokenRefs = this.getBrokenReferences(file);
			allBroken.push(...brokenRefs);

			// 2. Check Invalid Frontmatter (User Request)
			const invalidYaml = await this.getInvalidFrontmatter(file);
			if (invalidYaml) {
				allBroken.push(invalidYaml);
			}
		}

		return allBroken;
	}

	getBrokenReferences(file: TFile): BrokenReference[] {
		const cache = this.app.metadataCache.getFileCache(file);
		if (!cache) return [];

		const broken: BrokenReference[] = [];

		const hasYamlCards =
			cache.frontmatter && cache.frontmatter.cards && Array.isArray(cache.frontmatter.cards);

		if (hasYamlCards) {
			// 1. Deep Scan YAML Cards (User Request: "Only report inside the card list")
			const cards = cache.frontmatter.cards;
			cards.forEach((card: any, idx: number) => {
				// Fields to check: Front, Back, Text, Extra
				const fields = [
					card.Front,
					card.front,
					card.Back,
					card.back,
					card.Text,
					card.text,
					card.Extra,
					card.extra,
				];

				fields.forEach((content) => {
					if (typeof content === 'string') {
						this.scanTextForBrokenLinks(content, file, broken, `Card #${idx + 1}`);
					}
				});
			});
		} else {
			// 2. Standard Body Scan (Only if NOT a YAML card file)

			// Check Links
			if (cache.links) {
				for (const link of cache.links) {
					const dest = this.app.metadataCache.getFirstLinkpathDest(link.link, file.path);
					if (!dest) {
						broken.push({
							sourceFile: file,
							linkText: link.original,
							linkPath: link.link,
							type: 'link',
							position: link.position,
						});
					}
				}
			}

			// Check Embeds (Images, Transclusions)
			if (cache.embeds) {
				for (const embed of cache.embeds) {
					const dest = this.app.metadataCache.getFirstLinkpathDest(embed.link, file.path);
					if (!dest) {
						broken.push({
							sourceFile: file,
							linkText: embed.original,
							linkPath: embed.link,
							type: 'image', // simplified type, could be note embed too
							position: embed.position,
						});
					}
				}
			}
		}

		return broken;
	}

	private scanTextForBrokenLinks(
		text: string,
		file: TFile,
		brokenList: BrokenReference[],
		context: string,
	) {
		// Regex for [[wikilinks]] and ![[embeds]]
		const linkRegex = /(!?)\[\[([^|\]]+)(?:\|[^\]]+)?\]\]/g;
		let match;

		while ((match = linkRegex.exec(text)) !== null) {
			const isEmbed = match[1] === '!';
			const linkPath = match[2]; // The path part
			const original = match[0];

			const dest = this.app.metadataCache.getFirstLinkpathDest(linkPath, file.path);

			if (!dest) {
				brokenList.push({
					sourceFile: file,
					linkText: `${context}: ${original}`, // Add context since we lack line numbers
					linkPath: linkPath,
					type: isEmbed ? 'image' : 'link',
					position: null, // Cannot determining exact line in YAML easily
				});
			}
		}
	}

	async getInvalidFrontmatter(file: TFile): Promise<BrokenReference | null> {
		const cache = this.app.metadataCache.getFileCache(file);

		// If cache parses frontmatter fine, we are good.
		if (cache && cache.frontmatter) return null;

		// If no frontmatter in cache, check if file actually HAS valid-looking YAML start
		// Only read file if cache implies no frontmatter to save IO?
		// Actually cache is always loaded in memory but file content might be read.
		// Obsidian API: valid frontmatter means `cache.frontmatter` exists.

		const content = await this.app.vault.read(file);
		const trimmed = content.trimStart();
		if (trimmed.startsWith('---\n') || trimmed.startsWith('---\r\n')) {
			// File has YAML block start, but cache didn't parse it -> Invalid!
			return {
				sourceFile: file,
				linkText: 'INVALID YAML',
				linkPath: 'Frontmatter',
				type: 'invalid-yaml',
				position: null, // Info not available from cache failure
			};
		}
		return null;
	}
}
