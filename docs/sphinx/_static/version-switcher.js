/**
 * Version Switcher for Praval Documentation
 *
 * Fetches available versions from versions.json and provides
 * a dropdown to switch between documentation versions.
 */

(function() {
    'use strict';

    // Configuration
    const VERSIONS_URL = '/docs/versions.json';
    const VERSION_SWITCHER_ID = 'praval-version-switcher';

    /**
     * Create version switcher dropdown
     */
    function createVersionSwitcher(versions, currentVersion) {
        const container = document.createElement('div');
        container.id = VERSION_SWITCHER_ID;
        container.className = 'version-switcher';

        const label = document.createElement('span');
        label.className = 'version-switcher-label';
        label.textContent = 'Version: ';

        const select = document.createElement('select');
        select.className = 'version-switcher-select';

        versions.forEach(version => {
            const option = document.createElement('option');
            option.value = version.url;
            option.textContent = version.title;
            if (version.version === currentVersion) {
                option.selected = true;
            }
            select.appendChild(option);
        });

        select.addEventListener('change', function() {
            window.location.href = this.value;
        });

        container.appendChild(label);
        container.appendChild(select);

        return container;
    }

    /**
     * Insert version switcher into the page
     */
    function insertVersionSwitcher(switcher) {
        // Try to insert in the sidebar search area
        const searchArea = document.querySelector('.wy-side-nav-search');
        if (searchArea) {
            searchArea.appendChild(switcher);
            return;
        }

        // Fallback: insert at the top of the page
        const body = document.body;
        if (body && body.firstChild) {
            body.insertBefore(switcher, body.firstChild);
        }
    }

    /**
     * Get current version from page
     */
    function getCurrentVersion() {
        // Try to extract from URL path
        const pathMatch = window.location.pathname.match(/\/docs\/v([\d.]+)\//);
        if (pathMatch) {
            return pathMatch[1];
        }

        // Check if on latest
        if (window.location.pathname.includes('/docs/latest/')) {
            return 'latest';
        }

        // Default to current version from page variable
        if (typeof DOCUMENTATION_OPTIONS !== 'undefined' && DOCUMENTATION_OPTIONS.VERSION) {
            return DOCUMENTATION_OPTIONS.VERSION;
        }

        return null;
    }

    /**
     * Load versions and create switcher
     */
    function initVersionSwitcher() {
        const currentVersion = getCurrentVersion();

        fetch(VERSIONS_URL)
            .then(response => {
                if (!response.ok) {
                    throw new Error('Failed to load versions.json');
                }
                return response.json();
            })
            .then(data => {
                if (data.versions && data.versions.length > 0) {
                    const switcher = createVersionSwitcher(data.versions, currentVersion || data.current);
                    insertVersionSwitcher(switcher);
                }
            })
            .catch(error => {
                console.warn('Version switcher initialization failed:', error);
                // Silently fail - version switcher is optional
            });
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initVersionSwitcher);
    } else {
        initVersionSwitcher();
    }
})();
