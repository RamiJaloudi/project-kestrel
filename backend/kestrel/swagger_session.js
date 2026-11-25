// Same-origin Swagger reuses the portal's protected cookie, including on reload.
window.kestrelSwaggerRequest = async (request) => {
    const target = new URL(request.url, window.location.href);
    if (target.origin !== window.location.origin) throw new Error('Same-origin API required');
    const method = (request.method || 'GET').toUpperCase();
    if (['GET', 'HEAD', 'OPTIONS'].includes(method)) return request;
    if (['/api/v1/auth/login', '/api/v1/auth/session', '/api/v1/auth/preferences', '/oauth/token'].includes(target.pathname)) return request;
    const response = await fetch('/api/v1/auth/session', {method: 'POST', credentials: 'same-origin'});
    if (response.ok) {
        request.headers = request.headers || {};
        request.headers['X-CSRF-Token'] = (await response.json()).csrf_token;
    }
    return request;
};
