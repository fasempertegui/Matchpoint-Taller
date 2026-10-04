document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("form[data-filtros-automaticos]").forEach(function (formulario) {
        var valoresTexto = new Map();
        formulario.querySelectorAll('input[type="text"], input[type="search"]').forEach(function (campo) {
            valoresTexto.set(campo, campo.value);
        });

        formulario.addEventListener("change", function (evento) {
            if (evento.target.matches("select")) formulario.requestSubmit();
        });

        formulario.addEventListener("focusout", function (evento) {
            var campo = evento.target;
            if (!valoresTexto.has(campo) || campo.value === valoresTexto.get(campo)) return;
            if (evento.relatedTarget && evento.relatedTarget.closest("[data-limpiar-filtros]")) return;
            formulario.requestSubmit();
        });

        formulario.addEventListener("keydown", function (evento) {
            if (evento.key !== "Enter" || !valoresTexto.has(evento.target)) return;
            evento.preventDefault();
            formulario.requestSubmit();
        });
    });
});
