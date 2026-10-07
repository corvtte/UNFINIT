const fs = require('fs');

const html = fs.readFileSync('debug_panel.html', 'utf8');

// Match all script blocks except those with src=
const scriptRegex = /<script\b[^>]*>([\s\S]*?)<\/script>/gi;

let match;
let i = 0;
while ((match = scriptRegex.exec(html)) !== null) {
    const code = match[1].trim();
    if (code.length > 0) {
        fs.writeFileSync(`test_script_${i}.js`, code);
        console.log(`Extracted script ${i} (${code.length} bytes)`);
        i++;
    }
}
