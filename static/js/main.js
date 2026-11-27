/* FINORA - Core Application JavaScript */

document.addEventListener('DOMContentLoaded', () => {
    // 1. Initialize Lucide Icons
    if (window.lucide) {
        window.lucide.createIcons();
    }

    // 2. Initial Notification Badge Load
    loadNotifications();

    // 2.1 Register PWA Service Worker for Mobile App Installation
    if ('serviceWorker' in navigator) {
        window.addEventListener('load', () => {
            navigator.serviceWorker.register('/static/sw.js')
                .then(reg => console.log('FINORA PWA ServiceWorker registered:', reg.scope))
                .catch(err => console.log('FINORA ServiceWorker registration failed:', err));
        });
    }

    // 3. Sidebar Toggle (Responsive Mobile Drawer + Desktop Mini Collapse)
    const sidebarToggleBtn = document.getElementById('sidebarToggleBtn');
    const mobileMenuBtn = document.getElementById('mobileMenuBtn');
    const appSidebar = document.getElementById('appSidebar');
    const mainWrapper = document.getElementById('mainWrapper');
    const sidebarBackdrop = document.getElementById('sidebarBackdrop');

    function toggleMobileSidebar() {
        if (!appSidebar) return;
        appSidebar.classList.toggle('mobile-open');
        if (sidebarBackdrop) {
            sidebarBackdrop.classList.toggle('show');
        }
    }

    function closeMobileSidebar() {
        if (!appSidebar) return;
        appSidebar.classList.remove('mobile-open');
        if (sidebarBackdrop) {
            sidebarBackdrop.classList.remove('show');
        }
    }

    if (sidebarToggleBtn && appSidebar) {
        sidebarToggleBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            if (window.innerWidth <= 992) {
                toggleMobileSidebar();
            } else {
                appSidebar.classList.toggle('collapsed');
                if (mainWrapper) {
                    mainWrapper.classList.toggle('sidebar-collapsed');
                }
            }
        });
    }

    if (mobileMenuBtn) {
        mobileMenuBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            toggleMobileSidebar();
        });
    }

    if (sidebarBackdrop) {
        sidebarBackdrop.addEventListener('click', closeMobileSidebar);
    }

    // 4. User Profile Dropdown
    const profileBtn = document.getElementById('profileBtn');
    const profileMenu = document.getElementById('profileMenu');

    if (profileBtn && profileMenu) {
        profileBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            profileMenu.classList.toggle('show');
            const notifDropdown = document.getElementById('notifDropdown');
            if (notifDropdown) notifDropdown.classList.remove('show');
        });
    }

    // 5. Notification Dropdown Toggle
    const notifBtn = document.getElementById('notifBtn');
    const notifDropdown = document.getElementById('notifDropdown');

    if (notifBtn && notifDropdown) {
        notifBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            notifDropdown.classList.toggle('show');
            if (profileMenu) profileMenu.classList.remove('show');
            loadNotifications();
        });
    }

    // Close dropdowns on outside click
    document.addEventListener('click', () => {
        if (profileMenu) profileMenu.classList.remove('show');
        if (notifDropdown) notifDropdown.classList.remove('show');
    });

    if (profileMenu) {
        profileMenu.addEventListener('click', (e) => e.stopPropagation());
    }
    if (notifDropdown) {
        notifDropdown.addEventListener('click', (e) => e.stopPropagation());
    }

    // 6. Global Modal Helpers
    window.openModal = function(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.add('show');
            document.body.style.overflow = 'hidden';
            if (window.lucide) window.lucide.createIcons();
        }
    };

    window.closeModal = function(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.remove('show');
            document.body.style.overflow = '';
        }
    };

    // Close modals on backdrop click via event delegation
    document.addEventListener('click', (e) => {
        if (e.target.classList && e.target.classList.contains('modal-backdrop-custom')) {
            e.target.classList.remove('show');
            document.body.style.overflow = '';
        }
    });

    // 7. Global Quick Search (Enter triggers filter)
    const topbarSearch = document.getElementById('topbarSearchInput');
    if (topbarSearch) {
        topbarSearch.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                const val = encodeURIComponent(topbarSearch.value.trim());
                if (val) {
                    window.location.href = `/transactions?search=${val}`;
                }
            }
        });
    }
});

