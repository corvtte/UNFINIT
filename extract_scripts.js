const fs = require('fs');
const html = fs.readFileSync('rendered_dashboard.html', 'utf-8');

const regex = /<script>([\s\S]*?)<\/script>/g;
let match;
let count = 0;

while ((match = regex.exec(html)) !== null) {
    count++;
    const code = match[1];
    fs.writeFileSync(`script_block_${count}.js`, code);
    console.log(`Extracted block ${count} to script_block_${count}.js`);
}
