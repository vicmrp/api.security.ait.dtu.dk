// vic_search_form.js

class VicSearchFormApp {
    constructor(uiBinder = VicSearchFormUIBinder.getInstance(), baseUIBinder = BaseUIBinder.getInstance(), baseAppUtils = BaseAppUtils.getInstance()) {
        if (!VicSearchFormApp.instance) {
            this.uiBinder = uiBinder;
            this.baseUIBinder = baseUIBinder;
            this.baseAppUtils = baseAppUtils;
            this.ENDS_WITH_A_COMMON_NAME = true;
            this.pathsConfig = {
                searchBarUnitLimiter: {
                    path: "/admin/myview/adorganizationalunitlimiter/",
                    setup: this.setupSearchBarForUnitLimiter.bind(this)
                },
                searchBarGroupAssociation: {
                    path: "/admin/myview/adgroupassociation/",
                    setup: this.setupSearchBarForGroupAssociation.bind(this)
                }
            };
            this.monitorPaths();
            VicSearchFormApp.instance = this;
        }
        return VicSearchFormApp.instance;
    }

    monitorPaths() {
        const currentPath = window.location.pathname;
        const pathConfig = Object.values(this.pathsConfig).find(config => config.path === currentPath);

        if (pathConfig && pathConfig.setup) {
            pathConfig.setup();
        }
    }

    setupSearchBarForUnitLimiter() {
        const searchBar = this.uiBinder.searchBar;

        // Display expansion glass
        this.uiBinder.vicreSearchAndFindByCanonicalNameSearchBar.css('display', 'inline-block');
        this.uiBinder.djangoVanillaSearchBar.hide();

        // Append spinner element next to the search bar
        this.uiBinder.appendSpinner();

        searchBar.on('input', (event) => {
            const input = $(event.target);
            const isValid = this.isValidCanonicalName(input.val());
            const currentTheme = localStorage.getItem("theme") || "dark";

            // Define colors for dark and light modes
            const colors = {
                dark: {
                    valid: '#006400', // Dark green
                    invalid: '#8B0000', // Dark red
                    defaultBg: '#333333', // Dark gray
                    textColor: '#FFFFFF' // White text
                },
                light: {
                    valid: '#90EE90', // Light green
                    invalid: '#FFB6C1', // Light red
                    defaultBg: '#FFFFFF', // White
                    textColor: '#000000' // Black text
                }
            };

            const themeColors = colors[currentTheme];

            if (!input.val()) {
                // Reset to default background color if input is empty
                input.css('backgroundColor', themeColors.defaultBg);
                input.css('color', themeColors.textColor);
            } else if (isValid) {
                // Set background color to green if the input is a valid canonical name
                input.css('backgroundColor', themeColors.valid);
                input.css('color', themeColors.textColor);
            } else {
                // Set background color to red if the input is not a valid canonical name
                input.css('backgroundColor', themeColors.invalid);
                input.css('color', themeColors.textColor);
            }
        });

        const form = document.querySelector('#changelist-search');

        form.addEventListener('submit', async (event) => {
            event.preventDefault();

            const input = form.querySelector('input[type="text"]');
            const canonicalName = input.value;

            if (!input.value || !this.isValidCanonicalName(canonicalName)) {
                alert('Please enter a valid canonical name.');
                return;
            } // Guard clause for empty input

            const distinguishedName = this.canonicalToDistinguishedName(canonicalName, !this.ENDS_WITH_A_COMMON_NAME);
            console.log(distinguishedName); // Output the distinguished name for testing

            let formData = new FormData();
            formData.append('action', 'ajax__search_form__add_new_organizational_unit');
            formData.append('distinguished_name', distinguishedName);
            try {
                // Show the spinner
                this.uiBinder.showSpinner();

                const response = await this.baseAppUtils.restAjax('POST', '/myview/ajax/', formData);

                if (response.status === 200) {
                    // Handle 200 OK status
                    console.log('Success: ', response);
                    // Reload the page
                    location.reload();
                } else if (response.status === 201) {
                    // Handle 201 Created status
                    console.log('Created: ', response);
                    // Reload the page
                    location.reload();
                } else if (response.status === 500) {
                    // Handle 500 Internal Server Error status
                    console.error('Server error: ', response);
                    alert(`Server error: ${response.data.error}`);
                } else {
                    // Handle other statuses
                    console.log('Other status: ', response);
                }
            } catch (error) {
                // Handle any errors that occurred during the execution of the restAjax function
                console.error('An error occurred: ', error);
            } finally {
                // Hide the spinner
                this.uiBinder.hideSpinner();
            }
        });
    }