// Notifications AJAX Fetcher
function loadNotifications() {
    const list = document.getElementById('notifList');
    const badge = document.getElementById('notifBadge');
    if (!list) return;

    fetch('/api/notifications')
        .then(res => res.json())
        .then(data => {
            if (badge) {
                if (data.unread_count > 0) {
                    badge.style.display = 'flex';
                    badge.innerText = data.unread_count;
                } else {
                    badge.style.display = 'none';
                }
            }

            if (!data.notifications || data.notifications.length === 0) {
                list.innerHTML = `
                    <div style="text-align: center; padding: 24px 16px; font-size: 0.8rem; color: #8799A8;">
                        <i data-lucide="check-check" style="width: 28px; height: 28px; color: var(--income); margin-bottom: 6px;"></i>
                        <div>No new alerts. You're all caught up!</div>
                    </div>
                `;
                if (window.lucide) window.lucide.createIcons();
                return;
            }

            const typeColors = {
                'danger': '#D59A9A',
                'warning': '#D6B77A',
                'success': '#8EAD98',
                'info': '#789BB8'
            };

            list.innerHTML = data.notifications.map(n => {
                const accentColor = typeColors[n.type] || '#789BB8';
                return `
                    <div class="notif-item ${n.is_read ? 'read' : ''}" style="border-left: 3px solid ${accentColor}; position: relative;">
                        <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                            <div class="notif-title" style="cursor: pointer;" onclick="markNotificationRead(${n.id})">${n.title}</div>
                            <button onclick="dismissNotification(event, ${n.id})" style="background: none; border: none; cursor: pointer; color: #8799A8; padding: 0 4px;" title="Dismiss alert">
                                &times;
                            </button>
                        </div>
                        <div class="notif-desc" style="cursor: pointer;" onclick="markNotificationRead(${n.id})">${n.message}</div>
                        <div style="font-size: 0.68rem; color: #8799A8; margin-top: 4px;">${n.created_at}</div>
                    </div>
                `;
            }).join('');

            if (window.lucide) window.lucide.createIcons();
        })
        .catch(err => console.error('Failed to load notifications', err));
}

function markNotificationRead(id) {
    fetch(`/api/notifications/mark-read/${id}`, { method: 'POST' })
        .then(() => loadNotifications());
}

function dismissNotification(e, id) {
    if (e) e.stopPropagation();
    fetch(`/api/notifications/delete/${id}`, { method: 'POST' })
        .then(() => loadNotifications());
}

function markAllNotificationsRead() {
    fetch('/api/notifications/mark-all-read', { method: 'POST' })
        .then(() => loadNotifications());
}

/* ==========================================================================
   FINORA INSTANT APP ROUTER
   Seamless Native-App Navigation: zero browser reloads, zero topbar flashes,
   instant page swaps with GPU transitions.
   ========================================================================== */
