
                window.showToast = function(msg, type='info') {
            const container = document.getElementById('toast-container') || (function() {
                const c = document.createElement('div');
                c.id = 'toast-container';
                c.className = 'fixed bottom-4 right-4 z-[9999] flex flex-col gap-2';
                document.body.appendChild(c);
                return c;
            })();
            
            const cleanMsg = msg.replace(/^[❌✅]/, '').trim();
            for (const el of container.children) {
                if (el.dataset.msg === cleanMsg) {
                    clearTimeout(el.toastTimer);
                    el.toastTimer = setTimeout(() => {
                        el.classList.add('translate-x-full', 'opacity-0');
                        setTimeout(() => el.remove(), 300);
                    }, 3500);
                    return;
                }
            }
            
            const t = document.createElement('div');
            t.dataset.msg = cleanMsg;
            const isErr = type === 'error' || msg.includes('❌') || msg.includes('خطا');
            const isOk = type === 'success' || msg.includes('✅') || msg.includes('موفق');
            const bg = isErr ? 'bg-rose-950/90 border-rose-800 text-rose-200' : (isOk ? 'bg-emerald-950/90 border-emerald-800 text-emerald-200' : 'bg-slate-800/90 border-slate-700 text-slate-200');
            const icon = isErr ? '<svg class="w-5 h-5 text-rose-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>' : 
                         (isOk ? '<svg class="w-5 h-5 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>' : 
                         '<svg class="w-5 h-5 text-sky-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>');
            t.className = `flex items-center gap-3 px-4 py-3 rounded-xl border backdrop-blur-md shadow-lg transform transition-all duration-300 translate-x-full opacity-0 ${bg}`;
            t.innerHTML = `${icon} <span class="text-sm font-bold font-sans" style="font-family: 'IRANSans', 'Vazirmatn', sans-serif;">${cleanMsg}</span>`;
            container.appendChild(t);
            requestAnimationFrame(() => {
                t.classList.remove('translate-x-full', 'opacity-0');
            });
            t.toastTimer = setTimeout(() => {
                t.classList.add('translate-x-full', 'opacity-0');
                setTimeout(() => t.remove(), 300);
            }, 3500);
        };

        let currentBaleOrderId = '';
        let currentBaleInvoiceUrl = '';
        let currentBaleDlLink = '';
        let balePollTimer = null;
        let selectedCourseId = '';
        let selectedCourseName = '';
        let selectedCoursePrice = 0;

        function copyText(txt) {
            if (!txt) return;
            navigator.clipboard.writeText(txt).then(() => {
                showToast('✅ با موفقیت کپی شد:\\n' + txt);
            }).catch(() => {
                prompt('لینک جهت کپی:', txt);
            });
        }

        function copyBaleInvoiceLink() {
            if (currentBaleInvoiceUrl) {
                copyText(currentBaleInvoiceUrl);
            } else {
                showToast('لینکی جهت پرداخت وجود ندارد.');
            }
        }

        function closeModal(id) {
            const el = document.getElementById(id);
            if (el) el.classList.add('hidden');
            if (id === 'baleBuyModal' && balePollTimer) {
                clearInterval(balePollTimer);
                balePollTimer = null;
            }
        }

        function openBaleBuyModal(target) {
            let pid = '', name = '', price = 0;
            if (target && (target instanceof HTMLElement || target.nodeType === 1)) {
                pid = target.getAttribute('data-id') || '';
                name = target.getAttribute('data-name') || '';
                price = parseInt(target.getAttribute('data-price') || '0', 10);
            } else {
                pid = arguments[0] || '';
                name = arguments[1] || '';
                price = parseInt(arguments[2] || '0', 10);
            }

            selectedCourseId = pid;
            selectedCourseName = name;
            selectedCoursePrice = price;

            const nameEl = document.getElementById('baleModalCourseName');
            const priceEl = document.getElementById('baleModalCoursePrice');
            if (nameEl) nameEl.innerText = name;
            if (priceEl) priceEl.innerText = price.toLocaleString() + ' تومان';

            const formEl = document.getElementById('baleBuyForm');
            const invEl = document.getElementById('baleInvoiceSection');
            const succEl = document.getElementById('baleSuccessSection');
            if (formEl) formEl.classList.remove('hidden');
            if (invEl) invEl.classList.add('hidden');
            if (succEl) succEl.classList.add('hidden');

            const inpName = document.getElementById('baleCustomerName');
            const inpPhone = document.getElementById('baleCustomerPhone');
            if (inpName) inpName.disabled = false;
            if (inpPhone) inpPhone.disabled = false;

            const btn = document.getElementById('btnBalePaySubmit');
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '<span>⚡️</span> دریافت لینک پرداخت بله';
            }

            const modal = document.getElementById('baleBuyModal');
            if (modal) modal.classList.remove('hidden');
        }

        function openZarinpalBuyModal(target) {
            let pid = '', name = '', price = 0;
            if (target && (target instanceof HTMLElement || target.nodeType === 1)) {
                pid = target.getAttribute('data-id') || '';
                name = target.getAttribute('data-name') || '';
                price = parseInt(target.getAttribute('data-price') || '0', 10);
            } else {
                pid = arguments[0] || '';
                name = arguments[1] || '';
                price = parseInt(arguments[2] || '0', 10);
            }

            const idEl = document.getElementById('zarinpalCourseId');
            const titleEl = document.getElementById('zarinpalModalCourseTitle');
            const priceEl = document.getElementById('zarinpalModalPrice');

            if (idEl) idEl.value = pid;
            if (titleEl) titleEl.innerText = name;
            if (priceEl) priceEl.innerText = price.toLocaleString() + ' تومان';

            const modal = document.getElementById('zarinpalBuyModal');
            if (modal) modal.classList.remove('hidden');
        }

        async function handleZarinpalPaymentSubmit(e) {
            e.preventDefault();
            const btn = document.getElementById('btnZarinpalPaySubmit');
            const courseId = document.getElementById('zarinpalCourseId').value;
            const name = document.getElementById('zarinpalCustomerName').value.trim();
            const phone = document.getElementById('zarinpalCustomerPhone').value.trim();
            const email = document.getElementById('zarinpalCustomerEmail').value.trim();

            btn.disabled = true;
            btn.innerHTML = '<span>⏳</span> در حال اتصال به درگاه زرین‌پال...';

            try {
                const res = await fetch('/api/payment/zarinpal/request', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json; charset=utf-8' },
                    body: JSON.stringify({
                        course_id: courseId,
                        customer_name: name,
                        phone: phone,
                        email: email
                    })
                });
                const data = await res.json();
                if (data.ok && data.payment_url) {
                    window.location.href = data.payment_url;
                } else {
                    showToast('❌ خطا در اتصال به درگاه: ' + (data.error || 'پاسخ نامعتبر از سرور'));
                    btn.disabled = false;
                    btn.innerHTML = '<span>⚡️</span> ورود به درگاه شاپرک و پرداخت';
                }
            } catch (err) {
                showToast('❌ خطای ارتباط با سرور: ' + err.message);
                btn.disabled = false;
                btn.innerHTML = '<span>⚡️</span> ورود به درگاه شاپرک و پرداخت';
            }
        }

        function openCardBuyModal(target) {
            let pid = '', name = '', price = 0;
            if (target && (target instanceof HTMLElement || target.nodeType === 1)) {
                pid = target.getAttribute('data-id') || '';
                name = target.getAttribute('data-name') || '';
                price = parseInt(target.getAttribute('data-price') || '0', 10);
            } else {
                pid = arguments[0] || '';
                name = arguments[1] || '';
                price = parseInt(arguments[2] || '0', 10);
            }

            selectedCourseId = pid;
            selectedCourseName = name;
            selectedCoursePrice = price;

            const priceEl = document.getElementById('cardModalCoursePrice');
            if (priceEl) priceEl.innerText = price.toLocaleString() + ' تومان';

            const formEl = document.getElementById('cardBuyForm');
            const succEl = document.getElementById('cardSuccessSection');
            if (formEl) formEl.classList.remove('hidden');
            if (succEl) succEl.classList.add('hidden');

            const modal = document.getElementById('cardBuyModal');
            if (modal) modal.classList.remove('hidden');
        }

        function openTrackModal() {
            const modal = document.getElementById('trackOrderModal');
            if (modal) modal.classList.remove('hidden');
        }

        function openFreeModal(target) {
            let dlLink = '';
            if (target && (target instanceof HTMLElement || target.nodeType === 1)) {
                dlLink = target.getAttribute('data-link') || '';
            } else {
                dlLink = arguments[2] || arguments[0] || '';
            }

            if (dlLink) {
                window.open(dlLink, '_blank');
            } else {
                showToast('فایل‌های این دوره رایگان در حال آماده‌سازی می‌باشد.');
            }
        }

        async function handleBalePaymentSubmit(e) {
            e.preventDefault();
            const btn = document.getElementById('btnBalePaySubmit');
            btn.disabled = true;
            btn.innerText = 'در حال ارتباط با درگاه بله...';

            const name = document.getElementById('baleCustomerName').value.trim();
            const phone = document.getElementById('baleCustomerPhone').value.trim();

            try {
                const res = await fetch('/api/store/buy_bale', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json; charset=utf-8' },
                    body: JSON.stringify({
                        course_id: selectedCourseId,
                        customer_name: name,
                        phone: phone
                    })
                });
                const data = await res.json();
                if (!data.ok) {
                    showToast('❌ خطا در ایجاد فاکتور پرداخت: ' + (data.error || ''));
                    btn.disabled = false;
                    btn.innerText = '⚡️ دریافت لینک پرداخت بله';
                    return;
                }

                currentBaleOrderId = data.order_id;
                currentBaleInvoiceUrl = data.invoice_url || '';

                if (data.is_free) {
                    showBaleSuccess(data.download_link);
                    return;
                }

                document.getElementById('baleBuyForm').classList.add('hidden');
                document.getElementById('baleOrderIdBadge').innerText = data.order_id;
                const linkBtn = document.getElementById('baleInvoiceLinkBtn');
                linkBtn.href = data.invoice_url;

                document.getElementById('baleInvoiceSection').classList.remove('hidden');
                try {
                    window.open(data.invoice_url, '_blank');
                } catch (e) {
                    console.warn('Popup blocked, use direct link or copy button');
                }

                // Start polling order status every 3 seconds
                if (balePollTimer) clearInterval(balePollTimer);
                balePollTimer = setInterval(async () => {
                    try {
                        const stRes = await fetch('/api/store/order_status?order_id=' + encodeURIComponent(data.order_id));
                        const stData = await stRes.json();
                        if (stData.ok && stData.orders && stData.orders.length > 0) {
                            const ord = stData.orders[0];
                            if (ord.status === 'completed' || ord.status === 'approved') {
                                clearInterval(balePollTimer);
                                balePollTimer = null;
                                showBaleSuccess(ord.download_link);
                            }
                        }
                    } catch (err) {
                        console.warn('Poll error:', err);
                    }
                }, 3000);

            } catch (err) {
                showToast('❌ خطای ارتباط با سرور: ' + err.message);
                btn.disabled = false;
                btn.innerText = '⚡️ دریافت لینک پرداخت بله';
            }
        }

        function showBaleSuccess(dlLink) {
            currentBaleDlLink = dlLink || '';
            document.getElementById('baleInvoiceSection').classList.add('hidden');
            document.getElementById('baleBuyForm').classList.add('hidden');

            const dlBtn = document.getElementById('baleDirectDlBtn');
            if (dlLink) {
                dlBtn.href = dlLink;
                dlBtn.style.display = 'flex';
            } else {
                dlBtn.style.display = 'none';
            }
            document.getElementById('baleSuccessSection').classList.remove('hidden');
        }

        function copyBaleDlLink() {
            if (currentBaleDlLink) {
                copyText(currentBaleDlLink);
            } else {
                showToast('لینکی جهت کپی موجود نیست.');
            }
        }

        async function handleCardPaymentSubmit(e) {
            e.preventDefault();
            const btn = document.getElementById('btnCardPaySubmit');
            btn.disabled = true;
            btn.innerText = 'در حال ثبت رسید...';

            const name = document.getElementById('cardCustomerName').value.trim();
            const phone = document.getElementById('cardCustomerPhone').value.trim();
            const receipt = document.getElementById('cardReceiptInfo').value.trim();
            const fileInp = document.getElementById('cardReceiptImage');
            const receiptFile = fileInp && fileInp.files ? fileInp.files[0] : null;

            let receiptImageData = '';
            if (receiptFile) {
                try {
                    receiptImageData = await new Promise((resolve, reject) => {
                        const reader = new FileReader();
                        reader.onload = () => resolve(reader.result);
                        reader.onerror = reject;
                        reader.readAsDataURL(receiptFile);
                    });
                } catch (readErr) {
                    console.warn('Failed reading receipt image:', readErr);
                }
            }

            try {
                const res = await fetch('/api/store/buy_card', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json; charset=utf-8' },
                    body: JSON.stringify({
                        course_id: selectedCourseId,
                        customer_name: name,
                        phone: phone,
                        receipt_info: receipt,
                        receipt_image: receiptImageData
                    })
                });
                const data = await res.json();
                if (!data.ok) {
                    showToast('❌ خطا: ' + (data.error || 'ثبت سفارش ناموفق بود.'));
                    btn.disabled = false;
                    btn.innerText = '📤 ثبت سفارش و ارسال رسید';
                    return;
                }

                document.getElementById('cardBuyForm').classList.add('hidden');
                document.getElementById('cardOrderIdBadge').innerText = data.order_id;
                document.getElementById('cardSuccessSection').classList.remove('hidden');

            } catch (err) {
                showToast('❌ خطای ارتباط: ' + err.message);
                btn.disabled = false;
                btn.innerText = '📤 ثبت سفارش و ارسال رسید';
            }
        }

        async function handleTrackSubmit(e) {
            e.preventDefault();
            const q = document.getElementById('trackInput').value.trim();
            if (!q) return;

            const box = document.getElementById('trackResultsContainer');
            box.innerHTML = '<p class="text-center text-xs text-cyan-400 py-6">در حال استعلام وضعیت سفارش...</p>';

            try {
                const res = await fetch('/api/store/order_status?order_id=' + encodeURIComponent(q));
                const data = await res.json();
                if (!data.ok || !data.orders || data.orders.length === 0) {
                    box.innerHTML = '<div class="p-4 rounded-2xl  border border-slate-800 text-center text-xs text-rose-300">هیچ سفارشی با این کد یا شماره همراه یافت نشد.</div>';
                    return;
                }

                box.innerHTML = data.orders.map(ord => {
                    let badge = '';
                    let dlHtml = '';
                    if (ord.status === 'completed' || ord.status === 'approved') {
                        badge = '<span class="px-2.5 py-1 rounded-lg text-xs font-bold bg-emerald-950 text-emerald-300 border border-emerald-800">✅ پرداخت تایید شده</span>';
                        if (ord.download_link) {
                            dlHtml = '<div class="pt-2 border-t border-slate-800 mt-2 flex items-center justify-between gap-2">' +
                                '<span class="text-[11px] text-slate-400 truncate max-w-[200px] font-mono">🔗 ' + ord.download_link + '</span>' +
                                '<div class="flex gap-1.5">' +
                                    '<a href="' + ord.download_link + '" target="_blank" class="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold transition">📥 دانلود</a>' +
                                    '<button data-dl="' + ord.download_link + '" onclick="copyText(this.dataset.dl)" class="px-2.5 py-1.5 rounded-lg bg-slate-800 text-cyan-300 text-xs border border-slate-700">کپی</button>' +
                                '</div>' +
                            '</div>';
                        } else {
                            dlHtml = '<div class="text-[11px] text-slate-400 pt-2 border-t border-slate-800 mt-2">لینک دانلود در دسترس نیست (با پشتیبانی تماس بگیرید).</div>';
                        }
                    } else if (ord.status === 'rejected') {
                        badge = '<span class="px-2.5 py-1 rounded-lg text-xs font-bold bg-rose-950 text-rose-300 border border-rose-800">❌ تایید نشده / رد شده</span>';
                    } else {
                        badge = '<span class="px-2.5 py-1 rounded-lg text-xs font-bold bg-amber-950 text-amber-300 border border-amber-800">⏳ در انتظار بررسی فیش</span>';
                        dlHtml = '<div class="text-[11px] text-amber-300/80 pt-2 border-t border-slate-800 mt-2">سفارش شما در صف بررسی توسط ادمین است. به محض تایید، لینک دانلود فعال خواهد شد.</div>';
                    }

                    const dateStr = ord.created_at ? ord.created_at.split('T')[0] : '-';

                    return '<div class="p-4 rounded-2xl  border border-slate-800 space-y-2 text-xs">' +
                        '<div class="flex justify-between items-start gap-2">' +
                            '<div>' +
                                '<span class="font-mono text-[10px] text-cyan-400 bg-cyan-950 px-2 py-0.5 rounded border border-cyan-800">' + ord.order_id + '</span>' +
                                '<h4 class="font-bold text-white text-sm mt-1">' + (ord.product_name || 'دوره آموزشی') + '</h4>' +
                            '</div>' +
                            badge +
                        '</div>' +
                        '<div class="flex justify-between text-[11px] text-slate-400 pt-1">' +
                            '<span>مبلغ: <span class="text-emerald-400 font-mono font-bold">' + (ord.amount || 0).toLocaleString() + ' تومان</span></span>' +
                            '<span class="font-mono">' + dateStr + '</span>' +
                        '</div>' +
                        dlHtml +
                    '</div>';
                }).join('');

            } catch (err) {
                box.innerHTML = '<div class="p-4 rounded-2xl bg-rose-950/40 border border-rose-800 text-center text-xs text-rose-300">خطا در دریافت وضعیت: ' + err.message + '</div>';
            }
        }

        // Check for payment callback status from URL
        (function checkPaymentStatus() {
            try {
                const urlParams = new URLSearchParams(window.location.search);
                const status = urlParams.get('payment');
                const orderId = urlParams.get('order_id');
                const dlLink = urlParams.get('dl');
                if (status === 'success') {
                    showToast('🎉 پرداخت شما با موفقیت انجام شد!\\nشناسه سفارش: ' + (orderId || '') + (dlLink ? '\\nلینک دانلود: ' + dlLink : ''));
                } else if (status === 'failed') {
                    showToast('❌ پرداخت زرین‌پال ناموفق بود یا لغو گردید.');
                }
            } catch(e) {}
        })();

        window.openBaleBuyModal = openBaleBuyModal;
        window.openCardBuyModal = openCardBuyModal;
        window.openZarinpalBuyModal = openZarinpalBuyModal;
        window.openTrackModal = openTrackModal;
        window.closeModal = closeModal;
    