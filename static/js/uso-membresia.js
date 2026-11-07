document.addEventListener("DOMContentLoaded", function () {
    var formulario = document.querySelector("[data-uso-formulario]");
    if (!formulario) return;
    var modo = formulario.querySelector("[data-uso-modo]");
    function actualizarPeriodo() {
        formulario.querySelectorAll("[data-uso-campo]").forEach(function (grupo) {
            var visible = grupo.dataset.usoCampo === modo.value;
            grupo.hidden = !visible;
            grupo.querySelectorAll("input").forEach(function (campo) { campo.disabled = !visible; });
        });
    }
    modo.addEventListener("change", actualizarPeriodo);
    actualizarPeriodo();
});
