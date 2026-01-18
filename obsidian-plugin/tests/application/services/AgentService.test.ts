import '../../test-setup';
import { requestUrl } from 'obsidian';
import { AgentService } from '@application/services/AgentService';

describe('AgentService', () => {
	let service: AgentService;
	let settings: any;

	beforeEach(() => {
		jest.clearAllMocks();
		settings = {
			execution_mode: 'server',
			ai_api_key: 'test-key',
			ai_provider: 'openai',
			server_port: 8777,
		};
		service = new AgentService(settings);
	});

	test('chat sends request in server mode', async () => {
		(requestUrl as jest.Mock).mockResolvedValue({
			status: 200,
			json: { chat_message: 'hello' },
		});

		const response = await service.chat('hi');
		expect(response.chat_message).toBe('hello');
		expect(requestUrl).toHaveBeenCalledWith(
			expect.objectContaining({
				method: 'POST',
				url: 'http://localhost:8777/agent/chat',
			}),
		);
	});

	test('chat throws error if not in server mode', async () => {
		settings.execution_mode = 'cli';
		await expect(service.chat('hi')).rejects.toThrow('Arete Server is not running');
	});

	test('chat throws error if API key missing', async () => {
		settings.ai_api_key = '';
		await expect(service.chat('hi')).rejects.toThrow('AI API Key is missing');
	});

	test('chat handles non-200 response', async () => {
		(requestUrl as jest.Mock).mockResolvedValue({
			status: 500,
			text: 'Internal Error',
		});
		await expect(service.chat('hi')).rejects.toThrow(
			'Server returned status 500: Internal Error',
		);
	});

	test('chat handles request error', async () => {
		(requestUrl as jest.Mock).mockRejectedValue(new Error('Network error'));
		await expect(service.chat('hi')).rejects.toThrow('Network error');
	});
});
