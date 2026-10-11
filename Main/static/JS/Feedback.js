/**
 * In-page feedback messages that replace window.alert().
 *
 * Messages render as dismissible Bootstrap alerts in a fixed region, so the page keeps its
 * form input and results. Text is always set with textContent; server messages are never
 * interpreted as HTML.
 *
 *   SystemaFeedback.error('検索に失敗しました');   // stays until closed
 *   SystemaFeedback.success('更新しました');        // closes after a few seconds
 *   if (!response.ok) throw await SystemaFeedback.responseError(response, '更新に失敗しました');
 *   ... .catch(error => SystemaFeedback.errorFrom(error, '更新に失敗しました'));
 */
(function () {
    'use strict';

    const REGION_ID = 'systemaFeedback';
    const MAX_MESSAGES = 3;
    const AUTO_CLOSE_MS = 5000;
    const VARIANTS = {
        error: { css: 'alert-danger', role: 'alert', autoClose: false },
        warning: { css: 'alert-warning', role: 'alert', autoClose: false },
        success: { css: 'alert-success', role: 'status', autoClose: true },
        info: { css: 'alert-info', role: 'status', autoClose: true },
    };

    function region() {
        let element = document.getElementById(REGION_ID);
        if (!element) {
            element = document.createElement('div');
            element.id = REGION_ID;
            element.className = 'systema-feedback';
            document.body.appendChild(element);
        }
        return element;
    }

    function remove(message) {
        if (message.isConnected) message.remove();
    }

    function show(kind, text) {
        const variant = VARIANTS[kind] || VARIANTS.info;
        const message = document.createElement('div');
        message.className = `alert ${variant.css} alert-dismissible shadow-sm mb-2`;
        message.setAttribute('role', variant.role);
        message.dataset.feedbackKind = kind;

        const body = document.createElement('div');
        body.className = 'systema-feedback__text';
        body.textContent = String(text ?? '');
        message.appendChild(body);

        const close = document.createElement('button');
        close.type = 'button';
        close.className = 'btn-close';
        close.setAttribute('aria-label', '閉じる');
        close.addEventListener('click', () => remove(message));
        message.appendChild(close);

        const container = region();
        container.appendChild(message);
        while (container.children.length > MAX_MESSAGES) container.firstElementChild.remove();
        if (variant.autoClose) window.setTimeout(() => remove(message), AUTO_CLOSE_MS);
        return message;
    }

    /** Build a user-facing message from a failed fetch Response (JSON `error`/`message` if any). */
    async function messageFrom(response, fallback) {
        let detail = '';
        try {
            const data = await response.clone().json();
            detail = (data && (data.error || data.message)) || '';
        } catch (_) {
            detail = '';
        }
        return detail ? `${fallback}: ${detail}` : `${fallback}（HTTP ${response.status}）`;
    }

    /** An Error for a failed Response whose `userMessage` is safe to show in the page. */
    async function responseError(response, fallback) {
        const error = new Error(`HTTP ${response.status}`);
        error.userMessage = await messageFrom(response, fallback);
        return error;
    }

    /** Show a caught error: its server message when present, else the fallback and detail. */
    function errorFrom(error, fallback) {
        const detail = error && error.message ? `: ${error.message}` : '';
        return show('error', (error && error.userMessage) || `${fallback}${detail}`);
    }

    window.SystemaFeedback = {
        error: text => show('error', text),
        warning: text => show('warning', text),
        success: text => show('success', text),
        info: text => show('info', text),
        clear: () => { region().replaceChildren(); },
        messageFrom,
        responseError,
        errorFrom,
    };
})();
