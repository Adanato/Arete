import { requestUrl } from 'obsidian';

export class AnkiConnectRepository {
	private url: string;

	constructor(url = 'http://127.0.0.1:8765') {
		this.url = url;
	}

	async invoke(action: string, params: any = {}): Promise<any> {
		console.log(`[Arete] AnkiConnect Invoke: ${action}`, params);
		try {
			const response = await requestUrl({
				url: this.url,
				method: 'POST',
				body: JSON.stringify({ action, version: 6, params }),
			});

			const result = response.json;
			if (result.error) {
				throw new Error(result.error);
			}
			return result.result;
		} catch (error) {
			console.error(`AnkiConnect Error (${action}):`, error);
			throw error;
		}
	}

	async modelStyling(modelName: string): Promise<string> {
		return this.invoke('modelStyling', { modelName });
	}

	async modelTemplates(
		modelName: string,
	): Promise<Record<string, { Front: string; Back: string }>> {
		return this.invoke('modelTemplates', { modelName });
	}

	async version(): Promise<number> {
		return this.invoke('version');
	}

	async suspendCards(cardIds: number[]): Promise<boolean> {
		return this.invoke('suspend', { cards: cardIds });
	}

	async unsuspendCards(cardIds: number[]): Promise<boolean> {
		return this.invoke('unsuspend', { cards: cardIds });
	}

	async getCardInfo(cardIds: number[]): Promise<any[]> {
		return this.invoke('cardsInfo', { cards: cardIds });
	}
}
