module.exports = {
	preset: 'ts-jest',
	testEnvironment: 'node',
	moduleFileExtensions: ['ts', 'js'],
	transform: {
		'^.+\\.ts$': 'ts-jest',
	},
	testMatch: ['**/tests/**/*.test.ts'],
	collectCoverage: true,
	coverageThreshold: {
		global: {
			branches: 80,
			functions: 92,
			lines: 95,
			statements: 94,
		},
	},
};
