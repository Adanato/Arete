export const select = jest.fn(() => ({
	selectAll: jest.fn(() => ({
		data: jest.fn(() => ({
			join: jest.fn(() => ({
				attr: jest.fn(),
				on: jest.fn(),
				call: jest.fn(),
				append: jest.fn(),
			})),
		})),
	})),
	append: jest.fn(() => ({
		attr: jest.fn(),
		style: jest.fn(),
	})),
	call: jest.fn(),
}));

export const zoom = jest.fn(() => ({
	on: jest.fn(),
	scaleExtent: jest.fn(),
}));

export const drag = jest.fn(() => ({
	on: jest.fn(),
}));

export const forceSimulation = jest.fn(() => ({
	force: jest.fn(),
	on: jest.fn(),
}));

export const forceLink = jest.fn(() => ({
	id: jest.fn(),
}));

export const forceManyBody = jest.fn();
export const forceCenter = jest.fn();
export const forceCollide = jest.fn();

export const zoomIdentity = {
	translate: jest.fn(),
	scale: jest.fn(),
};