    setupSearchBarForGroupAssociation() {
        const searchBar = this.uiBinder.searchBar;

        // Display expansion glass
        this.uiBinder.vicreSearchAndFindByCanonicalNameSearchBar.css('display', 'inline-block');
        this.uiBinder.djangoVanillaSearchBar.hide();

        // Append spinner element next to the search bar
        this.uiBinder.appendSpinner();

        searchBar.on('input', (event) => {
            const input = $(event.target);
            const isValid = this.isValidCanonicalName(input.val());
            const currentTheme = localStorage.getItem("theme") || "dark";

            // Define colors for dark and light modes
            const colors = {
                dark: {
                    valid: '#006400', // Dark green
                    invalid: '#8B0000', // Dark red
                    defaultBg: '#333333', // Dark gray
                    textColor: '#FFFFFF' // White text
                },
                light: {
                    valid: '#90EE90', // Light green
                    invalid: '#FFB6C1', // Light red
                    defaultBg: '#FFFFFF', // White
                    textColor: '#000000' // Black text
                }
            };

            const themeColors = colors[currentTheme];

            if (!input.val()) {
                // Reset to default background color if input is empty
                input.css('backgroundColor', themeColors.defaultBg);
                input.css('color', themeColors.textColor);
            } else if (isValid) {
                // Set background color to green if the input is a valid canonical name
                input.css('backgroundColor', themeColors.valid);
                input.css('color', themeColors.textColor);
            } else {
                // Set background color to red if the input is not a valid canonical name
                input.css('backgroundColor', themeColors.invalid);
                input.css('color', themeColors.textColor);
            }
        });

        const form = document.querySelector('#changelist-search');

        form.addEventListener('submit', async (event) => {
            event.preventDefault();

            const input = form.querySelector('input[type="text"]');
            const canonicalName = input.value;

            if (!input.value || !this.isValidCanonicalName(canonicalName)) {
                alert('Please enter a valid canonical name.');
                return;
            } // Guard clause for empty input

            const distinguishedName = this.canonicalToDistinguishedName(canonicalName, this.ENDS_WITH_A_COMMON_NAME);
            console.log(distinguishedName); // Output the distinguished name for testing

            let formData = new FormData();
            formData.append('action', 'ajax__search_form__add_new_ad_group_associations');
            formData.append('distinguished_name', distinguishedName);
            try {
                // Show the spinner
                this.uiBinder.showSpinner();

                const response = await this.baseAppUtils.restAjax('POST', '/myview/ajax/', formData);

                if (response.status === 200) {
                    // Handle 200 OK status
                    console.log('Success: ', response);
                    // Reload the page
                    location.reload();
                } else if (response.status === 201) {
                    // Handle 201 Created status
                    console.log('Created: ', response);
                    // Reload the page
                    location.reload();
                } else if (response.status === 500) {
                    // Handle 500 Internal Server Error status
                    console.error('Server error: ', response);
                    alert(`Server error: ${response.data.error}`);
                } else {
                    // Handle other statuses
                    console.log('Other status: ', response);
                }
            } catch (error) {
                // Handle any errors that occurred during the execution of the restAjax function
                console.error('An error occurred: ', error);
            } finally {
                // Hide the spinner
                this.uiBinder.hideSpinner();
            }
        });
    }

    isValidCanonicalName(canonicalName) {
        const regex = /^win\.dtu\.dk\/([a-zA-Z0-9\s\-]+\/?)*$/;
        return regex.test(canonicalName);
    }

    canonicalToDistinguishedName(canonicalName, endsWithCommonName) {
        let parts = canonicalName.split('/');
        let domainParts = parts[0].split('.');
        let organizationalUnits = parts.slice(1).reverse();

        let distinguishedName = [];

        // Add organizational units
        organizationalUnits.forEach((ou, index) => {
            if (endsWithCommonName && index === 0) {
                distinguishedName.push(`CN=${ou}`);
            } else {
                distinguishedName.push(`OU=${ou}`);
            }
        });

        // Add domain components
        domainParts.forEach(dc => {
            distinguishedName.push(`DC=${dc}`);
        });

        return distinguishedName.join(',');
    }

    static getInstance(uiBinder = VicSearchFormUIBinder.getInstance(), baseUIBinder = BaseUIBinder.getInstance(), baseAppUtils = BaseAppUtils.getInstance()) {
        if (!VicSearchFormApp.instance) {
            VicSearchFormApp.instance = new VicSearchFormApp(uiBinder, baseUIBinder, baseAppUtils);
        }
        return VicSearchFormApp.instance;
    }
}

class VicSearchFormUIBinder {
    constructor() {
        if (!VicSearchFormUIBinder.instance) {
            this.searchBar = $('#searchbar');
            this.vicreSearchAndFindByCanonicalNameSearchBar = $('#vicre-search-and-find-by-canonicalname-searchbar');
            this.djangoVanillaSearchBar = $('#django-vanilla-searchbar');
            this.spinnerElement = null;
            VicSearchFormUIBinder.instance = this;
        }
        return VicSearchFormUIBinder.instance;
    }

    appendSpinner() {
        if (!this.spinnerElement) {
            this.spinnerElement = $('<div>', {
                id: 'search-spinner',
                class: 'spinner-border text-primary',
                style: 'display: none; margin-left: 10px;',
                role: 'status'
            }).append($('<span>', { class: 'visually-hidden', text: 'Loading...' }));
            this.searchBar.after(this.spinnerElement);
        }
    }

    showSpinner() {
        if (this.spinnerElement) {
            this.spinnerElement.show();
        }
    }

    hideSpinner() {
        if (this.spinnerElement) {
            this.spinnerElement.hide();
        }
    }

    static getInstance() {
        if (!VicSearchFormUIBinder.instance) {
            VicSearchFormUIBinder.instance = new VicSearchFormUIBinder();
        }
        return VicSearchFormUIBinder.instance;
    }
}

document.addEventListener('DOMContentLoaded', function () {
    const app = VicSearchFormApp.getInstance();
});
