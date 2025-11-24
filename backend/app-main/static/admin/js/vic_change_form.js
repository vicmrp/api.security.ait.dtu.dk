// vic_change_form.js

class VicChangeFormApp {
    constructor(uiBinder = VicChangeFormUIBinder.getInstance(), baseUIBinder = BaseUIBinder.getInstance(), baseAppUtils = BaseAppUtils.getInstance()) {
        if (!VicChangeFormApp.instance) {
            this.uiBinder = uiBinder;
            this.baseUIBinder = baseUIBinder;
            this.baseAppUtils = baseAppUtils;

            this.pathsConfig = {
                changeFormEndpoint: {
                    pathPattern: "/admin/myview/endpoint/:id/change/",
                    setup: this.setupChangeFormEndpointMonitor.bind(this)
                },
                organizationalUnitLimiter: {
                    path: "/admin/myview/adorganizationalunitlimiter/",
                    setup: this.setupOrganizationalUnitLimiterMonitor.bind(this)
                }
            };

            this.monitorPaths();

            VicChangeFormApp.instance = this;
        }

        return VicChangeFormApp.instance;
    }

    monitorPaths() {
        const currentPath = window.location.pathname;
        const pathConfig = Object.values(this.pathsConfig).find(config => {
            if (config.path) {
                return config.path === currentPath;
            } else if (config.pathPattern) {
                // Replace :id with a regex to match digits
                const pattern = config.pathPattern.replace(':id', '(\\d+)');
                const regex = new RegExp(`^${pattern}$`);
                return regex.test(currentPath);
            }
            return false;
        });

        if (pathConfig && pathConfig.setup) {
            pathConfig.setup();
        }
    }

    waitForElement(selector, timeout = 5000) {
        return new Promise((resolve, reject) => {
            const startTime = Date.now();
            const interval = setInterval(() => {
                const element = $(selector);
                if (element.length > 0) {
                    clearInterval(interval);
                    resolve(element);
                } else if (Date.now() - startTime > timeout) {
                    clearInterval(interval);
                    reject(`Element ${selector} not found within ${timeout}ms`);
                }
            }, 100);
        });
    }

    async setupChangeFormEndpointMonitor() {
        try {
            const inputGroup = await this.waitForElement('#id_ad_groups_input');
            let timeoutId = null;
            inputGroup.on('input', (event) => {
                const inputElement = event.target;
                if (timeoutId !== null) {
                    clearTimeout(timeoutId);
                }
                timeoutId = setTimeout(async () => {
                    if (!inputElement.value) return; // Guard clause for empty input

                    let formData = new FormData();
                    formData.append('action', 'active_directory_query');
                    formData.append('base_dn', 'DC=win,DC=dtu,DC=dk');
                    formData.append('search_filter', `(&(objectClass=group)(cn=*${inputElement.value}*))`);
                    formData.append('search_attributes', 'cn,canonicalName,distinguishedName');
                    formData.append('limit', '5');

                    try {
                        let response = await this.baseAppUtils.restAjax('POST', '/myview/ajax/', formData);
                        console.log('Response:', response);

                        formData = new FormData();
                        formData.append('action', 'ajax_change_form_update_form_ad_groups');
                        formData.append('ad_groups', JSON.stringify(response.data));
                        formData.append('path', window.location.pathname);
                        response = await this.baseAppUtils.restAjax('POST', '/myview/ajax/', formData);
                        console.log('Reloading page...');
                        location.reload();
                    } catch (error) {
                        console.error('An error occurred: ', error);
                    } finally {
                        timeoutId = null;
                    }
                }, 500);
            });
        } catch (error) {
            console.error(error);
        }
    }

    async setupOrganizationalUnitLimiterMonitor() {
        try {
            const searchBar = await this.waitForElement('#searchbar');
            searchBar.on('input', (event) => {
                console.log('Searchbar input text:', event.target.value);
            });
        } catch (error) {
            console.error(error);
        }
    }

    static getInstance(uiBinder = VicChangeFormUIBinder.getInstance(), baseUIBinder = BaseUIBinder.getInstance(), baseAppUtils = BaseAppUtils.getInstance()) {
        if (!VicChangeFormApp.instance) {
            VicChangeFormApp.instance = new VicChangeFormApp(uiBinder, baseUIBinder, baseAppUtils);
        }
        return VicChangeFormApp.instance;
    }
}

class VicChangeFormUIBinder {
    constructor() {
        if (!VicChangeFormUIBinder.instance) {
            // Define any UI elements here if needed
            VicChangeFormUIBinder.instance = this;
        }
        return VicChangeFormUIBinder.instance;
    }

    static getInstance() {
        if (!VicChangeFormUIBinder.instance) {
            VicChangeFormUIBinder.instance = new VicChangeFormUIBinder();
        }
        return VicChangeFormUIBinder.instance;
    }
}

document.addEventListener('DOMContentLoaded', function () {
    const app = VicChangeFormApp.getInstance();
});
