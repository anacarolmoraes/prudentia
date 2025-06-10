// prudentIA - static/js/main.js

// Função para ser executada quando o DOM estiver completamente carregado
document.addEventListener('DOMContentLoaded', function() {
    console.log('prudentIA DOM carregado e pronto!');

    // Exemplo: Adicionar um listener para um botão com ID 'meuBotao'
    // const meuBotao = document.getElementById('meuBotao');
    // if (meuBotao) {
    //     meuBotao.addEventListener('click', function() {
    //         alert('Botão clicado!');
    //     });
    // }

    // Exemplo: Manipular o comportamento do toggle do sidebar (se existir)
    const sidebarToggle = document.querySelector('.menu-toggle'); // Assumindo que o toggle do menu tem essa classe
    const sidebar = document.querySelector('.sidebar'); // Assumindo que o sidebar tem essa classe

    if (sidebarToggle && sidebar) {
        sidebarToggle.addEventListener('click', function() {
            sidebar.classList.toggle('active');
            // Poderia também adicionar uma classe ao body para ajustar o conteúdo principal
            // document.body.classList.toggle('sidebar-active');
        });
    }
    
    // Inicializar tooltips do Bootstrap (se Bootstrap estiver sendo usado)
    if (typeof bootstrap !== 'undefined' && typeof bootstrap.Tooltip !== 'undefined') {
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }

    // Inicializar popovers do Bootstrap (se Bootstrap estiver sendo usado)
    if (typeof bootstrap !== 'undefined' && typeof bootstrap.Popover !== 'undefined') {
        const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
        popoverTriggerList.map(function (popoverTriggerEl) {
            return new bootstrap.Popover(popoverTriggerEl);
        });
    }
    
    // Lidar com alertas/mensagens do Django para que possam ser fechados
    const djangoAlerts = document.querySelectorAll('.alert .btn-close');
    djangoAlerts.forEach(function(alertCloseButton) {
        alertCloseButton.addEventListener('click', function() {
            // O Bootstrap já lida com o fechamento se o HTML estiver correto
            // Se não estiver usando Bootstrap para alertas, adicione a lógica de remoção aqui.
            // Exemplo: this.closest('.alert').remove();
        });
    });

});

// Funções Utilitárias Globais (Exemplos)

/**
 * Faz uma requisição AJAX (Fetch API)
 * @param {string} url - A URL para a requisição
 * @param {object} options - Opções para a requisição (method, headers, body, etc.)
 * @returns {Promise<object>} - Uma promessa que resolve com os dados JSON da resposta
 */
async function fetchData(url, options = {}) {
    try {
        const response = await fetch(url, options);
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ message: response.statusText }));
            throw new Error(errorData.message || `Erro HTTP: ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error('Erro na requisição Fetch:', error);
        throw error; // Re-throw para que o chamador possa lidar com o erro
    }
}

/**
 * Obtém o valor de um cookie CSRF
 * @param {string} name - O nome do cookie (geralmente 'csrftoken')
 * @returns {string|null} - O valor do cookie ou null se não encontrado
 */
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            // O cookie começa com o nome que queremos?
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

/**
 * Adiciona o token CSRF aos headers de uma requisição AJAX
 * @param {object} options - Opções da requisição Fetch
 * @returns {object} - Opções da requisição com o header CSRFToken adicionado
 */
function addCsrfTokenToHeaders(options = {}) {
    const csrftoken = getCookie('csrftoken');
    if (!options.headers) {
        options.headers = {};
    }
    if (csrftoken) {
        options.headers['X-CSRFToken'] = csrftoken;
    }
    // Se for enviar JSON, certifique-se de que o Content-Type está correto
    if (options.body && typeof options.body === 'object' && !(options.body instanceof FormData)) {
        options.headers['Content-Type'] = 'application/json';
        options.body = JSON.stringify(options.body);
    }
    return options;
}

/**
 * Exibe uma notificação simples (pode ser expandida com bibliotecas como Toastify, Noty, etc.)
 * @param {string} message - A mensagem da notificação
 * @param {string} type - O tipo de notificação ('success', 'error', 'info', 'warning')
 * @param {number} duration - Duração em milissegundos (0 para persistente)
 */
function showNotification(message, type = 'info', duration = 3000) {
    // Implementação básica de notificação (pode ser substituída por algo mais robusto)
    const notificationArea = document.getElementById('notification-area') || createNotificationArea();
    
    const notification = document.createElement('div');
    notification.className = `prudentia-notification notification-${type}`;
    notification.textContent = message;
    
    notificationArea.appendChild(notification);
    
    if (duration > 0) {
        setTimeout(() => {
            notification.classList.add('fade-out');
            setTimeout(() => notification.remove(), 500); // Tempo para a animação de fade-out
        }, duration);
    }
    
    // Estilos básicos para a notificação (adicionar ao seu CSS principal)
    /*
    #notification-area {
        position: fixed;
        top: 20px;
        right: 20px;
        z-index: 1050;
        display: flex;
        flex-direction: column;
        gap: 10px;
    }
    .prudentia-notification {
        padding: 15px 20px;
        border-radius: 5px;
        color: #fff;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        opacity: 1;
        transition: opacity 0.5s ease-in-out;
    }
    .prudentia-notification.fade-out {
        opacity: 0;
    }
    .notification-success { background-color: var(--color-success, #28a745); }
    .notification-error { background-color: var(--color-error, #dc3545); }
    .notification-info { background-color: var(--color-info, #17a2b8); }
    .notification-warning { background-color: var(--color-warning, #ffc107); color: #000; }
    */
}

function createNotificationArea() {
    let area = document.getElementById('notification-area');
    if (!area) {
        area = document.createElement('div');
        area.id = 'notification-area';
        document.body.appendChild(area);
    }
    return area;
}

// Exemplo de como usar as funções:
//
// Para fazer uma requisição POST com CSRF token:
// async function enviarDados(url, data) {
//     try {
//         const options = addCsrfTokenToHeaders({
//             method: 'POST',
//             body: data // Pode ser um objeto JS, será stringificado
//         });
//         const responseData = await fetchData(url, options);
//         console.log('Dados enviados com sucesso:', responseData);
//         showNotification('Dados enviados com sucesso!', 'success');
//     } catch (error) {
//         console.error('Falha ao enviar dados:', error);
//         showNotification(`Falha ao enviar dados: ${error.message}`, 'error');
//     }
// }
//
// Para fazer uma requisição GET:
// async function buscarDados(url) {
//     try {
//         const data = await fetchData(url);
//         console.log('Dados recebidos:', data);
//     } catch (error) {
//         console.error('Falha ao buscar dados:', error);
//     }
// }

console.log('main.js carregado.');
