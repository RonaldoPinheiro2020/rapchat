// URL do backend FastAPI rodando no uvicorn
const API_URL = "http://127.0.0.1:5000";

document.getElementById('login-form').addEventListener('submit', async (e) => {
    e.preventDefault(); // Impede a página de recarregar

    const usernameInput = document.getElementById('username').value;
    const passwordInput = document.getElementById('password').value;
    const errorDiv = document.getElementById('error-message');

    // Oculta mensagens de erro anteriores
    errorDiv.classList.add('hidden');

    try {
        // FastAPI geralmente espera OAuth2 no formato Form Data para login padrão
        const formData = new URLSearchParams();
        formData.append('username', usernameInput);
        formData.append('password', passwordInput);

        const response = await fetch(`${API_URL}/auth/login`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: formData
        });

        const data = await response.json();

        if (!response.ok) {
            // Se o backend rejeitar, mostra o erro da API (ex: "Senha incorreta")
            throw new Error(data.detail || "Erro ao realizar login");
        }

        // Sucesso! Guardamos o Token JWT no navegador para as próximas requisições
        localStorage.setItem('token', data.access_token);
        alert('Login realizado com sucesso! Pronto para carregar o chat.');
        
        // Aqui depois vamos esconder o card de login e mostrar a tela de chat
        // document.getElementById('login-card').classList.add('hidden');

    } catch (error) {
        // Exibe o erro na tela para o usuário
        errorDiv.innerText = error.message;
        errorDiv.classList.remove('hidden');
    }
});