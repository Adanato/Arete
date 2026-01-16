import { AretePluginSettings } from '../../domain/settings';
import { requestUrl } from 'obsidian';

export interface AgentResponse {
	chat_message: string;
	suggested_questions: string[];
	action_taken: string | null;
}

export class AgentService {
	constructor(private settings: AretePluginSettings) {}

	async chat(message: string): Promise<AgentResponse> {
		if (this.settings.execution_mode !== 'server') {
			throw new Error('Arete Server is not running. Please enable Server mode in settings.');
		}

		if (!this.settings.ai_api_key) {
			throw new Error('AI API Key is missing. Please configure it in settings.');
		}

		const port = this.settings.server_port || 8777;
		const url = `http://localhost:${port}/agent/chat`;

		try {
			const response = await requestUrl({
				url: url,
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
				},
				body: JSON.stringify({
					message: message,
					api_key: this.settings.ai_api_key,
					provider: this.settings.ai_provider,
				}),
			});

			if (response.status !== 200) {
				const errorDetail = response.text || 'No detail provided';
				throw new Error(`Server returned status ${response.status}: ${errorDetail}`);
			}

			return response.json as AgentResponse;
		} catch (error) {
			console.error('Arete Agent Error:', error);
			throw error;
		}
	}
}
