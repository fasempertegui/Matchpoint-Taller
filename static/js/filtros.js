document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("form[data-filtros-automaticos]").forEach(function (formulario) {
        var valoresIniciales = new Map();
        var tieneSegmentos = formulario.querySelector('input[type="radio"]') !== null;
        formulario.querySelectorAll('input[type="text"], input[type="search"], input[type="date"]').forEach(function (campo) {
            valoresIniciales.set(campo, campo.value);
        });

        formulario.addEventListener("change", function (evento) {
            if (evento.target.matches("select, input[type=radio]")) formulario.requestSubmit();
        });

        formulario.addEventListener("focusout", function (evento) {
            var campo = evento.target;
            if (!valoresIniciales.has(campo) || campo.value === valoresIniciales.get(campo)) return;
            var siguiente = evento.relatedTarget;
            if (siguiente && siguiente.closest("[data-limpiar-filtros]")) return;
            if (tieneSegmentos && siguiente?.matches("select, input[type=radio]")) return;
            formulario.requestSubmit();
        });

        formulario.addEventListener("keydown", function (evento) {
            if (evento.key !== "Enter" || !valoresIniciales.has(evento.target)) return;
            evento.preventDefault();
            formulario.requestSubmit();
        });
    });
});
