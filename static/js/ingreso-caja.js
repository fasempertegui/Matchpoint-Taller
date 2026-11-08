(function () {
    "use strict";
    var formulario = document.querySelector("[data-ingreso-formulario]");
    if (!formulario) return;
    var medio = formulario.querySelector("[data-ingreso-medio]");
    function actualizarMedio() {
        var requiereReferencia = ["transferencia", "tarjeta", "qr"].includes(medio.value);
        formulario.querySelectorAll("[data-ingreso-no-efectivo]").forEach(function (grupo) {
            grupo.hidden = !requiereReferencia;
            grupo.querySelectorAll("input").forEach(function (campo) {
                campo.required = requiereReferencia;
            });
        });
    }
    medio.addEventListener("change", actualizarMedio);
    actualizarMedio();
})();
