import os

p = 'services/web_panel.py'
text = open(p, encoding='utf-8').read()
svg = '<svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/><path stroke-linecap="round" stroke-linejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/></svg>'
text = text.replace('>👁️</button>', '>' + svg + '</button>').replace('>👁</button>', '>' + svg + '</button>')
text = text.replace('🔒', '<svg class="w-4 h-4 inline-block align-middle" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"/></svg>')

# Also remove hardcoded dark blue backgrounds per rule
# The rule says: "Remove all inline custom color overrides (like arbitrary dark-blue backgrounds). Use existing UNFINIT Hub theme CSS classes/variables."
# Wait, let's just do emojis first.
open(p, 'w', encoding='utf-8').write(text)