(function() {
    let isNavigating = false;
    const pageCache = new Map();

    async function loadPage(url, push = true) {
        if (isNavigating) return;
        isNavigating = true;

        const mainContent = document.querySelector('main.page-content');
        if (mainContent) {
            mainContent.style.opacity = '0.6';
            mainContent.style.transition = 'opacity 0.12s ease';
        }

        try {
            let html = pageCache.get(url);
            if (!html) {
                const response = await fetch(url, {
                    headers: { 'X-Requested-With': 'FinoraNativeApp' }
                });

                if (response.redirected && response.url.includes('/login')) {
                    window.location.href = response.url;
                    return;
                }

                html = await response.text();
                if (pageCache.size > 20) {
                    pageCache.delete(pageCache.keys().next().value);
                }
                pageCache.set(url, html);
            }

            const parser = new DOMParser();
            const newDoc = parser.parseFromString(html, 'text/html');

            // 1. Swap main content
            const newContent = newDoc.querySelector('main.page-content');
            if (newContent && mainContent) {
                mainContent.innerHTML = newContent.innerHTML;
                mainContent.style.opacity = '1';
            }

            // 2. Update page title
            if (newDoc.title) {
                document.title = newDoc.title;
            }

            // 3. Update topbar header title
            const currentTitle = document.querySelector('.page-header-title');
            const newTitle = newDoc.querySelector('.page-header-title');
            if (currentTitle && newTitle) {
                currentTitle.innerHTML = newTitle.innerHTML;
            }

            // 4. Update sidebar and mobile bottom navigation active classes
            const currentPath = new URL(url, window.location.origin).pathname;
            document.querySelectorAll('.sidebar-nav .nav-item').forEach(item => {
                const link = item.querySelector('a');
                if (link) {
                    const linkPath = new URL(link.href, window.location.origin).pathname;
                    if (linkPath === currentPath) {
                        item.classList.add('active');
                    } else {
                        item.classList.remove('active');
                    }
                }
            });

            document.querySelectorAll('.mobile-bottom-item').forEach(item => {
                if (item.tagName === 'A') {
                    const linkPath = new URL(item.href, window.location.origin).pathname;
                    if (linkPath === currentPath) {
                        item.classList.add('active');
                    } else {
                        item.classList.remove('active');
                    }
                }
            });

            // 5. Push history state
            if (push) {
                window.history.pushState({ url }, '', url);
            }

            // 6. Scroll smoothly to top
            window.scrollTo({ top: 0, behavior: 'instant' });

            // 7. Refresh Lucide Icons
            if (window.lucide) {
                window.lucide.createIcons();
            }

            // 8. Re-execute inline scripts within the new content (e.g. data arrays for charts)
            if (newContent) {
                const scripts = newContent.querySelectorAll('script');
                scripts.forEach(oldScript => {
                    const newScript = document.createElement('script');
                    Array.from(oldScript.attributes).forEach(attr => newScript.setAttribute(attr.name, attr.value));
                    newScript.appendChild(document.createTextNode(oldScript.innerHTML));
                    document.body.appendChild(newScript);
                    newScript.remove();
                });
            }

            // 9. Re-initialize Charts & Visualizations
            if (window.initAllCharts) {
                window.initAllCharts();
            }

            // 10. Close mobile sidebar if open
            const appSidebar = document.getElementById('appSidebar');
            const sidebarBackdrop = document.getElementById('sidebarBackdrop');
            if (appSidebar) appSidebar.classList.remove('mobile-open');
            if (sidebarBackdrop) sidebarBackdrop.classList.remove('show');

        } catch (err) {
            console.warn('Fast navigation fallback to standard browser:', err);
            window.location.href = url;
        } finally {
            if (mainContent) mainContent.style.opacity = '1';
            isNavigating = false;
        }
    }

    // Intercept clicks on links for seamless instant page swap
    document.addEventListener('click', (e) => {
        const link = e.target.closest('a');
        if (!link) return;

        const href = link.getAttribute('href');
        if (!href || href.startsWith('#') || href.startsWith('javascript:')) return;
        if (link.target === '_blank' || link.hasAttribute('download')) return;

        // Skip auth, exports, logout, file downloads
        if (href.includes('/logout') || href.includes('/reports/export') || href.includes('/api/')) return;

        const targetUrl = new URL(link.href, window.location.origin);
        if (targetUrl.origin !== window.location.origin) return;

        // Intercept and load with zero reload!
        e.preventDefault();
        loadPage(link.href, true);
    });

    // Handle Android Hardware Back button
    window.addEventListener('popstate', (e) => {
        loadPage(window.location.href, false);
    });
})();
