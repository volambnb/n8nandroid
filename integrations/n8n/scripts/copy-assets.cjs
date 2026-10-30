const fs = require('node:fs');
const path = require('node:path');

const source = path.join(__dirname, '..', 'nodes', 'AutoIXB', 'autoixb.svg');
const destination = path.join(__dirname, '..', 'dist', 'nodes', 'AutoIXB', 'autoixb.svg');
fs.mkdirSync(path.dirname(destination), { recursive: true });
fs.copyFileSync(source, destination);
