// ============================================
// DVP Challenge - View Script
// ============================================

if (window.$ === undefined) window.$ = CTFd.lib.$;

CTFd._internal.challenge.data = undefined;
CTFd._internal.challenge.renderer = null;

CTFd._internal.challenge.preRender = function() {
    console.log('[DVP] preRender called');
};

CTFd._internal.challenge.render = null;

CTFd._internal.challenge.postRender = function() {
    console.log('[DVP] postRender called');
    
    // ========== ДОБАВЬТЕ ЭТИ ТРИ СТРОКИ ==========
    $('.modal-backdrop').remove();
    $('body').removeClass('modal-open');
    // ============================================

    loadDVPInfo();
};

var dvpTimer = undefined;

// ============================================
// Загрузка информации об окружении
// ============================================

function loadDVPInfo() {
    var challenge_id = CTFd._internal.challenge.data.id;
    
    CTFd.fetch('/api/v1/dvp/status?challenge_id=' + challenge_id, {
        method: 'GET',
        credentials: 'same-origin',
        headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
    }).then(function(response) {
        return response.json();
    }).then(function(response) {
        console.log('[DVP] Status response:', response);
        
        // Очищаем старый таймер
        if (dvpTimer !== undefined) {
            clearInterval(dvpTimer);
            dvpTimer = undefined;
        }
        
        if (response.status === 'running') {
            // Окружение запущено
            $('#dvp-panel-stopped').hide();
            $('#dvp-panel-started').show();
            
            $('#dvp-url').attr('href', response.url);
            $('#dvp-url').text(response.url);
            $('#dvp-status-text').text('Запущено');
            
            // Запускаем таймер
            var expiresAt = response.expires_at;
            
            function updateTimer() {
                var now = Math.floor(Date.now() / 1000);
                var remaining = expiresAt - now;
                
                if (remaining <= 0) {
                    $('#dvp-timer').text('Истекло');
                    clearInterval(dvpTimer);
                    dvpTimer = undefined;
                    loadDVPInfo();
                    return;
                }
                
                var hours = Math.floor(remaining / 3600);
                var minutes = Math.floor((remaining % 3600) / 60);
                var seconds = remaining % 60;
                
                $('#dvp-timer').text(
                    hours + ':' + 
                    minutes.toString().padStart(2, '0') + ':' + 
                    seconds.toString().padStart(2, '0')
                );
            }
            
            updateTimer();
            dvpTimer = setInterval(updateTimer, 1000);
            
        } else if (response.status === 'already_running') {
            // Уже запущено (обрабатываем как running)
            $('#dvp-panel-stopped').hide();
            $('#dvp-panel-started').show();
            $('#dvp-url').attr('href', response.url);
            $('#dvp-url').text(response.url);
            $('#dvp-status-text').text('Запущено');
            
            var expiresAt = response.expires_at;
            
            function updateTimer2() {
                var now = Math.floor(Date.now() / 1000);
                var remaining = expiresAt - now;
                
                if (remaining <= 0) {
                    $('#dvp-timer').text('Истекло');
                    clearInterval(dvpTimer);
                    dvpTimer = undefined;
                    loadDVPInfo();
                    return;
                }
                
                var hours = Math.floor(remaining / 3600);
                var minutes = Math.floor((remaining % 3600) / 60);
                var seconds = remaining % 60;
                
                $('#dvp-timer').text(
                    hours + ':' + 
                    minutes.toString().padStart(2, '0') + ':' + 
                    seconds.toString().padStart(2, '0')
                );
            }
            
            updateTimer2();
            dvpTimer = setInterval(updateTimer2, 1000);
            
        } else {
            // Окружение не запущено
            $('#dvp-panel-started').hide();
            $('#dvp-panel-stopped').show();
            $('#dvp-status-text').text('Не запущено');
        }
    }).catch(function(error) {
        console.error('[DVP] Status error:', error);
        $('#dvp-panel-started').hide();
        $('#dvp-panel-stopped').show();
    });
}

// ============================================
// Запуск окружения
// ============================================

