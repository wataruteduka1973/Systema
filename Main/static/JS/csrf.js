(function () {
    'use strict';

    function getCookie(name) {
        const prefix = `${name}=`;
        return document.cookie
            .split(';')
            .map((value) => value.trim())
            .find((value) => value.startsWith(prefix))
            ?.slice(prefix.length) || '';
    }

    window.systemaCsrfHeaders = function (headers = {}) {
        return {
            ...headers,
            'X-CSRFToken': decodeURIComponent(getCookie('csrftoken')),
        };
    };
}());
