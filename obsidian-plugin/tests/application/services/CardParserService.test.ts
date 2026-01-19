import { CardParserService } from '@/application/services/CardParserService';

// Mock Obsidian's parseYaml since it's not available in Node/Jest environment
jest.mock('obsidian', () => ({
	parseYaml: jest.fn((text: string) => {
		// Very basic YAML parser simulation for testing
		const data: any = {};
		const lines = text.split('\n');
		for (const line of lines) {
			const nidMatch = line.match(/['"]?(?:nid|NID)['"]?\s*:\s*['"]?(\d+)/i);
			if (nidMatch) data.nid = nidMatch[1];
			const cidMatch = line.match(/['"]?(?:cid|CID)['"]?\s*:\s*['"]?(\d+)/i);
			if (cidMatch) data.cid = cidMatch[1];
		}
		return data;
	}),
}));

describe('CardParserService', () => {
	const musclesYaml = `---
aliases: null
arete: true
cards:
  - model: Basic
    Front: |-
      ![[Foot Muscles.png]] What is #1?
    Back: |-
      1. Peroneus Longus ![[Foot Muscles Legend.png]]
    nid: 1762277751241
    cid: 1762277751241
  - model: Basic
    Front: |-
      ![[Foot Muscles.png]] What is #2?
    Back: |-
      2. Peroneus Brevis ![[Foot Muscles Legend.png]]
    nid: '1762277751465'
    cid: '1762277751465'
---
# Muscles of the Foot
`;

	it('should parse 13-digit NIDs correctly (unquoted)', () => {
		const result = CardParserService.parseCards(musclesYaml);
		expect(result.ranges.length).toBe(2);
		expect(result.ranges[0].nid).toBe(1762277751241);
	});

	it('should parse 13-digit NIDs correctly (quoted)', () => {
		const result = CardParserService.parseCards(musclesYaml);
		expect(result.ranges.length).toBe(2);
		expect(result.ranges[1].nid).toBe(1762277751465);
	});

	it('should identify line ranges correctly', () => {
		const result = CardParserService.parseCards(musclesYaml);
		// Card 1 starts at index line 4 (0-indexed) where "- model: Basic" is
		// --- (0)
		// aliases (1)
		// arete (2)
		// cards: (3)
		// - model: Basic (4)
		expect(result.ranges[0].startLine).toBe(4);
		
		// Card 1 ends where "cid: 1762277751241" is (line 10)
		expect(result.ranges[0].endLine).toBe(10);
	});

	it('should find frontmatter end line', () => {
		const result = CardParserService.parseCards(musclesYaml);
		expect(result.frontmatterEndLine).toBe(18);
	});

    it('should handle missing nid/cid gracefully', () => {
        const partialYaml = `---
cards:
  - model: Basic
    front: dummy
---`;
        const result = CardParserService.parseCards(partialYaml);
        expect(result.ranges.length).toBe(1);
        expect(result.ranges[0].nid).toBeNull();
    });
});
