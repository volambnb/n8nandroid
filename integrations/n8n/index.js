'use strict';

module.exports = {
	nodes: [require('./dist/nodes/AutoIXB/AutoIXB.node.js').AutoIXB],
	credentials: [require('./dist/credentials/AutoIxbApi.credentials.js').AutoIxbApi],
};
