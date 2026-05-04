if (window.$ === undefined) window.$ = CTFd.lib.$;

CTFd._internal.challenge.data = undefined;
CTFd._internal.challenge.renderer = null;

CTFd._internal.challenge.preRender = function() { console.log('[DVP] preRender called'); };
CTFd._internal.challenge.render = null;

CTFd._internal.challenge.postRender = function() {
    console.log('[DVP] postRender called');
    $('.modal-backdrop').remove();
    $('body').removeClass('modal-open');
    loadDVPInfo();
    startPolling();
};

var dvpTimer = undefined;
var pollingInterval = undefined;

function loadDVPInfo() {
    var challenge_id = CTFd._internal.challenge.data.id;
    
    CTFd.fetch('/api/v1/dvp/status?challenge_id=' + challenge_id, {
        method: 'GET', credentials: 'same-origin',
        headers: {'Accept': 'application/json', 'Content-Type': 'application/json'}
    }).then(function(response) { return response.json(); })
    .then(function(response) {
        if (dvpTimer !== undefined) { clearInterval(dvpTimer); dvpTimer = undefined; }
        
        if (response.status === 'running' || response.status === 'already_running') {
            $('#dvp-panel-stopped').hide();
            $('#dvp-panel-started').show();
            
            var urlsContainer = $('#dvp-urls');
            urlsContainer.empty();
            if (response.urls && response.urls.length > 0) {
                response.urls.forEach(function(url, i) {
                    urlsContainer.append(
                        '<h6 class="card-subtitle mb-2 text-muted">ВМ ' + i + ': <a href="' + url + '" target="_blank">' + url + '</a></h6>'
                    );
                });
            } else {
                urlsContainer.append('<h6 class="card-subtitle mb-2 text-muted">⏳ Ожидание ингрессов...</h6>');
            }
            
            if (response.check_status === 'success') {
                $('#dvp-status-text').text('✅ Выполнено');
            } else if (response.check_status === 'failed') {
                $('#dvp-status-text').text('❌ Не выполнено');
            } else {
                $('#dvp-status-text').text('Запущено');
            }
            
            if (response.expires_at) { startTimer(response.expires_at); }
        } else {
            $('#dvp-panel-started').hide();
            $('#dvp-panel-stopped').show();
        }
    }).catch(function(error) {
        $('#dvp-panel-started').hide(); $('#dvp-panel-stopped').show();
    });
}

function startTimer(expiresAt) {
    function update() {
        var now = Math.floor(Date.now() / 1000), remaining = expiresAt - now;
        if (remaining <= 0) {
            $('#dvp-timer').text('Истекло').css('color', 'red');
            clearInterval(dvpTimer); dvpTimer = undefined; return;
        }
        var h = Math.floor(remaining/3600), m = Math.floor((remaining%3600)/60), s = remaining%60;
        $('#dvp-timer').text(h+':'+m.toString().padStart(2,'0')+':'+s.toString().padStart(2,'0'));
    }
    update(); dvpTimer = setInterval(update, 1000);
}

function startPolling() {
    if (pollingInterval) clearInterval(pollingInterval);
    pollingInterval = setInterval(function() {
        if (CTFd._internal.challenge.data && CTFd._internal.challenge.data.id) {
            loadDVPInfo();
        }
    }, 5000);
}

CTFd._internal.challenge.launch = function() {
    var challenge_id = CTFd._internal.challenge.data.id;
    $('.modal-backdrop').remove(); $('body').removeClass('modal-open');
    $('#dvp-button-launch').text('Запуск...').prop('disabled', true);
    
    CTFd.fetch('/api/v1/dvp/launch', {
        method: 'POST', credentials: 'same-origin',
        headers: {'Accept': 'application/json', 'Content-Type': 'application/json', 'CSRF-Token': CTFd.config.csrfNonce},
        body: JSON.stringify({ challenge_id: challenge_id })
    }).then(r => r.json()).then(function(response) {
        if (response.status === 'launched' || response.status === 'already_running') {
            CTFd._functions.events.eventAlert({title: 'Успех', html: 'Окружение запущено!', button: 'OK'});
            loadDVPInfo();
            startPolling();
        } else {
            CTFd._functions.events.eventAlert({title: 'Ошибка', html: response.error || 'Не удалось', button: 'OK'});
        }
    }).finally(function() { $('#dvp-button-launch').text('🚀 Запустить окружение').prop('disabled', false); });
};

CTFd._internal.challenge.terminate = function() {
    if (!confirm('Остановить окружение?')) return;
    var challenge_id = CTFd._internal.challenge.data.id;
    $('#dvp-button-terminate').text('Остановка...').prop('disabled', true);
    if (pollingInterval) { clearInterval(pollingInterval); pollingInterval = undefined; }
    
    CTFd.fetch('/api/v1/dvp/terminate', {
        method: 'POST', credentials: 'same-origin',
        headers: {'Accept': 'application/json', 'Content-Type': 'application/json', 'CSRF-Token': CTFd.config.csrfNonce},
        body: JSON.stringify({ challenge_id: challenge_id })
    }).then(r => r.json()).then(function(response) {
        if (response.status === 'terminated') {
            CTFd._functions.events.eventAlert({title: 'Успех', html: 'Окружение остановлено', button: 'OK'});
            loadDVPInfo();
        }
    }).finally(function() { $('#dvp-button-terminate').text('⏹ Остановить').prop('disabled', false); });
};

CTFd._internal.challenge.check = function() {
    var challenge_id = CTFd._internal.challenge.data.id;
    $('#dvp-button-check').text('Проверка...').prop('disabled', true);
    
    CTFd.fetch('/api/v1/dvp/check', {
        method: 'POST', credentials: 'same-origin',
        headers: {'Accept': 'application/json', 'Content-Type': 'application/json', 'CSRF-Token': CTFd.config.csrfNonce},
        body: JSON.stringify({ challenge_id: challenge_id })
    }).then(r => r.json()).then(function(response) {
        if (response.status === 'success') {
            CTFd._functions.events.eventAlert({title: '✅ Успех', html: 'Задание выполнено!', button: 'OK'});
            $('#dvp-status-text').text('✅ Выполнено');
        } else {
            CTFd._functions.events.eventAlert({title: '❌ Ошибка', html: response.message || 'Не выполнено', button: 'OK'});
            $('#dvp-status-text').text('❌ Не выполнено');
        }
    }).finally(function() { $('#dvp-button-check').text('✅ Проверить').prop('disabled', false); });
};

$(document).ready(function() {
    $(document).on('click', '#dvp-button-launch', function(e) { e.preventDefault(); CTFd._internal.challenge.launch(); });
    $(document).on('click', '#dvp-button-terminate', function(e) { e.preventDefault(); CTFd._internal.challenge.terminate(); });
    $(document).on('click', '#dvp-button-check', function(e) { e.preventDefault(); CTFd._internal.challenge.check(); });
});