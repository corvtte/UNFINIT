import sys

c = open('services/web_panel.py', encoding='utf-8').read()

old_transfer = '''function transferFeedDownload(url, title, audioUrl, videoUrl, sourceUrl) {{
            openFeedDispatchModal(url, title, audioUrl, videoUrl, sourceUrl);
        }}'''

new_transfer = '''async function transferFeedDownload(url, title, audioUrl, videoUrl, sourceUrl, btn) {{
            if (!audioUrl && !videoUrl) {{
                const badge = document.getElementById('crawlerStatusBadge');
                if (badge && badge.innerText.includes('OFFLINE')) {{
                    showToast('شما به حساب مرجع متصل نیستید. لطفاً ابتدا وارد حساب شوید.');
                    const m = document.getElementById('feedAuthModal');
                    if (m) m.classList.remove('hidden');
                    return;
                }}
                if (sourceUrl) {{
                    try {{
                        const loadingToast = document.createElement('div');
                        loadingToast.id = 'rescrapToast';
                        loadingToast.className = 'fixed bottom-4 right-4 bg-slate-800 border border-orange-500 text-white px-4 py-2 rounded-xl text-xs z-50';
                        loadingToast.innerText = '⏳ در حال دریافت لینک‌های دانلود از سایت اصلی...';
                        document.body.appendChild(loadingToast);

                        const res = await fetch('/api/crawler/rescrap-item', {{ method: 'POST', body: JSON.stringify({{ url: sourceUrl }}) }});
                        const data = await res.json();
                        document.body.removeChild(loadingToast);
                        if (data.ok && (data.audio_url || data.video_url || data.url)) {{
                            if (btn && btn.parentElement) {{
                                const safeA = (data.audio_url || '').replace(/'/g, "\\\\'");
                                const safeV = (data.video_url || '').replace(/'/g, "\\\\'");
                                let newHtml = '<div class="grid grid-cols-2 gap-2">';
                                if (data.audio_url) {{
                                    newHtml += '<button type="button" onclick="transferFeedDownload(\\\\'' + url + '\\\\', \\\\'' + title + '\\\\', \\\\'' + safeA + '\\\\', \\\\'' + safeV + '\\\\', \\\\'' + sourceUrl + '\\\\', this)" class="w-full py-1.5 px-2 rounded-lg bg-slate-800/80 hover:bg-slate-700/80 text-slate-300 border border-slate-700/50 flex items-center justify-center gap-1.5 transition text-xs font-medium"><svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z"/></svg><span>صوت</span></button>';
                                }} else {{
                                    newHtml += '<div></div>';
                                }}
                                if (data.video_url) {{
                                    newHtml += '<button type="button" onclick="transferFeedDownload(\\\\'' + url + '\\\\', \\\\'' + title + '\\\\', \\\\'' + safeA + '\\\\', \\\\'' + safeV + '\\\\', \\\\'' + sourceUrl + '\\\\', this)" class="w-full py-1.5 px-2 rounded-lg bg-slate-800/80 hover:bg-slate-700/80 text-slate-300 border border-slate-700/50 flex items-center justify-center gap-1.5 transition text-xs font-medium"><svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg><span>ویدیو</span></button>';
                                }} else {{
                                    newHtml += '<div></div>';
                                }}
                                newHtml += '</div>';
                                btn.outerHTML = newHtml;
                            }}
                            openFeedDispatchModal(data.url || data.audio_url || data.video_url, title, data.audio_url, data.video_url, sourceUrl);
                        }} else {{
                            showToast('❌ آدرس دانلودی برای این آیتم در سرور یافت نشد.');
                        }}
                    }} catch (e) {{
                        const tb = document.getElementById('rescrapToast');
                        if (tb) tb.remove();
                        showToast('❌ خطای ارتباط با سرور: ' + e.message);
                    }}
                }} else {{
                    showToast('❌ آدرس دانلودی برای این آیتم یافت نشد.');
                }}
            }} else {{
                openFeedDispatchModal(url, title, audioUrl, videoUrl, sourceUrl);
            }}
        }}'''

old_open = '''async function openFeedDispatchModal(url, title, audioUrl, videoUrl, sourceUrl) {{
            if (!url && !audioUrl && !videoUrl) {{
                if (sourceUrl) {{
                    try {{
                        const loadingToast = document.createElement('div');
                        loadingToast.id = 'rescrapToast';
                        loadingToast.className = 'fixed bottom-4 right-4 bg-slate-800 border border-orange-500 text-white px-4 py-2 rounded-xl text-xs z-50';
                        loadingToast.innerText = '⏳ در حال دریافت لینک‌های دانلود از سایت اصلی...';
                        document.body.appendChild(loadingToast);

                        const res = await fetch('/api/crawler/rescrap-item', {{ method: 'POST', body: JSON.stringify({{ url: sourceUrl }}) }});
                        const data = await res.json();
                        document.body.removeChild(loadingToast);
                        if (data.ok && (data.audio_url || data.video_url || data.url)) {{
                            return openFeedDispatchModal(data.url || data.audio_url || data.video_url, title, data.audio_url, data.video_url, sourceUrl);
                        }} else {{
                            showToast('❌ آدرس دانلودی برای این آیتم در سرور یافت نشد.');
                            return;
                        }}
                    }} catch (e) {{
                        const tb = document.getElementById('rescrapToast');
                        if (tb) tb.remove();
                        showToast('❌ خطای ارتباط با سرور: ' + e.message);
                        return;
                    }}
                }} else {{
                    showToast('❌ آدرس دانلودی برای این آیتم یافت نشد.');
                    return;
                }}
            }}
            pendingFeedAudioUrl = audioUrl || (url && url.toLowerCase().endsWith('.mp3') ? url : '');
            pendingFeedVideoUrl = videoUrl || (url && url.toLowerCase().endsWith('.mp4') ? url : '');
            if (!pendingFeedAudioUrl && !pendingFeedVideoUrl) {{
                pendingFeedAudioUrl = url;
            }}
            pendingFeedDispatchUrl = pendingFeedAudioUrl || pendingFeedVideoUrl || url;
            pendingFeedDispatchTitle = title || 'هدیه دانلودی';
            const titleEl = document.getElementById('feedDispatchModalTitle');
            if (titleEl) titleEl.textContent = pendingFeedDispatchTitle;

            setDispatchFormat(pendingFeedAudioUrl ? 'audio' : 'video');'''

new_open = '''function openFeedDispatchModal(url, title, audioUrl, videoUrl, sourceUrl) {{
            pendingFeedAudioUrl = audioUrl || (url && url.toLowerCase().endsWith('.mp3') ? url : '');
            pendingFeedVideoUrl = videoUrl || (url && url.toLowerCase().endsWith('.mp4') ? url : '');
            if (!pendingFeedAudioUrl && !pendingFeedVideoUrl) {{
                pendingFeedAudioUrl = url;
            }}
            pendingFeedDispatchUrl = pendingFeedAudioUrl || pendingFeedVideoUrl || url;
            pendingFeedDispatchTitle = title || 'هدیه دانلودی';
            const titleEl = document.getElementById('feedDispatchModalTitle');
            if (titleEl) titleEl.textContent = pendingFeedDispatchTitle;

            setDispatchFormat(pendingFeedAudioUrl ? 'audio' : 'video');'''

c = c.replace(old_transfer, new_transfer)
c = c.replace(old_open, new_open)

open('services/web_panel.py', 'w', encoding='utf-8').write(c)
print('Updated Javascript successfully')
