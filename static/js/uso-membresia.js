document.addEventListener("DOMContentLoaded", function () {
    function actualizarPeriodo(formulario) {
        var modo = formulario.querySelector("[data-uso-modo]").value;
        formulario.querySelectorAll("[data-uso-campo]").forEach(function (grupo) {
            var visible = grupo.dataset.usoCampo === modo;
            grupo.hidden = !visible;
            grupo.querySelectorAll("input").forEach(function (campo) { campo.disabled = !visible; });
        });
    }

    var formulario = document.querySelector("[data-uso-formulario]");
    if (!formulario) return;
    actualizarPeriodo(formulario);

    var tarjeta = formulario.closest(".tarjeta-filtros-contenido");
    tarjeta.addEventListener("change", function (evento) {
        if (evento.target.matches("[data-uso-modo]")) actualizarPeriodo(evento.target.form);
    });
    tarjeta.addEventListener("filtros:actualizados", function (evento) {
        actualizarPeriodo(evento.target);
    });
});
