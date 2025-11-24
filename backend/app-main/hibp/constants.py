"""Static metadata for the HIBP Django app."""

HIBP_ENDPOINT_PATHS = {
    "/hibp/v3/subscribeddomains",
    "/hibp/v3/subscription/status",
    "/hibp/v3/breacheddomain/{domain}",
    "/hibp/v3/dataclasses",
    "/hibp/v3/breachedaccount/{account}",
    "/hibp/v3/breaches",
    "/hibp/v3/breach/{name}",
    "/hibp/v3/pasteaccount/{account}",
    "/hibp/v3/stealerlogsbyemaildomain/{domain}",
    "/hibp/v3/stealerlogsbyemail/{account}",
    "/hibp/v3/stealerlogsbywebsitedomain/{domain}",
    "/hibp/range/{prefix}",
}