CTFd._internal.challenge.launch = function() {
    var challenge_id = CTFd._internal.challenge.data.id;

        // ========== ДОБАВЬТЕ ЭТИ ТРИ СТРОКИ ==========
    $('.modal-backdrop').remove();
    $('body').removeClass('modal-open');
    // ============================================
    
    $('#dvp-button-launch').text('Запуск...');
    $('#dvp-button-launch').prop('disabled', true);
    
    $('#dvp-button-launch').text('Запуск...');
    $('#dvp-button-launch').prop('disabled', true);
    
    CTFd.fetch('/api/v1/dvp/launch', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'CSRF-Token': window.csrf_nonce
        },
        body: JSON.stringify({ challenge_id: challenge_id })
    }).then(function(response) {
        return response.json();
    }).then(function(response) {
        console.log('[DVP] Launch response:', response);
        
        if (response.status === 'launched' || response.status === 'already_running') {
            CTFd._functions.events.eventAlert({
                title: 'Успех',
                html: 'Окружение запущено!',
                button: 'OK'
            });
            
            // ВАЖНО: обновляем интерфейс
            loadDVPInfo();
        } else {
            CTFd._functions.events.eventAlert({
                title: 'Ошибка',
                html: response.error || 'Не удалось запустить окружение',
                button: 'OK'
            });
        }
    }).catch(function(error) {
        console.error('[DVP] Launch error:', error);
        CTFd._functions.events.eventAlert({
            title: 'Ошибка',
            html: 'Сетевая ошибка при запуске',
            button: 'OK'
        });
    }).finally(function() {
        $('#dvp-button-launch').text('🚀 Запустить окружение');
        $('#dvp-button-launch').prop('disabled', false);
    });
};

// ============================================
// Остановка окружения
// ============================================

CTFd._internal.challenge.terminate = function() {
    var challenge_id = CTFd._internal.challenge.data.id;

    $('.modal-backdrop').remove();
    $('body').removeClass('modal-open');
    
    if (!confirm('Остановить окружение? Все данные будут потеряны.')) {
        return;
    }
    
    $('#dvp-button-terminate').text('Остановка...');
    $('#dvp-button-terminate').prop('disabled', true);
    
    CTFd.fetch('/api/v1/dvp/terminate', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'CSRF-Token': window.csrf_nonce
        },
        body: JSON.stringify({ challenge_id: challenge_id })
    }).then(function(response) {
        return response.json();
    }).then(function(response) {
        console.log('[DVP] Terminate response:', response);
        
        if (response.status === 'terminated') {
            CTFd._functions.events.eventAlert({
                title: 'Успех',
                html: 'Окружение остановлено',
                button: 'OK'
            });
            loadDVPInfo();
        }
    }).catch(function(error) {
        console.error('[DVP] Terminate error:', error);
    }).finally(function() {
        $('#dvp-button-terminate').text('⏹ Остановить');
        $('#dvp-button-terminate').prop('disabled', false);
    });
};

// ============================================
// Продление окружения
// ============================================

// CTFd._internal.challenge.extend = function() {
//     var challenge_id = CTFd._internal.challenge.data.id;
    
//     $('#dvp-button-extend').text('Продление...');
//     $('#dvp-button-extend').prop('disabled', true);
    
//     CTFd.fetch('/api/v1/dvp/extend', {
//         method: 'POST',
//         credentials: 'same-origin',
//         headers: {
//             'Accept': 'application/json',
//             'Content-Type': 'application/json',
//             'CSRF-Token': window.csrf_nonce
//         },
//         body: JSON.stringify({ 
//             challenge_id: challenge_id,
//             extend_by: 1800
//         })
//     }).then(function(response) {
//         return response.json();
//     }).then(function(response) {
//         console.log('[DVP] Extend response:', response);
        
//         if (response.status === 'extended') {
//             CTFd._functions.events.eventAlert({
//                 title: 'Успех',
//                 html: 'Время продлено на 30 минут',
//                 button: 'OK'
//             });
//             loadDVPInfo();
//         }
//     }).catch(function(error) {
//         console.error('[DVP] Extend error:', error);
//     }).finally(function() {
//         $('#dvp-button-extend').text('⏰ Продлить');
//         $('#dvp-button-extend').prop('disabled', false);
//     });
// };

// ============================================
// Привязка событий к кнопкам
// ============================================

$(document).ready(function() {
    console.log('[DVP] Binding buttons...');
    
    $(document).on('click', '#dvp-button-launch', function(e) {
        e.preventDefault();
        CTFd._internal.challenge.launch();
    });
    
    $(document).on('click', '#dvp-button-terminate', function(e) {
        e.preventDefault();
        CTFd._internal.challenge.terminate();
    });
    
    // $(document).on('click', '#dvp-button-extend', function(e) {
    //     e.preventDefault();
    //     CTFd._internal.challenge.extend();
    // });
    
    console.log('[DVP] Buttons bound');
});