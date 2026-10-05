                            container.insertBefore(draggedBtn, next ? target.nextSibling : target);
                        }
                    });

                    function saveProductSubtabsOrder() {
                        const buttons = Array.from(container.querySelectorAll('.prod-subtab-btn'));
                        const order = buttons.map(b => b.getAttribute('data-subtab')).filter(Boolean);
                        localStorage.setItem('unfinit_products_subtabs_order', JSON.stringify(order));
                    }
                }
                window.initProductSubtabsDragAndDrop = initProductSubtabsDragAndDrop;

                function inlineRenameTab(element, tabId) {
                    const currentText = element.textContent.trim();
                    const input = document.createElement('input');
                    input.type = 'text';
                    input.value = currentText;
                    input.className = 'w-full  text-white text-xs px-2 py-1 rounded border border-cyan-500 focus:outline-none';
                    
                    const saveRename = async () => {
                        const newTitle = input.value.trim();
                        if (newTitle && newTitle !== currentText) {
                            element.textContent = newTitle;
                            try {
                                const renames = JSON.parse(localStorage.getItem('unfinit_tab_renames') || '{}');
                                renames[tabId] = newTitle;
                                localStorage.setItem('unfinit_tab_renames', JSON.stringify(renames));
                            } catch (e) {}
                            try {
                                const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                                await fetch('/api/settings/rename', {
                                    method: 'POST',
                                    headers: { 'Content-Type': 'application/json; charset=utf-8', 'Authorization': 'Bearer ' + pwd, 'X-Admin-Password': pwd },
                                    body: JSON.stringify({ tab_id: tabId, title: newTitle, admin_password: pwd })
                                });
                            } catch (e) {
                                console.warn('Failed to save tab rename:', e);
                            }
                        } else {
                            element.textContent = currentText;
                        }
                    };

                    input.onblur = saveRename;
                    input.onkeydown = (e) => {
                        if (e.key === 'Enter') {
                            input.blur();
                        } else if (e.key === 'Escape') {
                            element.textContent = currentText;
                        }
                    };

                    element.textContent = '';
                    element.appendChild(input);
                    input.focus();
                    input.select();
                }
                window.inlineRenameTab = inlineRenameTab;

                function restoreTabRenames() {
                    try {
                        const renames = JSON.parse(localStorage.getItem('unfinit_tab_renames') || '{}');
                        for (const [tabId, title] of Object.entries(renames)) {
                            const btn = document.querySelector(`.sidebar-nav-btn[data-tab="${tabId}"] span.text-right`) ||
                                        document.querySelector(`.sidebar-nav-btn[data-tab="${tabId}"] span`);
                            if (btn && title) {
                                btn.textContent = title;
                            }
                        }
                    } catch (e) {}
                }
                window.restoreTabRenames = restoreTabRenames;

                async function deleteUserRow(userId) {
                    if (!userId || userId === '-' || userId === 'undefined') return;
                    if (!confirm(`Ø¢ÛŒØ§ Ø§Ø² Ø­Ø°Ù Ú©Ø§Ù…Ù„ Ú©Ø§Ø±Ø¨Ø± Ø¨Ø§ Ø´Ù†Ø§Ø³Ù‡ ${userId} Ø§Ø² Ù¾Ø§ÛŒÚ¯Ø§Ù‡ Ø¯Ø§Ø¯Ù‡ Ø§Ø·Ù…ÛŒÙ†Ø§Ù† Ø¯Ø§Ø±ÛŒØ¯ØŸ`)) return;
                    try {
                        const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                        const res = await fetch('/api/users/delete', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json; charset=utf-8', 'Authorization': 'Bearer ' + pwd, 'X-Admin-Password': pwd },
                            body: JSON.stringify({ user_id: userId, admin_password: pwd })
                        });
                        const data = await res.json();
                        if (data.ok) {
                            allLoadedUsers = allLoadedUsers.filter(u => String(u.user_id) !== String(userId));
                            renderUsersTable(allLoadedUsers);
                            const statTotal = document.getElementById('statTotalUsers');
                            if (statTotal) statTotal.innerText = allLoadedUsers.length;
                        } else {
                            showToast('Ø®Ø·Ø§ Ø¯Ø± Ø­Ø°Ù Ú©Ø§Ø±Ø¨Ø±: ' + (data.error || 'Ù†Ø§Ù…Ø´Ø®Øµ'));
                        }
                    } catch (e) {
                        showToast('Ø®Ø·Ø§ÛŒ Ø§Ø±ØªØ¨Ø§Ø·: ' + e.message);
                    }
                }
                window.deleteUserRow = deleteUserRow;

                async function purgeTestUsers() {
                    if (!confirm('Ù‡Ø´Ø¯Ø§Ø±: Ø¢ÛŒØ§ Ù…Ø·Ù…Ø¦Ù† Ù‡Ø³ØªÛŒØ¯ Ú©Ù‡ Ù…ÛŒâ€ŒØ®ÙˆØ§Ù‡ÛŒØ¯ ØªÙ…Ø§Ù… Ú©Ø§Ø±Ø¨Ø±Ø§Ù† Ø¢Ø²Ù…Ø§ÛŒØ´ÛŒ Ùˆ Ø³Ø§Ø®ØªÚ¯ÛŒ Ø±Ø§ Ù¾Ø§Ú©Ø³Ø§Ø²ÛŒ Ú©Ù†ÛŒØ¯ØŸ')) return;
                    try {
                        const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                        const res = await fetch('/api/users/purge_test', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json; charset=utf-8', 'Authorization': 'Bearer ' + pwd, 'X-Admin-Password': pwd },
                            body: JSON.stringify({ admin_password: pwd })
                        });
                        const data = await res.json();
                        if (data.ok) {
                            showToast(`Ù¾Ø§Ú©Ø³Ø§Ø²ÛŒ Ø§Ù†Ø¬Ø§Ù… Ø´Ø¯. ${data.deleted_count || 0} Ú©Ø§Ø±Ø¨Ø± Ø¢Ø²Ù…Ø§ÛŒØ´ÛŒ Ø­Ø°Ù Ø´Ø¯Ù†Ø¯.`);
                            loadUsersData();
                        } else {
                            showToast('Ø®Ø·Ø§ Ø¯Ø± Ù¾Ø§Ú©Ø³Ø§Ø²ÛŒ: ' + (data.error || 'Ù†Ø§Ù…Ø´Ø®Øµ'));
                        }
                    } catch (e) {
                        showToast('Ø®Ø·Ø§ÛŒ Ø§Ø±ØªØ¨Ø§Ø·: ' + e.message);
                    }
                }
                window.purgeTestUsers = purgeTestUsers;

                function filterUsersTable() {
                    const q = (document.getElementById('usersSearchInput')?.value || '').toLowerCase().trim();
                    if (!q) {
                        renderUsersTable(allLoadedUsers);
                        return;
                    }
                    const filtered = allLoadedUsers.filter(u => {
                        const id = String(u.user_id || '').toLowerCase();
                        const name = String(u.username || u.name || '').toLowerCase();
                        const phone = String(u.phone || '').toLowerCase();
                        const ref = String(u.referred_by || '').toLowerCase();
                        return id.includes(q) || name.includes(q) || phone.includes(q) || ref.includes(q);
                    });
                    renderUsersTable(filtered);
                }
                window.filterUsersTable = filterUsersTable;

                function exportUsersCsv() {
                    if (!allLoadedUsers || allLoadedUsers.length === 0) {
                        showToast('Ú©Ø§Ø±Ø¨Ø±ÛŒ Ø¨Ø±Ø§ÛŒ Ø®Ø±ÙˆØ¬ÛŒ Ù…ÙˆØ¬ÙˆØ¯ Ù†ÛŒØ³Øª.');
                        return;
                    }
                    const header = ['Ù¾Ù„ØªÙØ±Ù…', 'Ø´Ù†Ø§Ø³Ù‡', 'Ù†Ø§Ù…', 'Ø´Ù…Ø§Ø±Ù‡ ØªÙ…Ø§Ø³', 'Ù…Ø¹Ø±Ù', 'Ú©ÛŒÙ Ù¾ÙˆÙ„', 'ØªØ¹Ù‡Ø¯Ù†Ø§Ù…Ù‡'];
                    const rows = allLoadedUsers.map(u => [
                        u.platform || '',
                        u.user_id || '',
                        u.username || u.name || '',
                        u.phone || '',
                        u.referred_by || '',
                        u.wallet_balance || 0,
                        u.commitment_signed ? 'Ø§Ù…Ø¶Ø§ Ø´Ø¯Ù‡' : 'Ø®ÛŒØ±'
                    ]);
                    const csvContent = "\uFEFF" + [header.join(','), ...rows.map(r => r.map(c => `"${String(c).replace(/"/g, '""')}"`).join(','))].join('\n');
                    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
                    const url = URL.createObjectURL(blob);
                    const link = document.createElement('a');
                    link.href = url;
                    link.download = `unfinit_users_${new Date().toISOString().slice(0,10)}.csv`;
                    link.click();
                    URL.revokeObjectURL(url);
                }
                window.exportUsersCsv = exportUsersCsv;

                function checkAuthOnLoad() {
                    const token = localStorage.getItem('unfinit_auth_token') || sessionStorage.getItem('unfinit_auth_token');
                    const pwd = localStorage.getItem('unfinit_admin_pwd') || sessionStorage.getItem('unfinit_admin_pwd');
                    const gate = document.getElementById('loginGate');
                    const app = document.getElementById('appMain');
                    if (token === 'authenticated' && pwd) {
                        window.currentAdminPassword = pwd;
                        if (gate) {
                            gate.style.display = 'none';
                            gate.classList.add('hidden');
                        }
                        if (app) {
                            app.style.removeProperty('display');
                            app.style.display = 'block';
                            app.classList.remove('hidden');
                        }
                        try {
                            const savedTab = localStorage.getItem('unfinit_active_tab') || 'dashboard';
                            window.switchTab(savedTab);
                        } catch (e) {
                            console.warn('[Navigation] Tab switch notice:', e);
                        }
                    } else {
                        if (gate) {
                            gate.style.removeProperty('display');
                            gate.classList.remove('hidden');
                        }
                        if (app) {
                            app.classList.add('hidden');
                            app.style.display = 'none';
                        }
                    }
                }

                function bindNavDelegation() {
                    const sidebarNav = document.getElementById('sidebarNavList');
                    if (sidebarNav) {
                        sidebarNav.addEventListener('click', function(e) {
                            const btn = e.target.closest('[data-tab]');
                            if (btn) {
                                const tab = btn.getAttribute('data-tab');
                                if (tab && window.switchTab) window.switchTab(tab);
                            }
                        });
                    }
                    const desktopNav = document.getElementById('desktopNavTabs');
                    if (desktopNav) {
                        desktopNav.addEventListener('click', function(e) {
                            const btn = e.target.closest('[data-tab]');
                            if (btn) {
                                const tab = btn.getAttribute('data-tab');
                                if (tab && window.switchTab) window.switchTab(tab);
                            }
                        });
                    }
                    const mobileNav = document.getElementById('mobileNavMenu');
                    if (mobileNav) {
                        mobileNav.addEventListener('click', function(e) {
                            const btn = e.target.closest('[data-tab]');
                            if (btn) {
                                const tab = btn.getAttribute('data-tab');
                                if (tab && window.switchTab) {
                                    window.switchTab(tab);
                                    if (typeof window.toggleMobileMenu === 'function') {
                                        window.toggleMobileMenu(false);
                                    }
                                }
                            }
                        });
                    }
                }

                function persistTabsOrder() {
                    const sidebarNav = document.getElementById('sidebarNavList');
                    const desktopNav = document.getElementById('desktopNavTabs');
                    let currentOrder = [];
                    if (sidebarNav) {
                        currentOrder = Array.from(sidebarNav.querySelectorAll('[data-tab]')).map(b => b.getAttribute('data-tab')).filter(Boolean);
                    }
                    if (currentOrder.length === 0 && desktopNav) {
                        currentOrder = Array.from(desktopNav.querySelectorAll('[data-tab]')).map(b => b.getAttribute('data-tab')).filter(Boolean);
                    }
                    if (currentOrder.length === 0) return;
                    // ØªØ¶Ù…ÛŒÙ† Ù‚Ø·Ø¹ÛŒ Ù‚Ø±Ø§Ø± Ú¯Ø±ÙØªÙ† ØªØ¨ Ø¯Ø§Ø´Ø¨ÙˆØ±Ø¯ Ø¯Ø± Ù†Ø®Ø³ØªÛŒÙ† Ø¬Ø§ÛŒÚ¯Ø§Ù‡ Ø³Ø§ÛŒØ¯Ø¨Ø§Ø± (index: 0)
                    currentOrder = ['dashboard', ...currentOrder.filter(t => t !== 'dashboard')];
                    localStorage.setItem('unfinit_nav_order', JSON.stringify(currentOrder));
                    localStorage.setItem('unfinit_tabs_order', JSON.stringify(currentOrder));
                    try {
                        const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                        if (pwd) {
                            fetch('/api/settings/save', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json; charset=utf-8' },
                                body: JSON.stringify({
                                    password: pwd,
                                    settings: { NAV_TABS_ORDER: currentOrder }
                                })
                            }).catch(e => console.warn('[DragDrop] Cloud save failed:', e));
                        }
                    } catch (e) {}
                }

                function initTabsDragAndDrop() {
                    const sidebarNav = document.getElementById('sidebarNavList');
                    const desktopNav = document.getElementById('desktopNavTabs');

                    try {
                        let savedOrder = JSON.parse(localStorage.getItem('unfinit_nav_order') || localStorage.getItem('unfinit_tabs_order') || '[]');
                        if (Array.isArray(savedOrder) && savedOrder.length > 0) {
                            // ØªØ«Ø¨ÛŒØª Ø±ØªØ¨Ù‡ Ø§ÙˆÙ„ Ø¨Ø±Ø§ÛŒ Ø¯Ø§Ø´Ø¨ÙˆØ±Ø¯ Ø¯Ø± Ù‡Ù†Ú¯Ø§Ù… Ø¨Ø§Ø±Ú¯Ø°Ø§Ø±ÛŒ
                            savedOrder = ['dashboard', ...savedOrder.filter(t => t !== 'dashboard')];
                            if (sidebarNav) {
                                savedOrder.forEach(tabId => {
                                    const btn = sidebarNav.querySelector(`[data-tab="${tabId}"]`);
                                    if (btn) sidebarNav.appendChild(btn);
                                });
                            }
                            if (desktopNav) {
                                savedOrder.forEach(tabId => {
                                    const btn = desktopNav.querySelector(`[data-tab="${tabId}"]`);
                                    if (btn) desktopNav.appendChild(btn);
                                });
                            }
                        }
                    } catch (e) {
                        console.warn('[DragDrop] Error loading saved tab order:', e);
                    }

                    function setupDragForContainer(container, isVertical) {
                        if (!container) return;
                        let draggedItem = null;

                        // Set draggable="true" on all tab items while preserving cursor: pointer
                        container.querySelectorAll('[data-tab]').forEach(b => {
                            b.setAttribute('draggable', 'true');
                            b.style.cursor = 'pointer';
                        });

                        // Mouse Drag & Drop (Native HTML5: Clicks fire instantly, dragging initiates reorder)
                        container.addEventListener('dragstart', function(e) {
                            const btn = e.target.closest('[data-tab]');
                            if (!btn) return;
                            draggedItem = btn;
                            e.dataTransfer.effectAllowed = 'move';
                            e.dataTransfer.setData('text/plain', btn.getAttribute('data-tab'));
                            btn.classList.add('opacity-40');
                        });

                        container.addEventListener('dragend', function(e) {
                            const btn = e.target.closest('[data-tab]');
                            if (btn) {
                                btn.classList.remove('opacity-40');
                            }
                            container.querySelectorAll('[data-tab]').forEach(b => {
                                b.classList.remove('opacity-40');
                                b.setAttribute('draggable', 'true');
                                b.style.cursor = 'pointer';
                            });
                            draggedItem = null;
                            persistTabsOrder();
                        });

                        container.addEventListener('dragover', function(e) {
                            e.preventDefault();
                            e.dataTransfer.dropEffect = 'move';
                            const targetBtn = e.target.closest('[data-tab]');
                            if (targetBtn && targetBtn !== draggedItem && targetBtn.parentElement === container) {
                                const rect = targetBtn.getBoundingClientRect();
                                const midpoint = isVertical ? (rect.y + rect.height / 2) : (rect.x + rect.width / 2);
                                const coord = isVertical ? e.clientY : e.clientX;
                                if (coord < midpoint) {
                                    container.insertBefore(draggedItem, targetBtn);
                                } else {
                                    container.insertBefore(draggedItem, targetBtn.nextSibling);
                                }
                            }
                        });

                        container.addEventListener('drop', function(e) {
                            e.preventDefault();
                            persistTabsOrder();
                        });

                        // Mobile Touch with 500ms long-press
                        let touchTimer = null;
                        let touchDraggedItem = null;

                        container.addEventListener('touchstart', function(e) {
                            const btn = e.target.closest('[data-tab]');
                            if (!btn) return;
                            touchTimer = setTimeout(function() {
                                touchDraggedItem = btn;
                                btn.classList.add('opacity-40', 'scale-95');
                                if (navigator.vibrate) navigator.vibrate(50);
                            }, 500);
                        }, { passive: true });

                        container.addEventListener('touchmove', function(e) {
                            if (!touchDraggedItem) {
                                if (touchTimer) { clearTimeout(touchTimer); touchTimer = null; }
                                return;
                            }
                            e.preventDefault();
                            const touch = e.touches[0];
                            const targetEl = document.elementFromPoint(touch.clientX, touch.clientY);
                            if (!targetEl) return;
                            const targetBtn = targetEl.closest('[data-tab]');
                            if (targetBtn && targetBtn !== touchDraggedItem && targetBtn.parentElement === container) {
                                const rect = targetBtn.getBoundingClientRect();
                                const midpoint = isVertical ? (rect.y + rect.height / 2) : (rect.x + rect.width / 2);
                                const coord = isVertical ? touch.clientY : touch.clientX;
                                if (coord < midpoint) {
                                    container.insertBefore(touchDraggedItem, targetBtn);
                                } else {
                                    container.insertBefore(touchDraggedItem, targetBtn.nextSibling);
                                }
                            }
                        }, { passive: false });

                        function endTouchDrag() {
                            if (touchTimer) { clearTimeout(touchTimer); touchTimer = null; }
                            if (touchDraggedItem) {
                                touchDraggedItem.classList.remove('opacity-40', 'scale-95');
                                container.querySelectorAll('[data-tab]').forEach(b => b.classList.remove('opacity-40', 'scale-95'));
                                touchDraggedItem = null;
                                persistTabsOrder();
                            }
                        }
                        container.addEventListener('touchend', endTouchDrag);
                        container.addEventListener('touchcancel', endTouchDrag);
                    }

                    setupDragForContainer(sidebarNav, true);
                    setupDragForContainer(desktopNav, false);
                }

                function initUptimeTicker() {
                    const el = document.getElementById('uptimeDisplay');
                    if (!el) return;
                    const startSec = parseInt(el.getAttribute('data-start')) || 0;
                    if (!startSec) return;
                    function updateUptime() {
                        const now = Math.floor(Date.now() / 1000);
                        let diff = Math.max(0, now - startSec);
                        const h = Math.floor(diff / 3600);
                        const m = Math.floor((diff % 3600) / 60);
                        const s = diff % 60;
                        el.textContent = `${h}h ${m}m ${s}s`;
                    }
                    setInterval(updateUptime, 1000);
                }

                if (document.readyState === 'loading') {
                    document.addEventListener('DOMContentLoaded', function() {
                        bindNavDelegation();
                        initTabsDragAndDrop();
                        initSidebarState();
                        initUptimeTicker();
                        checkAuthOnLoad();
                        restoreTabRenames();
                    });
                } else {
                    bindNavDelegation();
                    initTabsDragAndDrop();
                    initSidebarState();
                    initUptimeTicker();
                    checkAuthOnLoad();
                    restoreTabRenames();
                }
            } catch (err) {
                console.error('[UNFINIT Navigation Module Error]:', err);
            }
        })();

        // =========================================================================
        // MODULE 2: STUDIO & MEDIA HUB (Sandboxed IIFE)
        // =========================================================================
        (function initStudioModule() {
            try {
        // WEB MP3TAG STUDIO CLIENT LOGIC
        // =========================================================================

        const studioDropzone = document.getElementById('studioDropzone');
        if (studioDropzone) {
            ['dragenter', 'dragover'].forEach(name => {
                studioDropzone.addEventListener(name, (e) => {
                    e.preventDefault();
                    e.stopPropagation();
