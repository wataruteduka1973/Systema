document.addEventListener('DOMContentLoaded', () => {
    const base = '/taskle/api/v1/saved-searches';
    const message = document.getElementById('savedSearchMessage');
    const csrf = () => document.cookie.split('; ').find(row => row.startsWith('csrftoken='))?.split('=')[1] || '';
    const notify = (text, danger = false) => {
        if (!message) return;
        message.textContent = text;
        message.className = `alert ${danger ? 'alert-danger' : 'alert-success'}`;
    };
    const payload = form => {
        const data = Object.fromEntries(new FormData(form));
        data.minimumPrice = data.minimumPrice || 0;
        data.maximumPrice = data.maximumPrice || null;
        data.endingWithinMinutes = data.endingWithinMinutes || null;
        data.excludedKeywords = (data.excludedKeywords || '').split(',').map(word => word.trim()).filter(Boolean);
        data.isActive = form.elements.isActive ? form.elements.isActive.checked : true;
        data.name = (data.name || data.keyword || '').trim();
        return data;
    };
    const request = async (url, method, body) => {
        const response = await fetch(url, { method, headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() }, body: body ? JSON.stringify(body) : undefined });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || '保存条件を処理できませんでした');
        return data;
    };

    window.saveTargetSearchConditions = async form => {
        if (!form || document.body.dataset.authenticated !== 'true') return null;
        const data = payload(form);
        data.name = (data.name || data.keyword || '').trim();
        data.replaceExisting = true;
        try {
            const result = await request(base, 'POST', data);
            notify(`「${data.name}」の条件を自動保存しました。`);
            return result.item;
        } catch (error) {
            notify(`分析結果は表示しましたが、条件を保存できませんでした: ${error.message}`, true);
            return null;
        }
    };

    document.querySelectorAll('.saved-search-create-form, #savedSearchCreateForm').forEach(form => {
        form.addEventListener('submit', async event => {
            event.preventDefault();
            const button = form.querySelector('button[type="submit"]');
            const spinner = button?.querySelector('.spinner-border');
            if (button?.disabled) return;
            if (button) button.disabled = true;
            if (spinner) spinner.classList.remove('d-none');
            try {
                const data = payload(form);
                data.replaceExisting = true;
                const result = await request(base, 'POST', data);
                notify('条件を作成し、ターゲット分析を実行しています。');
                await request(`${base}/${result.item.id}/run`, 'POST');
                location.href = `/accounts/profile/?saved_search=${result.item.id}#saved-search-results`;
            } catch (error) {
                notify(error.message, true);
                if (button) button.disabled = false;
                if (spinner) spinner.classList.add('d-none');
            }
        });
    });

    document.querySelectorAll('[data-saved-search-id]').forEach(container => {
        const id = container.dataset.savedSearchId;
        const form = container.querySelector('.saved-search-edit');
        if (form) form.addEventListener('submit', async event => {
            event.preventDefault();
            try { await request(`${base}/${id}`, 'PATCH', payload(form)); location.reload(); }
            catch (error) { notify(error.message, true); }
        });
        const runButton = container.querySelector('.saved-search-run');
        if (runButton) runButton.addEventListener('click', async () => {
            const spinner = runButton.querySelector('.spinner-border');
            runButton.disabled = true;
            spinner?.classList.remove('d-none');
            try {
                const result = await request(`${base}/${id}/run`, 'POST');
                if (container.dataset.savedSearchSurface === 'target' && window.renderTargetAnalysisResult) {
                    window.renderTargetAnalysisResult(result);
                    notify('保存条件でターゲット分析を更新しました。');
                    document.getElementById('medianPriceBox')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
                } else {
                    location.href = `/accounts/profile/?saved_search=${id}#saved-search-results`;
                }
            } catch (error) {
                notify(error.message, true);
            } finally {
                runButton.disabled = false;
                spinner?.classList.add('d-none');
            }
        });
        const deleteButton = container.querySelector('.saved-search-delete');
        if (deleteButton) deleteButton.addEventListener('click', async () => {
            if (!window.confirm('この保存条件を削除しますか？')) return;
            try { await request(`${base}/${id}`, 'DELETE'); container.remove(); notify('保存条件を削除しました。'); }
            catch (error) { notify(error.message, true); }
        });
    });
});
