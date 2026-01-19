module.exports = {
	preset: 'ts-jest',
	testEnvironment: 'node',
	moduleFileExtensions: ['ts', 'js'],
	transform: {
		'^.+\\.ts$': 'ts-jest',
	},
	transformIgnorePatterns: ['node_modules/(?!((d3.*)|internmap|delaunator|robust-predicates))'],
	testMatch: ['**/tests/**/*.test.ts'],
	collectCoverage: true,
	coverageThreshold: {
		global: {
			branches: 5,
			functions: 5,
			lines: 5,
			statements: 5,
		},
	},
	moduleNameMapper: {
		'^@/(.*)$': '<rootDir>/src/$1',
		'^@domain/(.*)$': '<rootDir>/src/domain/$1',
		'^@application/(.*)$': '<rootDir>/src/application/$1',
		'^@infrastructure/(.*)$': '<rootDir>/src/infrastructure/$1',
		'^@presentation/(.*)$': '<rootDir>/src/presentation/$1',
		'^obsidian$': '<rootDir>/tests/obsidian-mock.ts',
		'^d3$': '<rootDir>/tests/mocks/d3.mock.ts',
		'^3d-force-graph$': '<rootDir>/tests/mocks/3d-force-graph.mock.ts',
	},
	setupFilesAfterEnv: ['<rootDir>/tests/test-setup.ts'],
};
