document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("form[data-confirmar]").forEach(function (formulario) {
        formulario.addEventListener("submit", function (evento) {
            var selector = formulario.dataset.confirmarSi;
            if (selector && !formulario.querySelector(selector)) return;
            if (!window.confirm(formulario.dataset.confirmar)) {
                evento.preventDefault();
            }
        });
    });
});
